# server/core/explanation/generator.py
from typing import List, Dict, Any, Optional
from .models import TechnicalFactor, StrategicFactor, NaturalSummary, CompleteExplanation
from .codes import REASON_CODES
import logging

logger = logging.getLogger(__name__)

class ExplanationGenerator:
    """統合階層的説明生成器"""

    def generate(self, state: Dict[str, Any], move: str, engine_metadata: Dict[str, Any]) -> CompleteExplanation:
        # 層1: 技術的要因抽出
        tech_factors = self._extract_technical_factors(state, move, engine_metadata)
        
        # 層2: 戦略的要因抽出
        strat_factors = self._extract_strategic_factors(state, move, engine_metadata)
        
        # 層3: 自然言語要約生成
        summary = self._generate_natural_summary(tech_factors, strat_factors, move)
        
        # 付加情報
        confidence = engine_metadata.get("integrated_confidence", 0.5)
        alternatives = engine_metadata.get("alternative_moves", [])
        
        return CompleteExplanation(
            recommended_move=move,
            technical_factors=tech_factors,
            strategic_factors=strat_factors,
            summary=summary,
            confidence_score=confidence,
            alternative_moves=alternatives
        )

    def _extract_technical_factors(self, state: Dict[str, Any], move: str, meta: Dict[str, Any]) -> List[TechnicalFactor]:
        factors = []
        
        # 1. 向聴数/受入 (Engine metadata より)
        shanten = meta.get("shanten", 6)
        ukeire = meta.get("ukeire", 0)
        
        if shanten < 5:
            factors.append(TechnicalFactor(
                code="shanten_down",
                label=REASON_CODES["shanten_down"]["label"],
                value=float(shanten),
                detail=f"現在{shanten}向聴 / 受入{ukeire}枚"
            ))

        # 2. 安全度
        # river_danger_map などから対象牌の危険度を抽出 (mock 簡易化)
        danger = 0.0
        if "river_danger" in state:
            # 探索ロジック (省略)
            pass
            
        if danger < 0.1:
            factors.append(TechnicalFactor(
                code="anzen",
                label=REASON_CODES["anzen"]["label"],
                value=1.0 - danger,
                detail="現物または強力な安牌"
            ))
            
        return factors

    def _extract_strategic_factors(self, state: Dict[str, Any], move: str, meta: Dict[str, Any]) -> List[StrategicFactor]:
        factors = []
        
        # パラダイム情報の統合
        paradigm = meta.get("paradigm", {})
        pid = paradigm.get("primary", "PAR_SPEED")
        
        if pid == "PAR_SPEED":
            factors.append(StrategicFactor(
                code="shanten_down",
                label="速度優先",
                context="他家の速度に対抗するため、手牌の進行を最優先",
                priority=0.9
            ))
        elif pid == "PAR_DEF":
             factors.append(StrategicFactor(
                code="betaori",
                label=REASON_CODES["betaori"]["label"],
                context="リーチ者への放銃を避ける守備局面",
                priority=0.95
            ))

        # 親番、点差などのコンテキスト
        is_dealer = state.get("is_dealer", False)
        if is_dealer:
            factors.append(StrategicFactor(
                code="oya_attack",
                label=REASON_CODES["oya_attack"]["label"],
                context="親番維持のため攻撃的な打牌を選択",
                priority=0.85
            ))
            
        return sorted(factors, key=lambda x: x.priority, reverse=True)

    def _generate_natural_summary(self, tech: List[TechnicalFactor], strat: List[StrategicFactor], move: str) -> NaturalSummary:
        # One-liner
        top_tech = tech[0].label if tech else "手牌効率"
        top_strat = strat[0].label if strat else "局面判断"
        one_liner = f"{move}切り：{top_tech}と{top_strat}の両立"
        
        # Full Paragraph
        sentences = [f"推奨される打牌は {move} です。"]
        
        if tech:
            tech_labels = "、".join([f.label for f in tech[:2]])
            sentences.append(f"技術的には{tech_labels}を重視しています。")
            
        if strat:
            strat_desc = strat[0].context
            sentences.append(f"現在の戦略：{strat_desc}。")
            
        sentences.append("総合的な確信度に基づき、この選択肢を推奨します。")
        
        return NaturalSummary(
            one_liner=one_liner,
            full_paragraph=" ".join(sentences)
        )
