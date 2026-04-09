import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from game import GameState

class TestGameEngine(unittest.TestCase):
    def test_game_init(self):
        state = GameState()
        self.assertEqual(len(state.hands), 4)
        self.assertEqual(len(state.hands[0]), 13)
        self.assertEqual(len(state.wall), 84) # 136 - 13*4
        
    def test_draw_and_discard(self):
        state = GameState()
        # Draw a tile
        tile = state.draw()
        self.assertIsNotNone(tile)
        self.assertEqual(len(state.hands[0]), 14)
        
        # Discard the tile
        success = state.discard(0, tile)
        self.assertTrue(success)
        self.assertEqual(len(state.hands[0]), 13)
        self.assertEqual(state.current_player, 1)

if __name__ == '__main__':
    unittest.main()
