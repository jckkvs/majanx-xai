import numpy as np
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime

class PatternCatalog:
    # TODO: 実装時にパターンJSON（catalog_v2.jsonなど）をロードして部分一致検索を行うクラス
    # 現在は単純なダミー参照としている
    def match_sequence(self, discard_seq) -> List[float]:
        return [1.0] * len(discard_seq)
        
    def get_top_contributors(self, discard_seq) -> List[str]:
        return ["EARLY_MIDDLE_CUT_RIICHI_CONSEC"]

PATTERN_CATALOG = PatternCatalog()

@dataclass
class TenpaiEstimate:
    probability: float
    confidence_interval: tuple[float, float]
    dominant_patterns: List[str]
    update_timestamp: datetime

def likelihood_tenpai_given_discards(
    discard_seq: List[Any],
    turn: int,
    is_dealer: bool,
    point_gap: float
) -> float:
    # 事前計算済みパターンテーブル参照
    pattern_score = PATTERN_CATALOG.match_sequence(discard_seq)
    
    # 時系列減衰: 古い打牌ほど重みを指数関数的に減衰
    time_weights = np.exp(-0.3 * np.arange(len(discard_seq))[::-1])
    weighted_score = np.sum([s*w for s,w in zip(pattern_score, time_weights)])
    
    # 場況補正
    dealer_bonus = 1.12 if is_dealer else 1.0
    pressure_factor = 1.0 + min(0.4, abs(point_gap) / 8000 * 0.3)
    
    return float(np.clip(weighted_score * dealer_bonus * pressure_factor, 0.01, 2.5))

def compute_posterior_tenpai_prob(
    prior: float,
    likelihood: float,
    evidence_weight: float,
    discard_seq: List[Any]
) -> TenpaiEstimate:
    # 証拠の重み付け（観測ノイズを考慮）
    effective_likelihood = prior * (likelihood ** evidence_weight)
    
    # 正規化（P(Evidence)の近似）
    marginal = effective_likelihood + (1 - prior) * 0.15  # 非テンパイ時の尤度近似
    
    prob = float(np.clip(effective_likelihood / marginal, 0.01, 0.99))
    
    # 信頼区間（簡易ブートストラップ近似）
    ci_low = prob * 0.85
    ci_high = min(0.99, prob * 1.12)
    
    return TenpaiEstimate(
        probability=prob,
        confidence_interval=(ci_low, ci_high),
        dominant_patterns=PATTERN_CATALOG.get_top_contributors(discard_seq),
        update_timestamp=datetime.now()
    )
