from typing import Dict
from dataclasses import dataclass

@dataclass
class CPUStyleProfile:
    name: str
    risk_tolerance: float  # 0.0 (defensive) ~ 1.0 (aggressive)
    call_frequency: float  # 0.0 ~ 1.0
    yaku_obsession: float  # 0.0 ~ 1.0
    hesitation_factor: float # Multiplier for delay intervals

PROFILES = {
    "Aggressive": CPUStyleProfile("Aggressive", 0.85, 0.6, 0.2, 0.5), # Fast, cuts dangerous tiles
    "Defensive":  CPUStyleProfile("Defensive", 0.15, 0.2, 0.4, 1.8), # Slow on dangerous tiles, folds early
    "Balanced":   CPUStyleProfile("Balanced", 0.50, 0.4, 0.5, 1.0),
    "YakuSeeker": CPUStyleProfile("YakuSeeker", 0.65, 0.8, 0.9, 1.2)
}

def analyze_player_trend(past_5_games: list) -> CPUStyleProfile:
    """Analyze recent games to pick an opposite or matching tactical profile"""
    if not past_5_games:
        return PROFILES["Balanced"]
        
    avg_call = sum(g.get("calls", 0) for g in past_5_games) / max(len(past_5_games), 1)
    avg_deal_in = sum(g.get("deal_in_rate", 0) for g in past_5_games) / max(len(past_5_games), 1)
    
    if avg_deal_in > 0.15:
        # Player is aggressively dealing in, CPU should wait them out defensively
        return PROFILES["Defensive"]
    elif avg_call > 3:
        # Player calls a lot, CPU tries to push high values
        return PROFILES["YakuSeeker"]
    else:
        # Default tension
        return PROFILES["Aggressive"]
