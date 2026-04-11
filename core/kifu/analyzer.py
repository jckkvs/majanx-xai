# core/kifu/analyzer.py
import json
from pathlib import Path
from typing import Dict, List

class KifuAnalyzer:
    def __init__(self, kifu_dir: str = "./kifu_data"):
        self.kifu_dir = Path(kifu_dir)

    def load_all(self) -> List[Dict]:
        if not self.kifu_dir.exists(): return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in self.kifu_dir.glob("*.json")]

    def get_stats(self) -> Dict:
        kifu_list = self.load_all()
        if not kifu_list: return {"games_played": 0, "total_moves": 0, "ai_match_rate": 0.0}
        
        total_moves = sum(len(k["moves"]) for k in kifu_list)
        ai_matches = sum(
            1 for k in kifu_list for m in k["moves"]
            if m.get("ai_suggestion") and m["tile"] == m["ai_suggestion"].get("move")
        )
        return {
            "games_played": len(kifu_list),
            "total_moves": total_moves,
            "ai_match_rate": round(ai_matches / max(total_moves, 1) * 100, 1),
            "avg_moves_per_game": round(total_moves / len(kifu_list), 1)
        }
