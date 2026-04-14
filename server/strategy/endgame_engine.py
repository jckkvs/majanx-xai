# server/strategy/endgame_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Literal

@dataclass(frozen=True)
class EndgameStrategy:
    tile_selection: Literal["speed", "value_max", "balanced", "safest", "aggressive"]
    risk_tolerance: float  # 0.0(完全回避) 〜 1.0(高リスク許容)

class EndgameStrategyEngine:
    """局面コンテキストに応じた戦略優先度決定"""
    
    BASE_MAP = {
        (1, "ahead"): ("safest", 0.15),
        (1, "neutral"): ("balanced", 0.35),
        (1, "behind"): ("value_max", 0.45),
        (2, "ahead"): ("balanced", 0.30),
        (2, "neutral"): ("balanced", 0.40),
        (2, "behind"): ("speed", 0.50),
        (3, "any"): ("aggressive", 0.60),
        (4, "any"): ("value_max", 0.70),
    }
    
    @classmethod
    def decide(cls, rank: int, score_diff: int, honba: int, 
               is_all_last: bool, is_dealer: bool, current_seat: int) -> EndgameStrategy:
        """
        終盤戦略決定
        
        Args:
            rank: 現在順位 (1-4)
            score_diff: 点差 (正: リード, 負: ビハインド)
            honba: 本場数
            is_all_last: オーラスフラグ
            is_dealer: 親番フラグ
            current_seat: 自席ID
        """
        # 1. 状態分類
        if score_diff > 2000:
            state = "ahead"
        elif score_diff < -2000:
            state = "behind"
        else:
            state = "neutral"
            
        key = (rank, state) if state != "any" else (rank, "any")
        tag, risk_tol = cls.BASE_MAP.get(key, cls.BASE_MAP[(2, "neutral")])
        
        # 2. オーラス補正
        if is_all_last:
            if rank == 1:
                risk_tol *= 0.6
            elif rank in [3, 4]:
                risk_tol = min(1.0, risk_tol * 1.3)
                tag = "aggressive" if rank == 4 else tag
                
        # 3. 本場数・親番維持補正
        if is_dealer and current_seat == current_seat:  # 親番維持意図
            risk_tol *= (1 + honba * 0.04)
            
        # 4. 正規化
        risk_tol = max(0.0, min(1.0, risk_tol))
        
        return EndgameStrategy(tag, risk_tol)
