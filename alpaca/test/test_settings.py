import unittest

from alpaca import alpaca_setting
from alpaca.settings import _ALPACA_SETTINGS


class AlpacaSettingsTestCase(unittest.TestCase):

    def test_use_builtin_hash_for_module(self):
        setting_name = 'use_builtin_hash_for_module'

        cur_setting = alpaca_setting(setting_name)
        self.assertIsInstance(cur_setting, list)

        new_setting = alpaca_setting(setting_name, ['test'])
        self.assertListEqual(new_setting, ['test'])
        self.assertListEqual(alpaca_setting(setting_name), ['test'])
        self.assertListEqual(_ALPACA_SETTINGS[setting_name], ['test'])

        # Test wrong type
        with self.assertRaises(ValueError):
            alpaca_setting(setting_name, "test wrong type")

        # Restore value
        alpaca_setting(setting_name, cur_setting)
        self.assertListEqual(_ALPACA_SETTINGS[setting_name], cur_setting)

    def test_wrong_setting_name(self):
        with self.assertRaises(ValueError):
            alpaca_setting("wrong_setting")


if __name__ == "__main__":
    unittest.main()