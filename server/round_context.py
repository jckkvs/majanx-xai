from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from server.models import GameState

@dataclass
class MatchConfig:
    bakaze: str = "east"
    kyoku: int = 1
    honba: int = 0
    kyotaku: int = 0
    uma: List[int] = field(default_factory=lambda: [20, 10, 0, -20])
    box_threshold: float = 20000.0
    avoid_last_weight: float = 0.5
    
    @property
    def is_all_last(self) -> bool:
        return self.bakaze == "south" and self.kyoku == 4

@dataclass
class RoundContext:
    bakaze: str
    kyoku: int
    is_all_last: bool
    rank: int
    score_gap_to_3rd: float
    box_risk: float
    urgency_index: float
    push_fold_threshold: float
    danger_tolerance: float = 1.0

    @classmethod
    def build(cls, gs: GameState, cfg: MatchConfig) -> "RoundContext":
        bakaze = cfg.bakaze
        kyoku = cfg.kyoku
        is_all = cfg.is_all_last
        
        scores = sorted([p.score for p in gs.players], reverse=True)
        self_score = gs.players[gs.current_player].score
        rank = 4 - sum(1 for s in scores if s > self_score)
        
        gap3 = self_score - scores[2] if rank >= 3 else 0.0
        box_risk = 1.0 if self_score <= cfg.box_threshold else 0.0
        
        avoid_w = cfg.avoid_last_weight
        # urgency: ラス回避重視とトップとの点差で補正（簡易近似）
        urgency = avoid_w * max(0.0, min(1.0, (3000 - gap3) / 3000)) + (1 - avoid_w) * 0.3
        
        if is_all and rank == 4:
            urgency = 1.0
            
        pft = 1500 * (1 - urgency) + 3000 * urgency
        
        return cls(bakaze, kyoku, is_all, rank, gap3, box_risk, urgency, pft)

