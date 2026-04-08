from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ObservedData:
    n: int
    success_rate: float

@dataclass
class ShrunkEstimate:
    mean: float
    variance: float
    shrinkage_factor: float

@dataclass
class PosteriorDistribution:
    mean: float
    variance: float

class HierarchicalBayesPooler:
    """
    階層ベイズによる情報プールのスタブ実装
    stan や PyMC3などのMCMCライブラリが利用可能な本番環境ではそれに差し替えられる
    """
    def __init__(self, hierarchy_config: Dict, mcmc_samples: int = 2000):
        self.hierarchy = hierarchy_config
        self.mcmc_samples = mcmc_samples
        self.posterior_cache: Dict[str, PosteriorDistribution] = {}
        
    def _min_sample_for_level(self, level: str) -> int:
        levels = {
            "L1": 500000,
            "L2": 100000,
            "L3": 50000,
            "L4": 10000
        }
        return levels.get(level, 50000)
        
    def _get_hierarchy_level(self, pattern_id: str) -> str:
        # ダミー判定
        if "L1" in pattern_id: return "L1"
        if "L2" in pattern_id: return "L2"
        return "L3"
        
    def _get_hierarchy_prior(self, pattern_id: str) -> PosteriorDistribution:
        return PosteriorDistribution(mean=0.1, variance=0.01)
        
    def _bayes_update(self, prior: PosteriorDistribution, raw_obs: ObservedData) -> PosteriorDistribution:
        return PosteriorDistribution(mean=(prior.mean + raw_obs.success_rate)/2, variance=prior.variance)
        
    def get_shrunk_estimate(self, pattern_id: str, raw_obs: ObservedData) -> ShrunkEstimate:
        level = self._get_hierarchy_level(pattern_id)
        min_samp = self._min_sample_for_level(level)
        
        if raw_obs.n >= min_samp:
            return ShrunkEstimate(
                mean=raw_obs.success_rate,
                variance=raw_obs.success_rate * (1 - raw_obs.success_rate) / max(raw_obs.n, 1),
                shrinkage_factor=0.1
            )
        else:
            prior = self._get_hierarchy_prior(pattern_id)
            posterior = self._bayes_update(prior, raw_obs)
            shrinkage = 1.0 - (raw_obs.n / min_samp)
            
            return ShrunkEstimate(
                mean=posterior.mean,
                variance=posterior.variance,
                shrinkage_factor=shrinkage
            )
