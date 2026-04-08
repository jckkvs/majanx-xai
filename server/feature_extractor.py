"""
server/feature_extractor.py
Mortal標準特徴量抽出器 (196次元)
"""
from __future__ import annotations
import numpy as np
from typing import List, Optional
from server.models import GameState, Tile

class MortalFeatureExtractor:
    def __init__(self, feature_dim: int = 196):
        self.feature_dim = feature_dim
        self._suit_offset = {'m': 0, 'p': 9, 's': 18, 'z': 27}

    def extract(self, gs: GameState, seat: int) -> np.ndarray:
        """
        GameState → [1, 196] numpy array 変換
        """
        feat = np.zeros(self.feature_dim, dtype=np.float32)
        player = gs.players[seat]

        # 1. 手牌 (0-33): 枚数カウント
        for t in player.hand:
            feat[self._tile_to_idx(t)] += 1.0

        # 2. 捨て牌 (34-169): 他家を含む全プレイヤーの打牌バイナリマスク
        for p_idx, p in enumerate(gs.players):
            base = 34 + (p_idx * 34)
            for t in p.discards:
                feat[base + self._tile_to_idx(t)] = 1.0

        # 3. ドラ表示牌 (170-203): バイナリマスク
        for t in gs.dora_indicators:
            feat[170 + self._tile_to_idx(t)] = 1.0

        # 4. 場況ベクトル (170-195): 正規化メタデータ
        feat[170] = min(gs.turn_count / 24.0, 1.0)           # 巡目正規化
        feat[171] = 1.0 if player.is_riichi else 0.0         # 自家リーチ
        feat[172] = 1.0 if seat == gs.dealer else 0.0        # 親フラグ
        feat[173] = sum(1 for p in gs.players if p.is_riichi) / 3.0 # 他家リーチ密度
        feat[174] = len(player.melds) / 4.0                  # 副露数
        feat[175] = player.score / 50000.0                   # 点数正規化

        return feat[np.newaxis, :]  # Shape: (1, 196)

    def _tile_to_idx(self, tile: Tile) -> int:
        num = 5 if tile.is_red else int(tile.id[0])
        return self._suit_offset[tile.id[-1]] + (num - 1)
