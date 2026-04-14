# server/tactics/attack_fold_controller.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
import numpy as np

@dataclass(frozen=True)
class AttackFoldDecision:
    action: str  # "attack" | "fold" | "partial_fold"
    confidence: float
    ev_attack: float
    ev_fold: float
    reason: str

class AttackFoldController:
    """期待値比較に基づく攻守判断スイッチ"""
    
    # 定数は設定外部化推奨 (config/tactics.yaml)
    AVG_WIN_POINTS = 6000.0
    AVG_DEAL_IN_LOSS = 8000.0
    FOLD_EARTH_LOSS = 1500.0  # 折り返し時の平均順位損失換算
    
    @classmethod
    def decide(
        cls,
        win_prob: float,
        deal_in_prob: float,
        avg_hand_value: float,
        current_score_diff: int,
        rank: int,
        turn: int,
        is_riichi_opponent: bool
    ) -> AttackFoldDecision:
        """
        攻撃期待値 vs 折り返し期待値を比較
        
        EV_attack = P(win) * AvgWin - P(deal_in) * AvgLoss
        EV_fold = -RankPreservationLoss (順位維持コスト)
        """
        ev_attack = (win_prob * avg_hand_value) - (deal_in_prob * cls.AVG_DEAL_IN_LOSS)
        
        # 順位・点差に応じた折り返しコスト計算
        fold_penalty = cls._calc_fold_penalty(rank, current_score_diff, turn)
        ev_fold = -fold_penalty
        
        # 判定閾値
        margin = 500.0  # 安全マージン
        
        if ev_attack > ev_fold + margin:
            return AttackFoldDecision("attack", min(0.95, win_prob), ev_attack, ev_fold, "攻撃期待値優位")
        elif ev_attack < ev_fold - margin:
            return AttackFoldDecision("fold", min(0.95, deal_in_prob), ev_attack, ev_fold, "放銃リスク超過")
        else:
            return AttackFoldDecision("partial_fold", 0.6, ev_attack, ev_fold, "危険牌回避・安全牌進行")
            
    @classmethod
    def _calc_fold_penalty(cls, rank: int, score_diff: int, turn: int) -> float:
        """順位維持コストの経験則モデル"""
        base = cls.FOLD_EARTH_LOSS
        if rank == 1:
            return base * (1.5 + (score_diff / 10000.0))
        elif rank == 4:
            return base * 0.3  # 4位は折り返しコスト低
        else:
            return base * (1.0 + max(0, -score_diff / 8000.0))
