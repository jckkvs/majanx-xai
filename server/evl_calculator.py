"""
順位点EVと放銃リスクの統合計算モジュール
"""
from dataclasses import dataclass
from typing import Tuple, Any

@dataclass
class EVResult:
    absolute_ev: float
    normalized_score: float

class EVLCalculator:
    """EV（期待値）の計算と押し引き閾値の決定"""
    
    def calculate_current_ev(self, gs: Any) -> EVResult:
        """現在の順位や点差に基づくEVスコア(状況スコア用)"""
        # 1位なら状況スコア高め（守る価値が高い）、ラスなら低め（攻めなきゃいけない）など
        current_player = gs.players[gs.current_player]
        scores = [p.score for p in gs.players]
        ordered_scores = sorted(scores, reverse=True)
        rank = ordered_scores.index(current_player.score) + 1
        
        # 簡易正規化 (トップ=1.0, ラス=0.2)
        norm_score = 1.0 - (rank - 1) * 0.25
        return EVResult(absolute_ev=current_player.score, normalized_score=norm_score)

    def calculate_push_fold_threshold(self, gs: Any) -> Tuple[str, float]:
        """
        攻め(ATTACK)か守り(DEFEND)かの閾値とEVを計算
        """
        current_player = gs.players[gs.current_player]
        scores = [p.score for p in gs.players]
        ordered_scores = sorted(scores, reverse=True)
        rank = ordered_scores.index(current_player.score) + 1
        
        is_top = rank == 1
        is_last = rank == 4
        
        # ダミーの勝率と放銃率
        est_agari_prob = 0.2
        est_deal_in_prob = 0.15
        
        win_ev = 4000
        deal_in_ev = -8000 if gs.dealer != gs.current_player else -4000
        
        expected_value = (est_agari_prob * win_ev) - (est_deal_in_prob * abs(deal_in_ev))
        
        # トップ目で親のリーチがあれば守備
        dealer_riichi = gs.players[gs.dealer].is_riichi if gs.dealer != gs.current_player else False
        
        if is_top and dealer_riichi:
            return "DEFEND", expected_value
            
        if is_last and gs.round_number >= 3:
            return "ATTACK", expected_value
            
        if expected_value < 0:
            return "DEFEND", expected_value
            
        return "BALANCE", expected_value
