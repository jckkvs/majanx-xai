"""
手牌評価・受入計算（TileEfficiencyEngineに委譲）
"""
from typing import List, Dict, Any
from server.tile_eval.efficiency_engine import TileEfficiencyEngine, EngineContext
from server.tile_eval.shape_evaluator import EvalContext
from server.models import Tile

class HandEstimator:
    def __init__(self):
        self.engine = TileEfficiencyEngine()
        
    def evaluate(self, sim_hand: List[Tile], turn_count: int) -> Dict[str, float]:
        """打牌後の手牌の攻撃力を評価"""
        hand_ids = [t.id for t in sim_hand]
        
        # コンテキストを作成できない場合は簡易計算
        # 実際には向聴数と有効牌枚数（TileEfficiencyEngine内ロジック相当）を返す
        from mahjong.shanten import Shanten
        shanten_obj = Shanten()
        
        # 34形式変換
        tiles_34 = [0] * 34
        for t_id in hand_ids:
            idx = self._tile_to_idx(t_id)
            tiles_34[idx] += 1
            
        current_shanten = shanten_obj.calculate_shanten(tiles_34)
        
        # シミュレーション用ダミー。本来は `UkeireCalculator` を利用して残り枚数分を足す
        ukeire_count = 10.0 if current_shanten >= 1 else 5.0
        
        # 向聴進行度（近いほど1に近づく）
        progress = 1.0 / (current_shanten + 1.5)
        
        return {
            'effective_ukeire': ukeire_count,
            'shanten_progress': progress,
            'shanten': current_shanten
        }
        
    def _tile_to_idx(self, tile_id: str) -> int:
        suit = tile_id[-1]
        if suit == 'z':
            return 27 + int(tile_id[0]) - 1
        suit_idx = {'m': 0, 'p': 1, 's': 2}[suit]
        num = int(tile_id[1]) if 'r' in tile_id else int(tile_id[0])
        return suit_idx * 9 + (num - 1)
