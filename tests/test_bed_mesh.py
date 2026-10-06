import copy
import unittest
from concurrent.futures import Future
from unittest.mock import Mock, patch

from test_capabilities import snapshot, printer, display
from printer_state import PrinterState
from bed_mesh import BedMeshSession, MeshData
from moonraker_client import MoonrakerError
from moonraker_subscription import MoonrakerSubscription


def data():
    source = snapshot(probe=True)
    source['settings']['bed_mesh'] = {'mesh_min': [20, 30], 'mesh_max': [220, 230], 'probe_count': [3, 3]}
    source['settings']['bltouch'].update(x_offset=-40, y_offset=-10)
    source['status']['configfile'] = {'save_config_pending': False, 'save_config_pending_items': {}}
    source['status']['bed_mesh'] = payload()['status']['bed_mesh']
    return source


def payload(name='lcd_mesh_1'):
    points = [[-.12, -.04, .02], [-.08, 0, .06], [-.03, .05, .12]]
    params = dict(min_x=20, max_x=220, min_y=30, max_y=230, x_count=3, y_count=3)
    return {'status': {'bed_mesh': dict(profile_name=name, mesh_min=[20, 30], mesh_max=[220, 230],
        probed_matrix=points, mesh_matrix=[[999]], profiles={name: dict(points=points, mesh_params=params)})}}


class MeshTests(unittest.TestCase):
    def make(self, source=None):
        p = printer(source or data())
        p.subscription.request.side_effect = lambda *a: Future()
        p.subscription.responses_since.return_value = (0, ())
        return p, p.bed_mesh

    def complete(self, session):
        session.pending.set_result(None)
        session.update()
        self.assertEqual(session.phase, 'reading')
        session.pending.set_result(payload(session.profile_name))
        session.update()
        self.assertEqual(session.phase, 'complete')

    def test_calibration_homing_completion_query_and_identical_repeat(self):
        p, session = self.make()
        for _ in range(2):
            session.start()
            self.assertIsNone(session.mesh)
            self.assertEqual(session.profile_name, 'lcd_mesh_2')
            p.subscription.request.assert_called_with('printer.gcode.script',
                {'script': 'BED_MESH_CALIBRATE PROFILE=lcd_mesh_2 ADAPTIVE=0'})
            session.update()
            self.assertEqual(session.phase, 'measuring')
            self.complete(session)
            self.assertEqual(session.mesh.extrema, (-.12, .12))
        self.assertEqual(p.subscription.request.call_count, 4)
        p.sendGCode.assert_not_called()
        source = data(); source['status']['toolhead']['homed_axes'] = 'xy'
        p, session = self.make(source);session.start()
        self.assertTrue(p.subscription.request.call_args.args[1]['script'].startswith('G28\n'))

    def test_start_guards_and_duplicate_submission(self):
        for case in ('printing', 'paused', 'manual', 'probe_missing', 'mesh_missing', 'recovery', 'screws', 'probe_busy', 'pending', 'invalid_grid', 'offline', 'epoch'):
            source = data()
            if case in ('printing', 'paused'):source['status']['print_stats']['state'] = case
            if case == 'manual':source['status']['manual_probe'] = {'is_active': True}
            if case == 'probe_missing':source['objects'].remove('probe')
            if case == 'mesh_missing':source['objects'].remove('bed_mesh')
            if case == 'pending':source['status']['configfile']['save_config_pending'] = True
            if case == 'invalid_grid':source['settings']['bed_mesh']['probe_count'] = [1, 3]
            p, session = self.make(source)
            if case == 'recovery':p._jog_restore = {'script': 'restore'}
            if case == 'screws':p.screws_tilt.pending = Future()
            if case == 'probe_busy':p.probe_wizard.pending = ('step', Future(), 0)
            if case == 'offline':p.connection_error = 'offline'
            if case == 'epoch':p.subscription.snapshot.return_value = dict(source, epoch=2)
            with self.subTest(case=case),self.assertRaises(ValueError):session.start()
            p.subscription.request.assert_not_called()
        p, session = self.make();session.start()
        with self.assertRaises(ValueError):session.start()
        self.assertEqual(p.subscription.request.call_count, 1)

    def test_profile_selection_is_read_only_immutable_and_uses_probed_points(self):
        p, session = self.make();session.refresh()
        result = payload();result['status']['bed_mesh']['profiles']['PLA 60C'] = copy.deepcopy(result['status']['bed_mesh']['profiles']['lcd_mesh_1'])
        session.pending.set_result(result);session.update()
        self.assertEqual(session.entries(), (None, 'lcd_mesh_1', 'PLA 60C'))
        mesh = session.view('PLA 60C')
        self.assertEqual(mesh.points[0][0], -.12)
        result['status']['bed_mesh']['profiles']['PLA 60C']['points'][0][0] = 88
        self.assertEqual(mesh.points[0][0], -.12)
        self.assertEqual(p.subscription.request.call_count, 1)
        p.sendGCode.assert_not_called()
        with self.assertRaises(ValueError):session.view('deleted')
        source = data(); source['epoch'] = 2;p.state = PrinterState.from_snapshot(source)
        with self.assertRaises(ValueError):session.view(None)

    def test_malformed_nonfinite_dimension_and_limits(self):
        for case in ('ragged', 'nan', 'inf', 'empty', 'boolean', 'limits', 'count'):
            result = payload();status = result['status']['bed_mesh']
            if case == 'ragged':status['probed_matrix'][0].pop()
            if case == 'nan':status['probed_matrix'][0][0] = float('nan')
            if case == 'inf':status['probed_matrix'][0][0] = float('inf')
            if case == 'boolean':status['probed_matrix'][0][0] = True
            if case == 'empty':status['probed_matrix'] = [[]]
            if case == 'limits':status['mesh_max'] = status['mesh_min']
            if case == 'count':status['profiles']['lcd_mesh_1']['mesh_params']['x_count'] = 4
            with self.subTest(case=case),self.assertRaises((ValueError,TypeError)):
                mesh = MeshData.current(status);MeshData.profile('lcd_mesh_1',status)

    def test_failure_disconnect_timeout_and_stale_result_never_succeed(self):
        for case in ('command', 'disconnect', 'epoch', 'timeout', 'stale', 'profile_changed'):
            p, session = self.make();session.start()
            if case == 'command':session.pending.set_exception(MoonrakerError('probe'))
            if case == 'disconnect':p.connection_error = 'offline'
            if case == 'epoch':p.state = PrinterState.from_snapshot(dict(data(),epoch=2))
            if case in ('stale', 'profile_changed'):
                session.pending.set_result(None);session.update()
                result = payload(session.profile_name)
                if case == 'stale':result['status']['bed_mesh']['profile_name'] = 'old'
                else:result['status']['bed_mesh']['profiles'][session.profile_name]['points'] = [[1,2,3]]*3
                session.pending.set_result(result)
            with patch('bed_mesh.time.monotonic',return_value=session.started+(901 if case=='timeout' else 1)):
                session.update()
            self.assertIn(session.phase, ('error','interrupted'))
            self.assertIsNone(session.mesh)
            self.assertIsNone(session.pending)
            self.assertEqual(p.subscription.request.call_count, 2 if case in ('stale','profile_changed') else 1)

    def test_progress_deduplicates_samples_and_maps_offset_coordinates(self):
        p, session = self.make();session.start()
        p.subscription.responses_since.return_value = (4, ('probe at 60.000,40.000 is z=2.10',
            'probe at 60.000,40.000 is z=2.11', 'probe at 260,240 is z=2.20', 'probe at 999,999 is z=2.30'))
        session.update()
        self.assertEqual(session.progress, {(0,0):2.11,(2,2):2.20})
        self.assertEqual(session.message, 'Probing: 2 points')
        self.assertIsNone(session.mesh)
        self.complete(session)
        self.assertEqual(session.mesh.points[0][0], -.12)

    def test_stop_uses_emergency_rpc_and_never_marks_result_complete(self):
        p, session = self.make();session.start();future = session.pending
        session.cancel()
        p.subscription.request.assert_called_with('printer.emergency_stop', {})
        session.pending.set_result(None);session.update()
        self.assertEqual(session.phase,'stopped');self.assertIsNone(session.mesh)
        self.assertTrue(future.cancelled())
        with self.assertRaises(ValueError):session.cancel()

    def test_save_validates_owned_profile_and_config_before_restart(self):
        for foreign in (False,True):
            p, session = self.make();session.start();self.complete(session);session.save()
            self.assertEqual(session.phase,'save_check')
            result = payload(session.profile_name)
            items = {'bed_mesh '+session.profile_name:{'points':'1,2,3'}}
            if foreign:items['probe'] = {'z_offset':'2.1'}
            result['status']['configfile'] = dict(save_config_pending=True,save_config_pending_items=items)
            session.pending.set_result(result);session.update()
            if foreign:
                self.assertEqual(session.phase,'error')
                self.assertNotIn({'script':'SAVE_CONFIG'}, [c.args[1] for c in p.subscription.request.call_args_list])
            else:
                p.subscription.request.assert_called_with('printer.gcode.script', {'script':'SAVE_CONFIG'})
                p.connection_error = 'restarting';session.update()
                self.assertEqual(session.phase,'interrupted')
                self.assertIn('check after restart',session.message)

    def test_round_layout_and_string_config(self):
        source=data();source['settings']['bed_mesh']=dict(mesh_radius=100,mesh_origin='110,120',round_probe_count=5)
        _, session=self.make(source);session.start()
        self.assertEqual(session.layout,((5,5),(10,20),(210,220)))
        source=data();source['settings']['bed_mesh']=dict(mesh_min='20,30',mesh_max='220,230',probe_count='3,5')
        _,session=self.make(source);session.start();self.assertEqual(session.layout[0],(3,5))


class ResponseTests(unittest.TestCase):
    def test_independent_response_cursors_bounded_history_and_queue(self):
        sub=MoonrakerSubscription('http://localhost:7125',autostart=False)
        self.assertEqual(sub.responses_since(None),(0,()))
        for i in range(300):sub._notification({'method':'notify_gcode_response','params':[str(i)]})
        cursor,responses=sub.responses_since(0)
        self.assertEqual(cursor,300);self.assertEqual(len(responses),256)
        self.assertEqual(responses[0],'44')
        self.assertEqual(sub.responses_since(299),(300,('299',)))
        self.assertEqual(sub.responses_since(cursor),(300,()))
        self.assertEqual(sub.gcode_responses.qsize(),64)
        self.assertEqual(sub.responses_since(299),(300,('299',)))
