# core/kifu/logger.py
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

class KifuLogger:
    def __init__(self, save_dir: str = "./kifu_data"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        self.current_game_id: Optional[str] = None
        self.moves: List[Dict] = []

    def start_game(self, room_id: str):
        self.current_game_id = f"{room_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.moves = []

    def log_move(self, seat: int, tile: str, state_snapshot: Optional[Dict] = None, ai_suggestion: Optional[Dict] = None):
        self.moves.append({
            "timestamp": datetime.now().isoformat(),
            "seat": seat,
            "tile": tile,
            "state": state_snapshot,  # 振り返り用状態スナップショット
            "ai_suggestion": ai_suggestion
        })

    def save(self):
        if not self.current_game_id or not self.moves: return
        filepath = self.save_dir / f"{self.current_game_id}.json"
        payload = {
            "id": self.current_game_id,
            "started_at": self.current_game_id.split("_")[1],
            "moves": self.moves
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return filepath
