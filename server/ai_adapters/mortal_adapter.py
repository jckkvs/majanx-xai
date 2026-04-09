"""
server/ai_adapters/mortal_adapter.py
Mortal風の速度・牌効率特化ダミーAIアダプター
"""
from __future__ import annotations

import logging
import random
from typing import List, Optional

from .base import BaseAIAdapter, AIRecommendation, MJAIAction

logger = logging.getLogger(__name__)

class MortalAdapter(BaseAIAdapter):
    """
    速度特化型の推奨手を返すモックアダプター（Mortalの代役）。
    """
    async def connect(self) -> bool:
        return True
        
    async def send_observation(self, mjai_events: List[dict]) -> None:
        pass
        
    async def request_action(self, legal_actions: List[MJAIAction]) -> Optional[AIRecommendation]:
        if not legal_actions:
            return None
            
        # 簡易的に最初の打牌手を選ぶ
        fallback_action = legal_actions[0]
        for a in legal_actions:
            if a.type == "dahai":
                fallback_action = a
                break

        return AIRecommendation(
            ai_name="Mortal",
            recommended_action=fallback_action,
            confidence=0.85,
            reasoning="有効牌最大化のため、不要な孤立牌を処理します。",
            raw_output={
                "checklist": ["受入枚数最大化", "シャンテン数前進優先", "孤立牌の早期処理"],
                "quantitative_data": {
                    "dataset": "Mortal_NKY_2023",
                    "period": "2023",
                    "sample_size": "n=10000",
                    "confidence_interval_95": "TBD",
                    "methodology": "Mortalシミュレーション"
                }
            }
        )

    async def disconnect(self) -> None:
        pass
