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
        self.assertEqual(constants['Language_English'], manifest['english_jpg'])
        for name, entry in manifest['icons'].items():
            self.assertEqual(constants[name], entry['id'], name)
            self.assertGreater(entry['width'], 0)
            self.assertGreater(entry['height'], 0)

    def test_source_copy_regions_remain_within_verified_sheet(self):
        tree = ast.parse((ROOT / 'dwinlcd.py').read_text())
        checked = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in ('Frame_AreaCopy', 'Frame_TitleCopy'):
                continue
            try:
                cache, x1, y1, x2, y2 = [ast.literal_eval(arg) for arg in node.args[:5]]
            except (ValueError, TypeError):
                continue
            self.assertEqual(cache, 1)
            self.assertTrue(0 <= x1 <= x2 < 272 and 0 <= y1 <= y2 < 480, node.lineno)
            checked += 1
        self.assertGreater(checked, 0)
