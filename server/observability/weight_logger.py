"""
重み決定プロセスの構造化ロギング
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class WeightDecisionLogger:
    """重み決定プロセスのJSONLロガー"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.log_path = os.path.join(log_dir, "weight_decisions.jsonl")
        os.makedirs(log_dir, exist_ok=True)

    def log_decision(
        self,
        context: Dict[str, Any],
        triggered_rules: List[str],
        raw_weights: Dict[str, float],
        adjusted_weights: Dict[str, float],
        selected_tile: str,
        reasoning: str = "",
    ):
        """重み決定の全プロセスを構造化ログ出力"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "triggered_rules": triggered_rules,
            "weights": {
                "raw": raw_weights,
                "adjusted": adjusted_weights,
            },
            "output": {
                "selected_tile": selected_tile,
                "reasoning": reasoning,
            },
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # ロギング失敗はサイレントに無視（ゲームを停止させない）

    def get_recent_decisions(self, count: int = 10) -> List[Dict]:
        """直近の決定ログを取得"""
        if not os.path.exists(self.log_path):
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [json.loads(line) for line in lines[-count:]]
        except Exception:
            return []
