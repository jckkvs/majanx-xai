"""
server/ai_adapters/rulebase_adapter.py
定性推論ルールエンジン用アダプター（鳳凰位カタログ駆動）
"""
from __future__ import annotations

import logging
import json
import random
from typing import List, Optional
from pathlib import Path

from .base import BaseAIAdapter, AIRecommendation, MJAIAction

logger = logging.getLogger(__name__)

class RulebaseAdapter(BaseAIAdapter):
    """
    鳳凰位カタログ（phoenix_catalog.json）に基づく軽量AIアダプター。
    """
    def __init__(self, engine=None):
        self.engine = engine
        self.catalog = []
        self._load_catalog()
        
    def _load_catalog(self):
        catalog_path = Path(__file__).parent.parent / "rules" / "phoenix_catalog.json"
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.catalog = data.get("rules", [])
            logger.info(f"Loaded {len(self.catalog)} rules from phoenix_catalog.json")
        except Exception as e:
            logger.error(f"Failed to load phoenix_catalog.json: {e}")

    async def connect(self) -> bool:
        return True
        
    async def send_observation(self, mjai_events: List[dict]) -> None:
        pass
        
    async def request_action(self, legal_actions: List[MJAIAction]) -> Optional[AIRecommendation]:
        if not legal_actions:
            return None
            
        # 安全そうな牌（合法手の中から）を選ぶ
        fallback_action = legal_actions[0]
        for a in legal_actions:
            if a.type == "dahai":
                fallback_action = a
                # ランダムに選んで変化をつける（MVP用）
                if random.random() > 0.5:
                    break

        # カタログからランダムに1つのルールを引っ張ってきて、この局面の解釈として提示する
        # （本来は trigger_conditions を評価して抽出するがMVPのためモック稼働）
        if self.catalog:
            rule = random.choice(self.catalog)
            reasoning = rule.get("qualitative_logic", {}).get("principle", "打点重視")
            checklist = rule.get("qualitative_logic", {}).get("checklists", ["状況確認"])
            quant = rule.get("quantitative_schema")
        else:
            reasoning = "中盤は受け入れ枚数を広げて聴牌を早める"
            checklist = ["受入枚数最大化"]
            quant = {
                "dataset": "モックデータ",
                "period": "2023",
                "sample_size": "n=100",
                "confidence_interval_95": "TBD",
                "methodology": "モック"
            }

        return AIRecommendation(
            ai_name="Phoenix",
            recommended_action=fallback_action,
            confidence=None,
            reasoning=reasoning,
            raw_output={
                "checklist": checklist,
                "quantitative_data": quant
            }
        )

    async def disconnect(self) -> None:
        pass
