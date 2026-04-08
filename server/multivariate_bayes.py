import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple
from server.round_context import RoundContext

@dataclass
class EstimateResult:
    probability: float
    ci: Tuple[float, float]
    top_contributors: List[str]

class PriorDB:
    # TODO: データベース等からの事前分布ロード
    def get(self, ctx: RoundContext) -> float:
        return 0.1  # ダミー

def compute_multivariate_likelihood(
    features: Dict[str, float],
    weights: Dict[str, float],
    corr_matrix: np.ndarray,
    feature_names: List[str]
) -> float:
    log_lik = 0.0
    for i, (name, w) in enumerate(weights.items()):
        feat_val = features.get(name, 0.5)
        # 相関補正
        corr_penalty = sum(abs(corr_matrix[i, j]) for j in range(len(feature_names)) if i != j)
        w_adj = w / (1.0 + corr_penalty * 0.5)
        # 対数尤度加算
        log_lik += w_adj * np.log(feat_val + 1e-9)
    return float(np.exp(np.clip(log_lik, -10.0, 10.0)))

class MultivariateBayesianEstimator:
    def __init__(self, prior_db: PriorDB, corr_matrix: np.ndarray):
        self.prior_db = prior_db
        self.corr_matrix = corr_matrix
        self.feature_weights = self._load_weights()
        
    def _load_weights(self) -> Dict[str, float]:
        # TODO: 実パラメータロード
        return {"feat1": 0.3, "feat2": 0.7}
        
    def estimate(self, features: Dict[str, float], ctx: RoundContext) -> EstimateResult:
        prior = self.prior_db.get(ctx)
        
        feature_names = list(self.feature_weights.keys())
        
        # サイズ合わせ（ダミー実装用）
        size = len(feature_names)
        dummy_corr = np.eye(size) if self.corr_matrix.size != size * size else self.corr_matrix
        
        likelihood = compute_multivariate_likelihood(
            features, self.feature_weights, dummy_corr, feature_names
        )
        posterior = self._bayes_update(prior, likelihood)
        
        return EstimateResult(
            probability=posterior,
            ci=self._compute_ci(posterior, likelihood),
            top_contributors=self._rank_contributors(features, likelihood)
        )
        
    def _bayes_update(self, prior: float, likelihood: float) -> float:
        evidence = prior * likelihood + (1 - prior) * 0.1
        return float(np.clip((prior * likelihood) / (evidence + 1e-9), 0.01, 0.99))
        
    def _compute_ci(self, posterior: float, likelihood: float) -> Tuple[float, float]:
        return (posterior * 0.9, min(0.99, posterior * 1.1))
        
    def _rank_contributors(self, features: Dict[str, float], likelihood: float) -> List[str]:
        return ["feat1", "feat2"]
