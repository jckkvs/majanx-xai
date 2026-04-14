# server/tactics/riichi_judge.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class RiichiDecision:
    should_riichi: bool
    confidence: float
    expected_gain: float
    reason: str

class RiichiJudge:
    """リーチ/ダマ選択判断"""
    
    RIICHI_BONUS_MULT = 1.35      # リーチによる和了確率上昇係数
    DAMA_WAIT_PENALTY = 0.15      # ダマ待ちの隠蔽効果減衰
    DEAL_IN_RISK_PENALTY = 0.25   # リーチ後の放銃ペナルティ
    
    @classmethod
    def judge(
        cls,
        hand: List[str],
        win_prob_dama: float,
        deal_in_prob: float,
        avg_hand_value: float,
        riichi_opponents: int,
        turn: int,
        is_dealer: bool
    ) -> RiichiDecision:
        # リーチ期待値
        win_prob_riichi = min(0.85, win_prob_dama * cls.RIICHI_BONUS_MULT)
        ev_riichi = (win_prob_riichi * (avg_hand_value + 1000)) - \
                    ((deal_in_prob + cls.DEAL_IN_RISK_PENALTY) * 8000)
                    
        # ダマ期待値
        ev_dama = (win_prob_dama * avg_hand_value * (1 - cls.DAMA_WAIT_PENALTY)) - \
                  (deal_in_prob * 6000)
                  
        gain = ev_riichi - ev_dama
        
        # 判定ロジック
        if turn >= 12 and deal_in_prob > 0.25:
            return RiichiDecision(False, 0.8, gain, "終盤高リスク・ダマ維持")
        if riichi_opponents >= 2 and win_prob_dama < 0.15:
            return RiichiDecision(False, 0.75, gain, "複数リーチ・低確率")
        if gain > 800:
            return RiichiDecision(True, min(0.95, win_prob_riichi), gain, "打点上昇・牽制効果")
        if gain > 0:
            return RiichiDecision(True, 0.6, gain, "微増・状況次第")
        return RiichiDecision(False, 0.7, gain, "ダマ優位")
