# core/review/analyzer.py
import json
from pathlib import Path
from typing import Dict, List, Optional
from core.explanation.generator import ExplanationGenerator
from core.inference.registry import EngineRegistry

class ReviewAnalyzer:
    def __init__(self, registry: EngineRegistry, explainer: ExplanationGenerator):
        self.registry = registry
        self.explainer = explainer
        self.cache_dir = Path("./kifu_analysis")
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_path(self, game_id: str) -> Path:
        return self.cache_dir / f"{game_id}_review.json"

    async def analyze_kifu(self, game_id: str, force: bool = False) -> Dict:
        cache = self.get_cache_path(game_id)
        if cache.exists() and not force:
            return json.loads(cache.read_text(encoding="utf-8"))

        kifu_path = Path(f"./kifu_data/{game_id}.json")
        if not kifu_path.exists():
            raise FileNotFoundError(f"Kifu not found: {game_id}")

        kifu = json.loads(kifu_path.read_text(encoding="utf-8"))
        timeline = []
        total_matches = 0
        critical_turns = []

        for i, move in enumerate(kifu.get("moves", [])):
            state = move.get("state")
            if not state: continue  # スナップショットなしはスキップ

            # AI推論（前処理済み推奨手があれば再利用）
            ai_rec = move.get("ai_suggestion")
            if not ai_rec:
                try:
                    adapter = self.registry.get_adapter("ensemble")
                    res = adapter.infer(state)
                    ai_rec = {"move": res["move"], "score": res["score"]}
                except Exception as e:
                    print(f"[Review Analysis Error] {e}")
                    ai_rec = {"move": "unknown", "score": 0.0}

            is_match = move["tile"] == ai_rec["move"]
            if is_match: total_matches += 1

            # 説明生成
            # state_snapshot は {"hand": [...], "river": [...], ...} 形式
            state_for_gen = {
                "hand_before": state["hand"],
                "hand_after": [t for t in state["hand"] if t != move["tile"]],
                "context": {
                    "round": state.get("round", "東1"), 
                    "turn": state.get("turn", i), 
                    "score_diff": 0, 
                    "is_dealer": False
                }
            }
            explanation = self.explainer.generate(ai_rec["move"], state_for_gen, {"confidence": ai_rec.get("score", ai_rec.get("confidence", 0.0))})

            # ユーザー打牌の簡易分析
            user_analysis = f"実戦打牌: {move['tile']}。"
            if not is_match:
                user_analysis += f" AI推奨: {ai_rec['move']}。速度・安全度・期待値のバランスが異なります。"

            entry = {
                "turn": i + 1,
                "round": state.get("round", "東1"),
                "user_move": move["tile"],
                "ai_move": ai_rec["move"],
                "is_match": is_match,
                "confidence": ai_rec.get("score", ai_rec.get("confidence", 0.0)),
                "explanation": explanation.model_dump(), # Pydantic v2 mode
                "user_move_analysis": user_analysis,
                "state_snapshot": state # 盤面再現用
            }
            timeline.append(entry)

            # 重要度判定（確信度高い＋不一致＝ミス候補）
            if not is_match and entry["confidence"] > 0.85:
                critical_turns.append(i + 1)

        total_turns = len(timeline)
        report = {
            "game_id": game_id,
            "summary": {
                "total_turns": total_turns,
                "match_count": total_matches,
                "match_rate": round(total_matches / max(total_turns, 1) * 100, 1),
                "critical_turns": critical_turns,
                "avg_confidence": round(sum(e["confidence"] for e in timeline) / max(total_turns, 1), 3) if total_turns > 0 else 0
            },
            "timeline": timeline
        }

        cache.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
