import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parser import parse_tenhou_tile, parse_meld_code

class TestParser(unittest.TestCase):
    def test_parse_tenhou_tile(self):
        # 128 is 1m, dora indicator, no red
        res = parse_tenhou_tile(128)
        self.assertEqual(res['tile'], '1m')
        self.assertTrue(res['is_dora_indicator'])
        self.assertFalse(res['is_red'])

        # 5 is 6m
        res = parse_tenhou_tile(5)
        self.assertEqual(res['tile'], '6m')
        self.assertFalse(res['is_dora_indicator'])
        self.assertFalse(res['is_red'])
        
        # 31 is P (Haku / White Dragon)
        res = parse_tenhou_tile(31)
        self.assertEqual(res['tile'], 'P')

    def test_parse_meld_code(self):
        res = parse_meld_code('24619')
        self.assertEqual(res['raw'], 24619)
        self.assertIn('meld_type', res)

if __name__ == '__main__':
    unittest.main()
