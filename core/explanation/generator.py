# core/explanation/generator.py
from typing import Dict, List
from .models import CompleteExplanation, NaturalSummary, TechnicalFactor, StrategicFactor
from .technical import TechnicalAnalyzer
from .strategic import StrategicAnalyzer

class ExplanationGenerator:
    def __init__(self):
        self.tech_analyzer = TechnicalAnalyzer()
        self.strat_analyzer = StrategicAnalyzer()

    def generate(
        self, 
        recommended_move: str, 
        state: Dict, 
        ai_metadata: Dict
    ) -> CompleteExplanation:
        # 1. 技術的要因抽出
        hand_before = state.get("hand_before", [])
        hand_after = state.get("hand_after", [])
        tech_factors = self.tech_analyzer.analyze(hand_before, hand_after, recommended_move)

        # 2. 戦略的要因抽出
        context = state.get("context", {})
        strat_factors = self.strat_analyzer.analyze(context)

        # 3. 自然言語要約生成（段階的・包括的）
        summary = self._synthesize_natural(tech_factors, strat_factors, recommended_move)

        # 4. 付加情報
        confidence = ai_metadata.get("confidence", 0.7)
        alternatives = ai_metadata.get("alternatives", [])

        return CompleteExplanation(
            recommended_move=recommended_move,
            technical_factors=tech_factors,
            strategic_factors=strat_factors,
            summary=summary,
            confidence_score=confidence,
            alternative_moves=alternatives
        )

    def _synthesize_natural(self, tech: List[TechnicalFactor], strat: List[StrategicFactor], move: str) -> NaturalSummary:
        tech_labels = [f.label for f in tech] if tech else ["手牌進行"]
        strat_labels = [f.label for f in strat] if strat else ["通常進行"]

        # 一行要約：技術×戦略の組み合わせ
        one_liner = f"{move}切り：{tech_labels[0]}＋{strat_labels[0]}"

        # 詳細段落：論理的展開構成
        sentences = [f"{move}を推奨します。"]
        if tech:
            sentences.append(f"技術的には{tech_labels[0]}により手牌が前進します。")
            if any(f.code == "shanten_down" for f in tech):
                sentences.append("向聴数が減少し、あがりに直結する形を構築可能です。")
        if strat:
            top_strat = strat[0]
            sentences.append(f"局面判断として「{top_strat.context}」を考慮し、{top_strat.label}を優先しました。")
        sentences.append("総合的な期待値・安全度・進行速度をバランスさせた最適手です。")
        
        full_paragraph = "".join(sentences)

        return NaturalSummary(one_liner=one_liner, full_paragraph=full_paragraph)
