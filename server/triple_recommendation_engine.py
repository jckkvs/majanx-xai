"""
5-Pattern Recommendation Engine
1. XAI解析エンジン
2. 戦略判断ルールエンジン1（一般知識）
3. 戦略判断ルールエンジン2（牌譜分析）
4. OSS AI解釈エンジン1（ルールエンジン1で解釈）
5. OSS AI解釈エンジン2（ルールエンジン2で解釈）
"""

from typing import Dict, List
from server.mahjong_ai import LatestOSSMahjongAI
from server.rule_engine_1 import GeneralMahjongRuleEngine
from server.rule_engine_2 import HaihuRuleEngine

class FivePatternRecommendationEngine:
    """5パターン推奨手生成エンジン"""
    
    def __init__(self):
        self.ai_model = LatestOSSMahjongAI()
        self.rule_engine_1 = GeneralMahjongRuleEngine()
        self.rule_engine_2 = HaihuRuleEngine()
        
        # 牌譜ルールを読み込み
        self.rule_engine_2.load_haihu_files()
        try:
            self.rule_engine_2.generate_rules_from_patterns()
        except Exception as e:
            print(f"[Warning] Failed to generate haihu rules: {e}")
    
    async def generate_recommendations(
        self, 
        game_state: Dict, 
        hand_tiles: List[str]
    ) -> Dict:
        """
        5パターンの推奨手を生成
        
        Returns:
            5パターンの推奨結果
        """
        # OSS AIで予測
        ai_output = await self.ai_model.predict(game_state, hand_tiles)
        
        # ルールエンジン1（一般知識）
        rules_1 = self.rule_engine_1.evaluate(game_state, hand_tiles)
        
        # ルールエンジン2（牌譜分析）
        rules_2 = self.rule_engine_2.evaluate(game_state, hand_tiles)
        
        return {
            "type": "five_pattern_recommendation",
            "data": {
                "pattern_1": {
                    "name": " XAI解析",
                    "type": "xai_analysis",
                    "content": self._generate_xai_analysis(ai_output, hand_tiles)
                },
                "pattern_2": {
                    "name": "📚 定石ルール（一般知識）",
                    "type": "rule_engine_1",
                    "content": self._format_rules(rules_1, "general")
                },
                "pattern_3": {
                    "name": "📊 牌譜分析ルール",
                    "type": "rule_engine_2",
                    "content": self._format_rules(rules_2, "haihu")
                },
                "pattern_4": {
                    "name": "🤖 AI解釈（定石照合）",
                    "type": "ai_interpretation_1",
                    "content": self._interpret_ai_with_rules(ai_output, rules_1)
                },
                "pattern_5": {
                    "name": "📈 AI解釈（牌譜照合）",
                    "type": "ai_interpretation_2",
                    "content": self._interpret_ai_with_rules(ai_output, rules_2)
                }
            }
        }
    
    def _generate_xai_analysis(self, ai_output: Dict, hand_tiles: List[str]) -> Dict:
        """パターン1: XAI解析"""
        probability = ai_output.get("probability", 0.0)
        recommended_tile = ai_output.get("recommended_tile", "unknown")
        
        return {
            "recommended_tile": recommended_tile,
            "probability": probability,
            "reasoning": (
                f"OSS AIは牌{recommended_tile}を確率"
                f"{probability:.2%}で推奨。"
                f"ニューラルネットワークは牌効率と手牌の柔軟性を最適化。"
            ),
            "alternatives": ai_output.get("alternatives", [])[:2],
            "technical_factors": {
                "neural_confidence": probability,
                "model_type": "pjura/mahjong_ai",
                "architecture": "TabularClassification"
            }
        }
    
    def _format_rules(self, rules: List, rule_type: str) -> Dict:
        """ルールエンジン結果をフォーマット"""
        if not rules:
            return {
                "judgment": "BALANCE",
                "recommended_tile": "unknown",
                "reasoning": "適用可能なルールが見つかりませんでした",
                "rules_applied": []
            }
        
        # 最も確信度の高いルールを選択
        best_rule = rules[0]
        
        # 属性名の差異を吸収
        judgment_raw = getattr(best_rule, 'judgment', "BALANCE")
        judgment = judgment_raw.value if hasattr(judgment_raw, 'value') else str(judgment_raw)
        
        recommended_tile = getattr(best_rule, 'recommended_tile', "unknown")
        reasoning = getattr(best_rule, 'reasoning', "理由なし")
        confidence = getattr(best_rule, 'confidence', getattr(best_rule, 'probability', 0.0))
        
        rules_applied = []
        for r in rules[:3]:
            r_id = getattr(r, 'rule_id', getattr(r, 'pattern_id', 'unknown'))
            r_name = getattr(r, 'source', getattr(r, 'situation_desc', 'unknown'))
            r_judg_raw = getattr(r, 'judgment', "BALANCE")
            r_judg = r_judg_raw.value if hasattr(r_judg_raw, 'value') else str(r_judg_raw)
            r_tile = getattr(r, 'recommended_tile', "unknown")
            rules_applied.append({
                "id": r_id,
                "name": r_name,
                "judgment": r_judg,
                "tile": r_tile
            })
            
        return {
            "judgment": judgment,
            "recommended_tile": recommended_tile,
            "reasoning": reasoning,
            "confidence": confidence,
            "rules_applied": rules_applied
        }
    
    def _interpret_ai_with_rules(self, ai_output: Dict, rules: List) -> Dict:
        """AI出力をルールで解釈"""
        ai_tile = ai_output.get("recommended_tile", "unknown")
        
        # AIが推奨した牌とルールが一致するか確認
        matching_rules = [r for r in rules if getattr(r, 'recommended_tile', None) == ai_tile]
        
        if matching_rules:
            interpretation = (
                f"AIの推奨牌{ai_tile}は、麻雀の定石パターンと一致。"
                f"{len(matching_rules)}個のルールで支持されています。"
            )
        else:
            interpretation = (
                f"AIの推奨牌{ai_tile}は定石とは異なる独自の判断。"
                f"ニューラルネットワーク独自の評価による選択。"
            )
        
        rule_refs = []
        for r in matching_rules[:2]:
            r_id = getattr(r, 'rule_id', getattr(r, 'pattern_id', 'unknown'))
            r_reason = getattr(r, 'reasoning', '')
            rule_refs.append({
                "id": r_id,
                "reasoning": r_reason
            })
            
        return {
            "ai_tile": ai_tile,
            "interpretation": interpretation,
            "matching_rules_count": len(matching_rules),
            "consistency_score": len(matching_rules) / len(rules) if rules else 0.0,
            "rule_references": rule_refs
        }
