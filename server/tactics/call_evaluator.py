# server/tactics/call_evaluator.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass(frozen=True)
class CallDecision:
    should_call: bool
    call_type: Optional[str]  # "chi" | "pon" | "kan"
    score_delta: float
    speed_gain: int  # 向聴数前進量
    risk_increase: float

class CallEvaluator:
    """鳴き選択の期待値評価"""
    
    @classmethod
    def evaluate(
        cls,
        current_hand: List[str],
        call_target: str,
        call_type: str,
        current_shanten: int,
        current_value: float,
        current_risk: float,
        turn: int,
        riichi_count: int
    ) -> CallDecision:
        # 1. 鳴き後の仮手牌構築・評価
        post_hand = cls._apply_call(current_hand, call_target, call_type)
        post_shanten = cls._calc_shanten(post_hand)
        post_value = cls._estimate_value(post_hand)
        post_risk = cls._estimate_risk(post_hand, riichi_count, turn)
        
        speed_gain = current_shanten - post_shanten
        value_delta = post_value - current_value
        risk_delta = post_risk - current_risk
        
        # 2. 総合スコア計算
        # 速度重視係数 (序盤は高、終盤は低)
        speed_weight = max(0.2, 1.0 - (turn / 20.0))
        score = (speed_gain * 3.0 * speed_weight) + \
                (value_delta / 2000.0) - \
                (risk_delta * 2.0)
                
        # 3. 閾値判定
        should_call = score > 0.5 and (post_shanten < current_shanten or value_delta > 1000)
        
        # カン判断の厳格化
        if call_type == "kan":
            if risk_delta > 0.4 or riichi_count > 0:
                should_call = False
                
        return CallDecision(
            should_call=should_call,
            call_type=call_type if should_call else None,
            score_delta=value_delta,
            speed_gain=max(0, speed_gain),
            risk_increase=max(0.0, risk_delta)
        )
        
    @classmethod
    def _apply_call(cls, hand: List[str], target: str, call_type: str) -> List[str]:
        # 実装時は牌構成から公開部分を除去し、固定面子として追加
        return hand  # モック実装
        
    @classmethod
    def _calc_shanten(cls, hand: List[str]) -> int:
        # 既存 calculate_shanten() を呼び出し
        return 0
        
    @classmethod
    def _estimate_value(cls, hand: List[str]) -> float:
        # 既存打点推定モジュール呼び出し
        return 2000.0
        
    @classmethod
    def _estimate_risk(cls, hand: List[str], riichi_count: int, turn: int) -> float:
        from server.tile_eval.risk_estimator import RiskEstimator
        # RiskEstimator などの既存モジュールを利用
        return 0.2
