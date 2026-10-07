import copy
from concurrent.futures import Future
import unittest
from unittest.mock import Mock, patch

from mmu_control import MMUState
from test_capabilities import snapshot, printer


def mmu_snapshot(**changes):
    data = snapshot()
    data['objects'] += ['mmu', 'mmu_machine']
    raw = dict(num_gates=4, enabled=True, gate=2, tool=2, action='Idle',
               print_state='ready', filament='Loaded', filament_pos=10,
               gate_status=[1, 1, 1, 0], ttg_map=[0, 1, 2, 3],
               gate_color_rgb=[[1, 0, 0], [1, 1, 1], [0, 0, 1], [1, 1, 0]],
               gate_material=['PLA', 'PLA', 'PLA', 'PETG'],
               gate_spool_id=[101, 102, 104, -1],
               sensors={'toolhead': True, 'extruder': False, 'mmu_shared_exit': None},
               sync_drive=False, bowden_progress=-1)
    raw.update(endless_spool_enabled=0, endless_spool_groups=[0, 1, 2, 3],
               gate_color=['ff0000', 'ffffff', '0000ff', 'ffff00'],
               spoolman_support='push', gate_temperature=[205, 210, 215, 230])
    raw.update(changes)
    data['status']['mmu'] = raw
    return data


class MMUControlTests(unittest.TestCase):
    def make(self, **changes):
        data = mmu_snapshot(**changes)
        p = printer(data)
        p.subscription.responses_since.return_value = (0, ())
        p.subscription.request.return_value = Future()
        return p, data, p.mmu_session

    def test_missing_and_malformed_fields_stay_unknown(self):
        data = mmu_snapshot()
        for key in ('enabled', 'tool', 'action', 'print_state', 'sensors', 'sync_drive'):
            data['status']['mmu'].pop(key)
        m = MMUState.from_snapshot(data)
        self.assertIsNone(m.enabled)
        self.assertIsNone(m.tool)
        self.assertIsNone(m.locked)
        self.assertTrue(m.busy)
        self.assertEqual(m.sensors, ())
        self.assertIsNone(m.sync_drive)
        for value in (False, '4', 0, 257):
            data['status']['mmu']['num_gates'] = value
            self.assertIsNone(MMUState.from_snapshot(data))

    def test_position_and_sensor_truth_are_distinct(self):
        m = MMUState.from_snapshot(mmu_snapshot(filament_pos=3, bowden_progress=68.2))
        self.assertEqual(m.filament, 'unknown')
        self.assertEqual(m.bowden_progress, 68)
        self.assertEqual(dict(m.sensors), {'toolhead': True, 'extruder': False, 'mmu_shared_exit': None})
        for value in (-1, 101, float('nan'), True, '68'):
            self.assertIsNone(MMUState.from_snapshot(mmu_snapshot(bowden_progress=value)).bowden_progress)

    def test_paused_unlocked_ignores_deprecated_is_locked_alias(self):
        m = MMUState.from_snapshot(mmu_snapshot(print_state='paused', is_locked=True))
        self.assertFalse(m.locked)

    def test_many_tools_can_map_to_one_gate(self):
        m = MMUState.from_snapshot(mmu_snapshot(ttg_map=[2, 2, 2, 3]))
        self.assertEqual(m.tools_for_gate(2), (0, 1, 2))

    def test_map_bulk_save_preserves_many_to_one_and_never_moves(self):
        p, _, s = self.make()
        op = s.prepare('map', values=[2, 2, 2, 0])
        self.assertEqual(op.script, 'MMU_TTG_MAP MAP=2,2,2,0')
        self.assertEqual(op.values, (2, 2, 2, 0))
        p.subscription.request.assert_not_called()

    def test_map_rejects_incomplete_invalid_or_unknown_mapping(self):
        for values in ([], [0, 1], [0, 1, 2, 4], [0, 1, 2, -1],
                       [0, 1, 2, True], [0, 1, 2, '3']):
            _, _, s = self.make()
            with self.subTest(values=values), self.assertRaises(ValueError):
                s.prepare('map', values=values)
        _, _, s = self.make(ttg_map=[0, 1])
        with self.assertRaises(ValueError): s.prepare('map', values=[0, 1, 2, 3])

    def test_map_print_pause_busy_and_external_map_change_are_guarded(self):
        for state in ('printing', 'paused'):
            p, data, s = self.make()
            data['status']['print_stats']['state'] = state
            with self.subTest(state=state), self.assertRaises(ValueError):
                s.prepare('map', values=[2]*4)
        p, data, s = self.make()
        op = s.prepare('map', values=[2]*4)
        data['status']['mmu']['ttg_map'] = [1]*4
        with self.assertRaises(ValueError): s.start(op)
        p.subscription.request.assert_not_called()
        _, _, s = self.make(action='Loading')
        with self.assertRaises(ValueError): s.prepare('map', values=[2]*4)

    def test_map_completion_checks_entire_result_not_rpc_acceptance(self):
        for matches in (True, False):
            p, data, s = self.make()
            s.start(s.prepare('map', values=[2]*4))
            status = copy.deepcopy(data['status'])
            if matches: status['mmu']['ttg_map'] = [2]*4
            self.complete(s, p, status)
            self.assertEqual(s.phase, 'complete' if matches else 'error')

    def test_endless_state_accepts_integer_switch_and_preserves_group_ids(self):
        m = MMUState.from_snapshot(mmu_snapshot(endless_spool_enabled=1,
                                               endless_spool_groups=[10, 10, 99, 99]))
        self.assertTrue(m.endless_enabled)
        self.assertEqual(m.endless_groups, (10, 10, 99, 99))
        for value in ('1', 2, None):
            self.assertIsNone(MMUState.from_snapshot(mmu_snapshot(endless_spool_enabled=value)).endless_enabled)
        data = mmu_snapshot(endless_spool=1)
        del data['status']['mmu']['endless_spool_enabled']
        self.assertTrue(MMUState.from_snapshot(data).endless_enabled)

    def test_endless_saves_whole_draft_in_single_non_motion_command(self):
        p, _, s = self.make()
        op = s.prepare('endless', enabled=True, values=[99, 99, 2, 3])
        self.assertEqual(op.script, 'MMU_ENDLESS_SPOOL ENABLE=1 GROUPS=99,99,2,3')
        p.subscription.request.assert_not_called()
        s.start(op)
        self.assertTrue(p.subscription.request.call_args.kwargs['guard']())

    def test_endless_rejects_invalid_draft_before_partial_enable_is_possible(self):
        for values in ([0], [0, 1, 2, -1], [0, 1, 2, True], [0, 1, 2, '3']):
            p, _, s = self.make()
            with self.subTest(values=values), self.assertRaises(ValueError):
                s.prepare('endless', enabled=True, values=values)
            p.subscription.request.assert_not_called()
        for fields in ({'endless_spool_enabled': None}, {'endless_spool_groups': [0, 1]},
                       {'endless_spool_groups': [0, 1, 2, -1]}):
            _, _, s = self.make(**fields)
            with self.assertRaises(ValueError): s.prepare('endless', enabled=True, values=[0]*4)
        _, _, s = self.make()
        with self.assertRaises(ValueError): s.prepare('endless', enabled=1, values=[0]*4)

    def test_endless_confirmation_guard_rejects_group_material_color_changes(self):
        for field, values in (('endless_spool_groups', [2]*4),
                              ('gate_material', ['ABS']*4), ('gate_color', ['000000']*4)):
            p, data, s = self.make()
            s.start(s.prepare('endless', enabled=True, values=[0]*4))
            data['status']['mmu'][field] = values
            self.assertFalse(p.subscription.request.call_args.kwargs['guard']())

    def test_endless_completion_requires_both_enabled_and_group_result(self):
        for result in ('both', 'groups', 'enabled'):
            p, data, s = self.make()
            s.start(s.prepare('endless', enabled=True, values=[0]*4))
            status = copy.deepcopy(data['status'])
            if result != 'groups': status['mmu']['endless_spool_enabled'] = 1
            if result != 'enabled': status['mmu']['endless_spool_groups'] = [0]*4
            self.complete(s, p, status)
            self.assertEqual(s.phase, 'complete' if result == 'both' else 'error')

    def test_spool_assignment_and_clear_preserve_temperature_and_global_indices(self):
        for mode in ('off', 'readonly', 'push'):
            p, _, s = self.make(spoolman_support=mode)
            op = s.prepare('spool', gate=1, values=(501,))
            self.assertEqual(op.script, 'MMU_GATE_MAP GATE=1 SPOOLID=501 TEMP=210')
            self.assertIn('G2', op.label)
            self.assertEqual(op.expected_spool_ids, (101, 501, 104, -1))
            self.assertEqual(s.prepare('spool', gate=1, values=(-1,)).script,
                             'MMU_GATE_MAP GATE=1 SPOOLID=-1 TEMP=210')
            p.subscription.request.assert_not_called()

    def test_spool_invalid_id_gate_mode_and_metadata_never_enable_assignment(self):
        for sid in (0, -2, True, '45', None, 1.5):
            _, _, s = self.make()
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                s.prepare('spool', gate=0, values=(sid,))
        for gate in (-1, 4, None, True):
            _, _, s = self.make()
            with self.assertRaises(ValueError): s.prepare('spool', gate=gate, values=(1,))
        for fields in ({'spoolman_support': 'pull'}, {'spoolman_support': None},
                       {'spoolman_support': 'unexpected'}, {'gate_spool_id': [101]},
                       {'gate_temperature': [0]*4}, {'gate_temperature': [205.5]*4},
                       {'gate_temperature': []}):
            p, _, s = self.make(**fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                s.prepare('spool', gate=0, values=(501,))
            p.subscription.request.assert_not_called()
        p, data, s = self.make()
        del data['status']['mmu']['spoolman_support']
        with self.assertRaises(ValueError): s.prepare('spool', gate=0, values=(501,))

    def test_spool_confirmation_and_queue_guard_revalidate_ids_mode_temperature(self):
        for field, value in (('gate_spool_id', [5]*4), ('spoolman_support', 'pull'),
                             ('gate_temperature', [230]*4)):
            p, data, s = self.make()
            op = s.prepare('spool', gate=0, values=(501,))
            data['status']['mmu'][field] = value
            with self.assertRaises(ValueError): s.start(op)
            p.subscription.request.assert_not_called()
            p, data, s = self.make()
            s.start(s.prepare('spool', gate=0, values=(501,)))
            data['status']['mmu'][field] = value
            self.assertFalse(p.subscription.request.call_args.kwargs['guard']())

    def test_spool_result_checks_assignment_and_duplicate_removal(self):
        for ids, success in (([102, -1, 104, -1], True), ([102, 102, 104, -1], False),
                             ([101, 102, 104, -1], False), ([102, -1, -1, -1], False)):
            p, data, s = self.make()
            s.start(s.prepare('spool', gate=0, values=(102,)))
            status = copy.deepcopy(data['status'])
            status['mmu']['gate_spool_id'] = ids
            self.complete(s, p, status)
            self.assertEqual(s.phase, 'complete' if success else 'error')

    def test_spool_clear_verifies_other_gate_assignments_are_unchanged(self):
        p, data, s = self.make()
        s.start(s.prepare('spool', gate=0, values=(-1,)))
        status = copy.deepcopy(data['status'])
        status['mmu']['gate_spool_id'][0] = -1
        self.complete(s, p, status)
        self.assertEqual(s.phase, 'complete')

    def test_spool_printing_pause_busy_disabled_and_pending_are_locked(self):
        for ps in ('printing', 'paused'):
            p, data, s = self.make()
            data['status']['print_stats']['state'] = ps
            with self.assertRaises(ValueError): s.prepare('spool', gate=0, values=(501,))
        for fields in ({'action': 'Loading'}, {'enabled': False}):
            _, _, s = self.make(**fields)
            with self.assertRaises(ValueError): s.prepare('spool', gate=0, values=(501,))
        _, _, s = self.make()
        s.start(s.prepare('spool', gate=0, values=(501,)))
        with self.assertRaises(ValueError): s.prepare('spool', gate=1, values=(502,))

    def test_commands_use_zero_based_gates_and_explicit_eject(self):
        for action, script in [('unload', 'MMU_UNLOAD'), ('eject', 'MMU_EJECT GATE=2 FORCE=1')]:
            p, _, session = self.make()
            op = session.prepare(action, gate=2)
            self.assertEqual(op.script, script)
            self.assertIn('G3', op.label)
            p.subscription.request.assert_not_called()

    def test_empty_filament_actions_and_bypass(self):
        p, _, s = self.make(filament='Unloaded', filament_pos=0)
        for action, script in [('select', 'MMU_SELECT GATE=1'), ('preload', 'MMU_PRELOAD GATE=1'), ('check', 'MMU_CHECK_GATE GATE=1')]:
            self.assertEqual(s.prepare(action, gate=1).script, script)
        self.assertEqual(s.prepare('load', gate=2).script, 'MMU_LOAD')
        self.assertEqual(s.prepare('bypass').script, 'MMU_SELECT BYPASS=1')
        with self.assertRaises(ValueError): s.prepare('load', gate=1)
        with self.assertRaises(ValueError): s.prepare('unload', gate=2)
        with self.assertRaises(ValueError): s.prepare('load_extruder')

    def test_change_uses_tool_mapping_and_preserves_current_mapped_tool(self):
        _, _, s = self.make(ttg_map=[1, 1, 2, 3])
        op = s.prepare('change', gate=1)
        self.assertEqual(op.tool, 0)
        self.assertEqual(op.script, 'MMU_CHANGE_TOOL TOOL=0 STANDALONE=1')
        _, _, s = self.make(ttg_map=[1, 1, 1, 3])
        self.assertEqual(s.prepare('change', gate=1).tool, 2)

    def test_motion_is_locked_for_unknown_busy_disabled_and_wrong_target(self):
        for fields in ({'enabled': False}, {'enabled': None}, {'action': 'Loading'},
                       {'action': None}, {'filament': 'Unknown'}, {'print_state': 'pause_locked'}):
            _, _, s = self.make(**fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                s.prepare('unload', gate=2)
        _, _, s = self.make()
        for action, gate in [('unload', 1), ('eject', 1), ('select', 0), ('change', 3), ('unload', True), ('unload', -1), ('unload', 4)]:
            with self.subTest(action=action, gate=gate), self.assertRaises(ValueError):
                s.prepare(action, gate=gate)

    def test_paused_print_allows_recovery_but_not_routine_movement(self):
        p, data, s = self.make(print_state='pause_locked', filament='Unknown', filament_pos=-1)
        data['status']['print_stats']['state'] = 'paused'
        self.assertEqual(s.prepare('recover').script, 'MMU_RECOVER')
        self.assertEqual(s.prepare('unlock').script, 'MMU_UNLOCK')
        op = s.prepare('manual', gate=2, tool=2, loaded=False)
        self.assertEqual(op.script, 'MMU_RECOVER TOOL=2 GATE=2 LOADED=0')
        with self.assertRaises(ValueError): s.prepare('resume')
        with self.assertRaises(ValueError): s.prepare('change', gate=1)
        data['status']['mmu'].update(print_state='paused', filament='Loaded', filament_pos=10)
        self.assertEqual(s.prepare('resume').script, 'RESUME')
        data['status']['print_stats']['state'] = 'printing'
        with self.assertRaises(ValueError): s.prepare('recover')

    def test_confirmation_revalidates_external_changes_and_epoch(self):
        p, data, s = self.make()
        op = s.prepare('unload', gate=2)
        data['status']['mmu']['gate'] = 1
        with self.assertRaises(ValueError): s.start(op)
        p.subscription.request.assert_not_called()
        data['status']['mmu']['gate'] = 2
        data['epoch'] = 2
        with self.assertRaises(ValueError): s.start(op)

    def test_queue_guard_rejects_state_change_without_mutating_session(self):
        p, data, s = self.make()
        s.start(s.prepare('unload', gate=2))
        pending = s.pending
        guard = p.subscription.request.call_args.kwargs['guard']
        self.assertTrue(guard())
        self.assertIs(s.pending, pending)
        data['status']['print_stats']['state'] = 'printing'
        self.assertFalse(guard())
        self.assertIs(s.pending, pending)

    def test_duplicate_submission_is_rejected(self):
        p, _, s = self.make()
        op = s.prepare('unload', gate=2)
        s.start(op)
        with self.assertRaises(ValueError): s.start(op)
        self.assertEqual(p.subscription.request.call_count, 1)

    def test_command_completion_requires_actual_result_query(self):
        p, data, s = self.make()
        s.start(s.prepare('unload', gate=2))
        command = s.pending
        s.update()
        self.assertEqual(s.phase, 'running')
        query = Future()
        p.subscription.request.return_value = query
        command.set_result('ok')
        s.update()
        self.assertEqual(s.phase, 'confirming')
        self.assertIs(s.pending, query)
        status = copy.deepcopy(data['status'])
        status['mmu'].update(filament='Unloaded', filament_pos=0)
        query.set_result({'status': status})
        s.update()
        self.assertEqual(s.phase, 'complete')
        self.assertIsNone(s.pending)

    def test_accepted_noop_is_not_reported_as_completed(self):
        p, data, s = self.make()
        s.start(s.prepare('unload', gate=2))
        s.pending.set_result('ok')
        query = Future()
        p.subscription.request.return_value = query
        s.update()
        query.set_result({'status': data['status']})
        s.update()
        self.assertEqual(s.phase, 'error')
        self.assertIn('unconfirmed', s.message)

    def test_error_disconnect_timeout_never_replay(self):
        for case in ('error', 'disconnect', 'timeout', 'gcode'):
            p, data, s = self.make()
            s.start(s.prepare('unload', gate=2))
            if case == 'error': s.pending.set_exception(RuntimeError('failed'))
            elif case == 'disconnect': data['epoch'] += 1
            elif case == 'gcode': p.subscription.responses_since.return_value = (1, ('!! no filament',))
            with patch('mmu_control.time.monotonic', return_value=s.started + (301 if case == 'timeout' else 1)):
                s.update()
            self.assertEqual(s.phase, 'error')
            self.assertEqual(p.subscription.request.call_count, 1)
            self.assertIsNone(s.pending)

    def test_independent_error_cursor_does_not_consume_other_sessions(self):
        p, _, s = self.make()
        p.pop_gcode_response = Mock()
        s.start(s.prepare('unload', gate=2))
        s.update()
        p.pop_gcode_response.assert_not_called()

    def test_other_calibration_session_blocks_mmu(self):
        p, _, s = self.make()
        p.bed_mesh.pending = Future()
        with self.assertRaises(ValueError): s.prepare('unload', gate=2)

    def test_malformed_lock_and_filament_position_do_not_enable_motion(self):
        _, _, s = self.make(print_state='garbage')
        with self.assertRaises(ValueError): s.prepare('unload', gate=2)
        for value in ('10', True, float('nan')):
            _, _, s = self.make(filament_pos=value)
            with self.assertRaises(ValueError): s.prepare('unload', gate=2)

    def test_failed_result_requires_acknowledgement_before_new_operation(self):
        _, _, s = self.make()
        s.phase = 'error'
        with self.assertRaisesRegex(ValueError, 'Acknowledge'):
            s.prepare('unload', gate=2)

    def complete(self, session, p, status):
        session.pending.set_result('ok')
        query = Future()
        p.subscription.request.return_value = query
        session.update()
        query.set_result({'status': status})
        session.update()

    def test_bypass_and_extruder_only_completion_use_actual_state(self):
        p, data, s = self.make(filament='Unloaded', filament_pos=0)
        s.start(s.prepare('bypass'))
        status = copy.deepcopy(data['status'])
        status['mmu'].update(gate=-2, tool=-2)
        self.complete(s, p, status)
        self.assertEqual(s.phase, 'complete')
        p, data, s = self.make(gate=-2, tool=-2, filament='Unloaded', filament_pos=0)
        op = s.prepare('load_extruder')
        self.assertEqual(op.script, 'MMU_LOAD EXTRUDER_ONLY=1')
        s.start(op)
        status = copy.deepcopy(data['status'])
        status['mmu'].update(filament='Loaded', filament_pos=10)
        self.complete(s, p, status)
        self.assertEqual(s.phase, 'complete')

    def test_auto_manual_unlock_and_resume_are_separate_verified_results(self):
        for action in ('recover', 'manual', 'unlock', 'resume'):
            p, data, s = self.make(print_state='pause_locked', filament='Unknown', filament_pos=-1)
            data['status']['print_stats']['state'] = 'paused'
            if action == 'resume':
                data['status']['mmu'].update(print_state='paused', filament='Loaded', filament_pos=10)
            op = s.prepare(action, gate=2, tool=2, loaded=False) if action == 'manual' else s.prepare(action)
            s.start(op)
            status = copy.deepcopy(data['status'])
            if action in ('recover', 'manual'):
                status['mmu'].update(filament='Unloaded', filament_pos=0)
            elif action == 'unlock':
                status['mmu']['print_state'] = 'paused'
            else:
                status['mmu']['print_state'] = 'printing'
                status['print_stats']['state'] = 'printing'
            self.complete(s, p, status)
            with self.subTest(action=action):
                self.assertEqual(s.phase, 'complete')
                scripts = [call.args[1]['script'] for call in p.subscription.request.call_args_list
                           if call.args[0] == 'printer.gcode.script']
                self.assertEqual(scripts, [op.script])
                if action != 'resume': self.assertNotIn('RESUME', scripts)

    def test_disabled_mmu_and_error_lock_at_result_never_report_success(self):
        for field in ('enabled', 'print_state'):
            p, data, s = self.make()
            s.start(s.prepare('unload', gate=2))
            status = copy.deepcopy(data['status'])
            status['mmu'].update(filament='Unloaded', filament_pos=0)
            status['mmu'][field] = False if field == 'enabled' else 'pause_locked'
            self.complete(s, p, status)
            self.assertEqual(s.phase, 'error')

    def test_mmu_pending_blocks_all_calibration_entry_points(self):
        from test_bed_mesh import data as mesh_data
        from test_probe_wizard import data as probe_data
        from test_screws_tilt import data as screws_data
        for source, name in ((mesh_data(), 'bed_mesh'), (probe_data(), 'probe_wizard'), (screws_data(), 'screws_tilt')):
            p = printer(source)
            p.mmu_session.pending = Future()
            with self.subTest(name=name), self.assertRaises(ValueError):
                getattr(p, name).start()
            p.subscription.request.assert_not_called()
            p.sendGCode.assert_not_called()
