"""
Mortal用特徴量抽出エンジン (Feature Extractor)
Implements: F-102 | ゲーム状態からMortalモデル入力テンソルへの変換
"""
import numpy as np
from server.models import GameState, PlayerState, TileSuit, MeldType, Tile

class MortalFeatureExtractor:
    """
    麻雀のゲームステートからONNXモデル用あるいはNumpyモデル用の多次元配列を生成します。
    ここでは、簡易Mortal互換形式として [10, 34] の2次元テンソルを抽出します。
    """

    CHANNELS = 10
    TILE_TYPES = 34

    @staticmethod
    def _tile_to_index(tile: Tile) -> int:
        if tile.suit == TileSuit.MAN:
            return tile.number - 1
        elif tile.suit == TileSuit.PIN:
            return 9 + tile.number - 1
        elif tile.suit == TileSuit.SOU:
            return 18 + tile.number - 1
        elif tile.suit == TileSuit.WIND:
            return 27 + tile.number - 1
        return 0

    def extract_features(self, state: GameState, player_seat: int) -> np.ndarray:
        """
        [10, 34] の特徴量行列を生成。
        0: 自身の手牌
        1: 自身の河
        2: 自身の副露
        3: 下家の河
        4: 下家の副露
        5: 対面の河
        6: 対面の副露
        7: 上家の河
        8: 上家の副露
        9: ドラ表示牌
        """
        features = np.zeros((self.CHANNELS, self.TILE_TYPES), dtype=np.float32)

        # 0: 自身の手牌
        me = state.players[player_seat]
        for t in me.hand:
            idx = self._tile_to_index(t)
            features[0, idx] += 1.0

        # 他家のオフセット
        # 自身=0, 下家(seat+1)=1, 対面(seat+2)=2, 上家(seat+3)=3
        
        for i in range(4):
            target_seat = (player_seat + i) % 4
            target_player = state.players[target_seat]
            
            # discards
            discard_channel = 1 + i * 2
            if discard_channel < 9:
                for d in target_player.discards:
                    idx = self._tile_to_index(d)
                    features[discard_channel, idx] += 1.0
            
            # melds
            meld_channel = 2 + i * 2
            if meld_channel < 9:
                for m in target_player.melds:
                    for t in m.tiles:
                        idx = self._tile_to_index(t)
                        features[meld_channel, idx] += 1.0

        # 9: ドラ表示牌
        for indicator in state.dora_indicators:
            idx = self._tile_to_index(indicator)
            features[9, idx] += 1.0

        return features
