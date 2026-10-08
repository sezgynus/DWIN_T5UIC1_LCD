import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AssetContracts(unittest.TestCase):
    def test_ui_icon_ids_match_verified_stock_manifest(self):
        manifest = json.loads((ROOT / 'docs/lcd-assets.json').read_text())
        tree = ast.parse((ROOT / 'dwinlcd.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DWIN_LCD')
        constants = {n.targets[0].id: n.value.value for n in cls.body
                     if isinstance(n, ast.Assign) and len(n.targets) == 1
                     and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
        self.assertEqual(constants['ICON'], manifest['library'])
        # The legacy English JPEG cache is intentionally not a UI constant:
        # virtual display areas are reserved for managed custom atlases.
        self.assertNotIn('Language_English', constants)
        for name, entry in manifest['icons'].items():
            self.assertEqual(constants[name], entry['id'], name)
            self.assertGreater(entry['width'], 0)
            self.assertGreater(entry['height'], 0)

    def test_legacy_virtual_area_cache_is_not_used_by_ui(self):
        source = (ROOT / 'dwinlcd.py').read_text()
        tree = ast.parse(source)
        forbidden = {'cache_jpeg', 'show_jpeg', 'copy_cache', 'copy_cache1'}
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden:
                    calls.append((node.func.attr, node.lineno))
        self.assertEqual(calls, [])

