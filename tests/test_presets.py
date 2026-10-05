import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from preset_store import PresetStore
from test_regressions import backend


def defaults():
    return [dict(name='PLA', hotend_temp=200, bed_temp=60, fan_speed=100),
            dict(name='ABS', hotend_temp=210, bed_temp=100, fan_speed=30)]


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'settings' / 'presets.json'

    def printer(self):
        with patch.object(backend, 'MoonrakerClient'), patch.object(backend, 'MoonrakerSubscription'):
            return backend.PrinterData(settings_path=self.path)

    def test_save_and_restart_preserve_all_values(self):
        first = self.printer()
        first.material_preset[0].hotend_temp = 225
        first.material_preset[0].bed_temp = 70
        first.material_preset[0].fan_speed = 40
        self.assertTrue(first.save_settings())
        second = self.printer()
        self.assertEqual(vars(second.material_preset[0]),
                         dict(name='PLA', hotend_temp=225, bed_temp=70, fan_speed=40))
        second.material_preset[0].hotend_temp = 230
        self.assertEqual(first.material_preset[0].hotend_temp, 225)

    def test_corrupt_file_keeps_defaults_and_is_not_overwritten(self):
        self.path.parent.mkdir()
        self.path.write_text('{broken')
        with self.assertLogs(level='WARNING'):
            printer = self.printer()
        self.assertEqual(printer.material_preset[0].hotend_temp, 200)
        self.assertIsNotNone(printer.settings_error)
        self.assertEqual(self.path.read_text(), '{broken')

    def test_replace_failure_preserves_existing_file_and_cleans_temporary(self):
        store = PresetStore(self.path)
        store.save(defaults())
        original = self.path.read_bytes()
        printer = self.printer()
        printer.material_preset[0].hotend_temp = 230
        with patch('preset_store.os.replace', side_effect=OSError('read-only')), self.assertLogs(level='ERROR'):
            self.assertFalse(printer.save_settings())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        self.assertTrue(printer.save_settings())
        self.assertIsNone(printer.settings_error)

    def test_invalid_documents_are_rejected_before_writing(self):
        store = PresetStore(self.path)
        for key, value in (('fan_speed', 101), ('hotend_temp', float('nan')),
                           ('bed_temp', -1), ('hotend_temp', True)):
            data = defaults()
            data[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                store.save(data)
        self.assertFalse(self.path.exists())

    def test_unsupported_version_does_not_partially_load(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps(dict(version=2, presets=defaults())))
        with self.assertLogs(level='WARNING'):
            printer = self.printer()
        self.assertEqual(printer.material_preset[1].fan_speed, 100)

    def test_default_path_honors_xdg_directory(self):
        with patch.dict('os.environ', {'XDG_CONFIG_HOME': self.directory.name}):
            self.assertEqual(PresetStore().path, Path(self.directory.name) / 'dwin-lcd/presets.json')
