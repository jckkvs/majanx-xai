"""
server/orchestrator.py
3方向性統合オーケストレーター
"""
from __future__ import annotations
import asyncio
import time
import logging
from typing import Dict, Any
from dataclasses import dataclass

from server.engines.xai_analyzer import XAIAnalyzer
from server.engines.strategy_judge import StrategyJudge
from server.engines.mortal_interpreter import MortalInterpreter

logger = logging.getLogger(__name__)

@dataclass
class TriplePayload:
    xai: Dict[str, Any]
    strategy: Dict[str, Any]
    interpret: Dict[str, Any]
    meta: Dict[str, Any]

class Orchestrator:
    def __init__(self, xai: XAIAnalyzer, strat: StrategyJudge, interp: MortalInterpreter):
        self.xai = xai
        self.strat = strat
        self.interp = interp

    async def run(self, features: Any, ai_idx: int, ai_prob: float, ai_tile: str, ctx: Dict, model: Any = None) -> TriplePayload:
        start = time.perf_counter()
        
        # 並列実行
        t1 = asyncio.to_thread(self.xai.analyze, features, ai_idx, ai_prob, model)
        t2 = asyncio.to_thread(self.strat.judge, ctx)
        t3 = asyncio.to_thread(self.interp.interpret, ai_tile, ai_prob, ctx)
        
        r1, r2, r3 = await asyncio.gather(t1, t2, t3)
        lat = (time.perf_counter() - start) * 1000
        
        # 整合性判定
        tiles = {r1.tile, r2.tile, r3.tile}
        cons = "一致" if len(tiles) == 1 else "分岐"
        note = f"推奨一致:{len(tiles)}/3 | 遅延:{lat:.1f}ms"
        
        return TriplePayload(
            xai={"tile": r1.tile, "reasoning": r1.reasoning, "scores": r1.scores, "keywords": r1.keywords},
            strategy={"tile": r2.tile, "judgment": r2.judgment, "type": r2.strategy_type, "scores": r2.scores, "rules": r2.triggered_rules},
            interpret={"tile": r3.tile, "text": r3.text, "confidence": r3.confidence, "intents": r3.intents, "rules": r3.matched_rules},
            meta={"consistency": cons, "note": note, "latency_ms": round(lat, 1)}
        )
