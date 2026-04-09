"""
server/recommendation_aggregator.py
双視点並列提示・定量厳格化プロトコルに基づくアグリゲータ
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any
from server.ai_adapters.base import AIRecommendation

class RecommendationAggregator:
    """複数AIの推奨手を統合し、双視点を等価に提示するアグリゲータ"""
    
    # 定量データの出力必須5条件
    REQUIRED_QUANTITATIVE_FIELDS = [
        "dataset", 
        "period", 
        "sample_size", 
        "confidence_interval_95", 
        "methodology"
    ]
    
    def aggregate(
        self,
        recommendations: List[AIRecommendation],
        legal_actions: List[str]
    ) -> Dict[str, Any]:
        """
        AIからのレコメンドリストを受け取り、双視点並行(perspective_parallel)を出力する。
        """
        perspectives = []
        
        # コンセンサス・多数決ロジックは削除。全件をperspectiveとして同列に扱う
        for rec in recommendations:
            if not rec.recommended_action or rec.recommended_action.type == "none":
                continue
                
            p_data = {
                "source_ai": rec.ai_name,
                "recommended_action": rec.recommended_action.to_dict(),
                "reasoning": rec.reasoning or "定性原則が提供されていません",
                "checklist": self._extract_checklist(rec),
                "quantitative_reference": self._validate_and_extract_quantitative(rec)
            }
            perspectives.append(p_data)
            
        tradeoff = self._generate_tradeoff(perspectives)
            
        return {
            "perspective_parallel": perspectives,
            "tradeoff_analysis": tradeoff,
            "boundary_condition": self._generate_boundary_condition(perspectives, legal_actions)
        }
        
    def _validate_and_extract_quantitative(self, rec: AIRecommendation) -> Optional[Dict[str, Any]]:
        """定量データが5つの必須条件を満たしているか検証。欠落時はNoneを返す"""
        raw = rec.raw_output or {}
        quant = raw.get("quantitative_data")
        
        if not quant:
            return None
            
        # 必須条件のチェック
        missing = [f for f in self.REQUIRED_QUANTITATIVE_FIELDS if f not in quant]
        if missing:
            # 要件を満たさない疑似科学的数値は非表示
            return None
            
        return {
            "data": quant,
            "disclaimer": "※ この数値は相関傾向を示すものであり因果関係を保証しない。実戦判断は定性フレームを優先せよ。"
        }
        
    def _extract_checklist(self, rec: AIRecommendation) -> List[str]:
        """ダミーメソッド。実際にはraw_outputやreasoningから実践チェックリストを抽出"""
        raw = rec.raw_output or {}
        return raw.get("checklist", ["状況確認"])
        
    def _generate_tradeoff(self, perspectives: List[Dict]) -> Dict[str, Any]:
        """複数視点のトレードオフを明示する"""
        if len(perspectives) < 2:
            return {
                "message": "複数視点がありません。最終選択は現在の全般状況を加味して決定せよ。"
            }
            
        return {
            "option_A": f"{perspectives[0]['source_ai']}の提示する期待利益と許容リスク",
            "option_B": f"{perspectives[1]['source_ai']}の提示する期待利益と許容リスク",
            "final_guideline": "最終選択は現在の順位・点差・対戦相手の傾向で決定せよ"
        }
        
    def _generate_boundary_condition(self, perspectives: List[Dict], legal: List[str]) -> str:
        """境界条件エンジンスタブ。盤面変化によってAI推奨が反転する閾値を算出"""
        if not perspectives:
            return ""
        action = perspectives[0]["recommended_action"].get("pai", "不明")
        return (
            f"⚠️ もし「{action}が場に見えて3枚」になれば、受入消滅により防御軸へ反転。\n"
            "🔍 実戦確認: 最初の行動前に場に見える枚数をカウントせよ。"
        )
