import unittest

import dwinlcd
from ui_case_light import CaseLightMixin
from ui_mmu import MMUViewMixin


class UIModularityTests(unittest.TestCase):
    def test_feature_views_are_composed_as_mixins(self):
        self.assertTrue(issubclass(dwinlcd.DWIN_LCD, MMUViewMixin))
        self.assertTrue(issubclass(dwinlcd.DWIN_LCD, CaseLightMixin))
        self.assertNotIn('Draw_MMU_Status', dwinlcd.DWIN_LCD.__dict__)
        self.assertNotIn('Draw_Case_Light_Menu', dwinlcd.DWIN_LCD.__dict__)
        self.assertIs(dwinlcd.DWIN_LCD.Draw_MMU_Status, MMUViewMixin.Draw_MMU_Status)
        self.assertIs(dwinlcd.DWIN_LCD.HMI_Case_Light, CaseLightMixin.HMI_Case_Light)

    def test_removed_legacy_symbols_do_not_return(self):
        for name in (
            'Language_Chinese', 'PREPARE_CASE_LANG', 'Back_Print',
            'Popup_Window', 'MaxSpeed', 'MaxAcceleration', 'MaxJerk',
            'Step', 'ICON_Language', 'ICON_ReadEEPROM',
            'ICON_ResumeEEPROM', 'ICON_StockConfiguraton',
        ):
            self.assertFalse(hasattr(dwinlcd.DWIN_LCD, name), name)


if __name__ == '__main__':
    unittest.main()
