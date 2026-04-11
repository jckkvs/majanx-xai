# server/ai/cpu_pacing.py
import random
from dataclasses import dataclass
from server.ai.cpu_style_profiles import CPUStyleProfile, PROFILES

@dataclass
class CPUAction:
    tile: str
    delay_ms: int
    is_suboptimal: bool

class CPUPacingEngine:
    def __init__(self, difficulty: str = "standard", style: CPUStyleProfile = None):
        self.cfg = {
            "easy":     {"base": 1100, "jitter": 350, "hesitation": 0.28, "suboptimal_rate": 0.18},
            "standard": {"base": 850,  "jitter": 250, "hesitation": 0.14, "suboptimal_rate": 0.06},
            "hard":     {"base": 600,  "jitter": 150, "hesitation": 0.06, "suboptimal_rate": 0.02}
        }[difficulty]
        self.style = style or PROFILES["Balanced"]

    def resolve(self, candidates: List[Dict[str, Any]], ctx: Dict[str, Any]) -> CPUAction:
        if not candidates:
            return CPUAction(tile="unknown", delay_ms=500, is_suboptimal=False)

        raw_delay = self.cfg["base"] + random.uniform(-self.cfg["jitter"], self.cfg["jitter"])
        delay = max(400, min(2200, raw_delay))

        is_risky = any(c.get("risk_score", 0.0) > (1.0 - self.style.risk_tolerance) for c in candidates)
        
        # Hesitation factor is scaled by the AI persona profile
        if (ctx.get("opponent_riichi", False) or ctx.get("turn", 0) >= 10) and is_risky:
            hesitation_prob = self.cfg["hesitation"] * self.style.hesitation_factor
            if random.random() < hesitation_prob:
                delay += random.uniform(250, 600) * self.style.hesitation_factor

        selected = candidates[0]
        is_suboptimal = False

        if len(candidates) > 1 and random.random() < self.cfg["suboptimal_rate"]:
            selected = candidates[1]
            is_suboptimal = True
            delay = max(400, int(delay * 0.85))

        return CPUAction(tile=selected["tile"], delay_ms=int(delay), is_suboptimal=is_suboptimal)
