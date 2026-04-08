"""
字牌の戦略的価値を評価するモジュール
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class HonorScore:
    """字牌評価スコア"""
    tile_id: str
    pair_value: float        # 対子価値
    pon_value: float         # 鳴き価値
    defensive_value: float   # 終盤安牌価値
    opportunity_cost: float  # 保持による機会損失
    total_score: float
    
    @property
    def keep_priority(self) -> float:
        """保持優先度（高いほど切るべきではない）"""
        return self.total_score

class HonorEvaluator:
    """字牌の戦略的価値を評価"""
    
    def evaluate(self, tile_id: str, count: int, context: 'HonorContext') -> HonorScore:
        """単一字牌の価値を評価"""
        # 対子価値（役牌・場風・自風は高評価）
        pair_value = self._calc_pair_value(tile_id, count, context)
        
        # 鳴き価値（中盤以前は高評価）
        pon_value = self._calc_pon_value(count, context.turn)
        
        # 防御価値（終盤・リーチ下で上昇）
        defensive_value = self._calc_defensive_value(tile_id, context)
        
        # 機会損失（手牌スペースを占有するコスト）
        opportunity_cost = 0.15 * count if context.turn <= 6 else 0.05 * count
        
        # 総合スコア
        total = pair_value + pon_value + defensive_value - opportunity_cost
        
        return HonorScore(
            tile_id=tile_id,
            pair_value=pair_value,
            pon_value=pon_value,
            defensive_value=defensive_value,
            opportunity_cost=opportunity_cost,
            total_score=max(0.0, total)
        )
    
    def _calc_pair_value(self, tile_id: str, count: int, context: 'HonorContext') -> float:
        """対子価値・基本価値の計算 (A-tier ルール準拠)"""
        if count == 0:
            return 0.0
            
        base = 0.2  # 客風牌1枚
        
        is_yakuhai = tile_id in ['5z', '6z', '7z']
        is_field = tile_id == f"{context.bakaze_val}z"
        is_self = tile_id == f"{context.jikaze_val}z"
        
        if is_field and is_self:
            base = 0.9  # 連風牌
        elif is_yakuhai:
            base = 0.8  # 三元牌
        elif is_field:
            base = 0.6  # 場風
        elif is_self:
            base = 0.55 # 自風
            
        if count >= 2:
            if base == 0.2:
                base = 0.5 # 客風牌の対子
            else:
                base *= 1.5 # 役牌などの対子は大きく価値上昇
                
        if count >= 3:
            base += 0.5
            
        return base
    
    def _calc_pon_value(self, count: int, turn: int) -> float:
        """鳴き価値の計算"""
        if count != 2:
            return 0.0
        
        # 序盤・中盤は鳴き価値高
        if turn <= 4:
            return 0.35
        elif turn <= 7:
            return 0.25
        elif turn <= 10:
            return 0.10
        return 0.0  # 終盤は鳴き価値ほぼゼロ
    
    def _calc_defensive_value(self, tile_id: str, context: 'HonorContext') -> float:
        """防御価値の計算"""
        if context.turn < 8:
            return 0.05  # 序盤は防御価値低
        
        # 終盤：客風牌は安牌として価値上昇
        is_guest_wind = tile_id in ['1z', '2z', '3z', '4z'] and \
                       tile_id not in [f"{context.bakaze_val}z", f"{context.jikaze_val}z"]
        
        if is_guest_wind:
            return 0.4 if context.turn >= 10 else 0.25
        
        # 三元牌・場風・自風は危険牌だが、安牌枯れ時の最終防衛線
        if context.riichi_count > 0 and context.safe_tiles_remaining <= 2:
            return 0.3
        
        return 0.1

@dataclass
class HonorContext:
    """字牌評価コンテキスト"""
    turn: int
    bakaze_val: Optional[int]
    jikaze_val: Optional[int]
    riichi_count: int
    safe_tiles_remaining: int
