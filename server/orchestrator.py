"""
server/orchestrator.py
6方向性統合オーケストレーター（v3）

パイプライン:
  Step 0: パラダイムエンジン — 思考軸の決定
  Step 1: 読みエンジン先行実行 — danger_map を ctx に注入
  Step 2: 3エンジン並列実行 — XAI/戦略/解釈
  Step 3: 境界条件検出 — 盤面微差の判断反転
  Step 4: 4層出力フォーマッティング — 定性/チェック/定量/境界

出力:
  QuadPayload — 既存4エンジン出力 + 4層統合出力
"""
from __future__ import annotations
import asyncio
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from server.engines.xai_analyzer import XAIAnalyzer
from server.engines.strategy_judge import StrategyJudge
from server.engines.mortal_interpreter import MortalInterpreter
from server.engines.opponent_reader import OpponentReader
from server.engines.paradigm_engine import ParadigmEngine
from server.engines.boundary_detector import BoundaryDetector
from server.engines.output_formatter import OutputFormatter

logger = logging.getLogger(__name__)

@dataclass
class TriplePayload:
    xai: Dict[str, Any]
    strategy: Dict[str, Any]
    interpret: Dict[str, Any]
    reading: Dict[str, Any]
    four_layer: Dict[str, Any]   # 4層統合出力（新規）
    meta: Dict[str, Any]

class Orchestrator:
    def __init__(self, xai: XAIAnalyzer, strat: StrategyJudge,
                 interp: MortalInterpreter, reader: OpponentReader = None,
                 paradigm: ParadigmEngine = None,
                 boundary: BoundaryDetector = None,
                 formatter: OutputFormatter = None):
        self.xai = xai
        self.strat = strat
        self.interp = interp
        self.reader = reader or OpponentReader()
        self.paradigm = paradigm or ParadigmEngine()
        self.boundary = boundary or BoundaryDetector()
        self.formatter = formatter or OutputFormatter()

    async def run(self, features: Any, ai_idx: int, ai_prob: float,
                  ai_tile: str, ctx: Dict, model: Any = None) -> TriplePayload:
        start = time.perf_counter()

        # ═══ Step 0: パラダイムエンジン — 思考軸決定 ═══
        paradigm_result = self.paradigm.determine(ctx)
        ctx["_paradigm"] = paradigm_result.name_ja
        ctx["_paradigm_id"] = paradigm_result.primary

        # ═══ Step 1: 読みエンジン先行実行 → danger_map を ctx に注入 ═══
        gs = ctx.get("_gs")
        seat = ctx.get("_seat", 0)
        reading_result = None

        if gs:
            reading_result = await asyncio.to_thread(self.reader.read, gs, seat)
            ctx["reading_danger_map"] = reading_result.danger_map
            ctx["reading_override_flags"] = reading_result.override_flags

        # ═══ Step 2: 3エンジン並列実行 ═══
        t1 = asyncio.to_thread(self.xai.analyze, features, ai_idx, ai_prob, model)
        t2 = asyncio.to_thread(self.strat.judge, ctx)
        t3 = asyncio.to_thread(self.interp.interpret, ai_tile, ai_prob, ctx)

        r1, r2, r3 = await asyncio.gather(t1, t2, t3)
        lat_engines = (time.perf_counter() - start) * 1000

        # ═══ Step 3: 境界条件検出 ═══
        recommended_tile = r2.tile  # 戦略エンジンの推奨牌を基準に
        boundary_result = self.boundary.detect(
            ctx, recommended_tile, paradigm_result.primary
        )

        # ═══ Step 4: 4層出力フォーマッティング ═══
        four_layer = self.formatter.format(
            tile=recommended_tile,
            paradigm_result=paradigm_result,
            strategy_result=r2,
            reading_result=reading_result,
            boundary_result=boundary_result,
            ctx=ctx,
        )
        lat_total = (time.perf_counter() - start) * 1000

        # 整合性判定（推奨牌の一致度）
        tiles = {r1.tile, r2.tile, r3.tile}
        if len(tiles) == 1:
            consistency = "完全一致"
        elif len(tiles) == 2:
            consistency = "部分一致"
        else:
            consistency = "分岐"

        # 矛盾時の注記生成
        note = self._build_consistency_note(r1, r2, r3, tiles, consistency)

        # 統合confidence
        avg_conf = (
            r2.confidence * 0.35 +
            r3.confidence_score * 0.25 +
            (0.5 if r1.scores.get("attention", 0) > 0.3 else 0.3) * 0.20 +
            (reading_result.confidence if reading_result else 0.3) * 0.20
        )

        # 読み結果の構造化出力
        reading_out = reading_result.to_dict() if reading_result else {
            "reader_type": "opponent_read_v1",
            "rules": [],
            "wait_candidates": [],
            "confidence": 0.0,
        }

        return TriplePayload(
            xai={
                "tile": r1.tile,
                "reasoning": r1.reasoning,
                "scores": r1.scores,
                "keywords": r1.keywords
            },
            strategy={
                "tile": r2.tile,
                "judgment": r2.judgment,
                "type": r2.strategy_type,
                "scores": r2.scores,
                "rules": r2.triggered_rules,
                "han_evaluation": r2.han_evaluation,
                "reasoning": r2.reasoning,
                "confidence": r2.confidence,
                "tile_scores": r2.tile_scores,
            },
            interpret={
                "tile": r3.tile,
                "text": r3.text,
                "confidence": r3.confidence,
                "confidence_score": r3.confidence_score,
                "intents": r3.intents,
                "rules": r3.matched_rules,
                "category": r3.category,
                "han_context": r3.han_context
            },
            reading=reading_out,
            four_layer=four_layer.to_dict(),
            meta={
                "consistency": consistency,
                "note": note,
                "paradigm": paradigm_result.to_dict(),
                "latency_engines_ms": round(lat_engines, 1),
                "latency_total_ms": round(lat_total, 1),
                "integrated_confidence": round(avg_conf, 2)
            }
        )

    def _build_consistency_note(self, r1, r2, r3, tiles, consistency) -> str:
        """整合性の注記を生成"""
        parts = [f"推奨一致:{3 - len(tiles) + 1}/3"]

        if consistency == "完全一致":
            parts.append("3系統の出力が整合。AI確率分布・戦略判断・逆推論が一致。")
        elif consistency == "部分一致":
            parts.append(f"方向性2({r2.strategy_type})と方向性3({r3.category})の判断軸に差異あり。")
        else:
            parts.append(f"XAI:{r1.tile} / 戦略:{r2.tile}({r2.strategy_type}) / 解釈:{r3.tile}({','.join(r3.intents[:2])})")
            if r2.strategy_type == "DEFENSIVE_FOLD" and r3.category != "DEFENSE":
                parts.append("戦略エンジンは防御を推奨するが、解釈エンジンは攻めの意図を検出。巡目・手牌形状を要確認。")

        return " | ".join(parts)
