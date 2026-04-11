import json
import os
from dataclasses import dataclass, asdict
from typing import Dict

@dataclass
class LocalRank:
    points: int = 1000
    division: str = "四段"
    games: int = 0
    avg_rank: float = 2.5

    def apply_result(self, rank: int):
        self.games += 1
        delta = {1: 20, 2: 5, 3: -10, 4: -25}.get(rank, 0)
        self.points += delta
        self.avg_rank = (self.avg_rank * (self.games - 1) + rank) / self.games
        self._update_division()

    def _update_division(self):
        thresholds = [(2000, "魂天"), (1700, "七段"), (1400, "六段"), 
                      (1100, "五段"), (800, "四段"), (500, "三段"), (0, "二段")]
        for pts, div in thresholds:
            if self.points >= pts:
                self.division = div
                break

class OfflineEngine:
    def __init__(self, path: str = "data/progress.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.data = self._load()
        self.rank = LocalRank(**self.data.get("rank", {}))
        self.cpu_diff = self._calc_difficulty()

    def _load(self) -> Dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {}

    def save(self):
        self.data["rank"] = asdict(self.rank)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def _calc_difficulty(self) -> str:
        if self.rank.points >= 1500: 
            return "hard"
        if self.rank.points >= 900: 
            return "standard"
        return "easy"

    def finish_round(self, player_rank: int) -> Dict:
        self.rank.apply_result(player_rank)
        self.save()
        self.cpu_diff = self._calc_difficulty()
        return {
            "rank": self.rank.division,
            "points": self.rank.points,
            "next_cpu_diff": self.cpu_diff,
            "avg_rank": round(self.rank.avg_rank, 2)
        }
