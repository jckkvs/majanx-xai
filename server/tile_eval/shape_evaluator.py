"""
手牌形状の価値を評価するモジュール
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from .tile_analyzer import TileConnection, TileRelation

@dataclass(frozen=True)
class ShapeScore:
    """形状評価スコア"""
    tile_id: str
    base_value: float      # 基本価値（中張牌=1.0, 端牌=0.7, 字牌=0.5）
    shape_bonus: float     # 形状ボーナス（両面=+0.5, 嵌張=+0.2等）
    stability_factor: float # 安定度係数（0.0-1.0）
    evolution_potential: float  # 進化余地（手変わり可能性）
    total_score: float
    
    @property
    def discard_priority(self) -> float:
        """切り優先度（低いほど切るべき）"""
        return 1.0 / (self.total_score + 0.01)

class ShapeEvaluator:
    """手牌形状の価値を評価するクラス"""
    
    # 牌種別基本価値（孤立牌優先度ルール S-1 に準拠: 以下は孤立の場合の価値。低いほど先に切る）
    TILE_BASE_VALUES = {
        'guest_wind': 0.1,   # 客風牌
        'terminal': 0.3,     # 1, 9牌
        'field_wind': 0.4,   # 場風
        'self_wind': 0.5,    # 自風
        'yakuhai': 0.6,      # 三元牌
        'edge_middle': 0.7,  # 2, 8牌
        'middle': 0.9,       # 3-7牌
        'red5': 1.0,         # 赤5
        'dora': 1.3,
    }
    
    # 形状別ボーナス (S-2 に準拠)
    SHAPE_BONUSES = {
        TileRelation.RYANMEN: 0.9,
        TileRelation.COMPOUND: 0.85, # 4連形相当
        TileRelation.OVERLAP: 0.75,  # 中膨れ・リャンカン相当
        TileRelation.PAIR_CANDIDATE: 0.55,
        TileRelation.KANCHAN: 0.5,
        TileRelation.EDGE: 0.4,
        TileRelation.ISOLATED: 0.2,
    }
    
    def evaluate(self, connections: Dict[str, TileConnection], 
                 context: 'EvalContext') -> Dict[str, ShapeScore]:
        """各牌の形状価値を評価"""
        results = {}
        
        for tile_id, conn in connections.items():
            # 基本価値
            base = self._get_base_value(conn, context)
            
            # 形状ボーナス（最良の関係を採用）
            shape_bonus = max(
                (self.SHAPE_BONUSES.get(r, 0.0) for r in conn.relations),
                default=0.0
            )
            
            # 安定度係数
            stability = conn.shape_stability
            
            # 進化余地（孤立牌・カンチャンは手変わり余地大）
            evolution = self._calc_evolution_potential(conn, context.turn)
            
            # 総合スコア: shape_bonus 重視
            total = (base * 0.3 + shape_bonus * 1.5) * stability * (1.0 + evolution * 0.3)
            
            results[tile_id] = ShapeScore(
                tile_id=tile_id,
                base_value=base,
                shape_bonus=shape_bonus,
                stability_factor=stability,
                evolution_potential=evolution,
                total_score=total
            )
        
        return results
    
    def _get_base_value(self, conn: TileConnection, context: 'EvalContext') -> float:
        """牌の基本価値を取得"""
        # ドラ・赤ドラの優先
        if conn.is_red: return self.TILE_BASE_VALUES['red5']
        if context.is_dora(conn.tile_id): return self.TILE_BASE_VALUES['dora']
        
        # 字牌
        if conn.suit == 'z':
            if conn.number in [5, 6, 7]: return self.TILE_BASE_VALUES['yakuhai']
            if conn.number == context.jikaze_val: return self.TILE_BASE_VALUES['self_wind']
            if conn.number == context.bakaze_val: return self.TILE_BASE_VALUES['field_wind']
            return self.TILE_BASE_VALUES['guest_wind']
        
        # 数牌
        if conn.number in [1, 9]:
            return self.TILE_BASE_VALUES['terminal']
        if conn.number in [2, 8]:
            return self.TILE_BASE_VALUES['edge_middle']
        return self.TILE_BASE_VALUES['middle']
    
    def _calc_evolution_potential(self, conn: TileConnection, turn: int) -> float:
        """手変わり・形状進化の余地を評価"""
        if TileRelation.ISOLATED in conn.relations:
            # 孤立牌は中張なら進化余地大
            if conn.number and conn.number not in [1, 9]:
                return 0.4 if turn <= 6 else 0.2
            return 0.1
        elif TileRelation.KANCHAN in conn.relations:
            # 嵌張は両面への進化余地
            return 0.3 if turn <= 7 else 0.1
        elif TileRelation.RYANMEN in conn.relations:
            # 両面は既に最適、進化余地小
            return 0.05
        return 0.15

@dataclass
class EvalContext:
    """評価コンテキスト"""
    turn: int
    bakaze: str  # 'east', 'south'
    jikaze: str
    dora_indicators: List[str]
    
    @property
    def bakaze_val(self) -> Optional[int]:
        mapping = {'east': 1, 'south': 2, 'west': 3, 'north': 4}
        return mapping.get(self.bakaze)
    
    @property
    def jikaze_val(self) -> Optional[int]:
        mapping = {'east': 1, 'south': 2, 'west': 3, 'north': 4}
        return mapping.get(self.jikaze)
    
    def is_dora(self, tile_id: str) -> bool:
        """ドラ牌の判定"""
        if tile_id in self.dora_indicators:
            return True
        # 赤ドラ判定
        if 'r' in tile_id:
            return True
        return False
