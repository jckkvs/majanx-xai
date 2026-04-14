# server/xai/explanation_generator.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Any
import json

@dataclass(frozen=True)
class TileExplanation:
    selected_tile: str
    total_score: float
    weight_contributions: Dict[str, float]
    probabilities: Dict[str, float]
    reasoning: str
    alternative_tiles: List[str]

class ExplanationGenerator:
    """打牌判断の構造化説明出力モジュール"""
    
    @classmethod
    def generate(
        cls,
        selected_tile: str,
        scores: Dict[str, float],
        weights: Dict[str, float],
        probs: Dict[str, float],
        candidates: List[Dict[str, Any]]
    ) -> TileExplanation:
        """
        説明データ生成
        
        Args:
            selected_tile: 決定牌
            scores: 評価軸別生スコア
            weights: 適用重み
            probs: 確率分布 (win, tenpai, deal_in, draw)
            candidates: 全候補牌の評価結果リスト
        """
        # 1. 重み寄与度計算 (スコア×重み)
        contributions = {k: scores.get(k, 0.0) * weights.get(k, 0.0) for k in weights}
        
        # 2. 主理由抽出
        dominant = max(contributions.items(), key=lambda x: x[1])[0]
        mapping = {
            "shape": "形状価値", "ukeire": "受入最大化", 
            "honor": "字牌/役牌評価", "risk": "防御/放銃回避"
        }
        reason = f"{mapping.get(dominant, '総合')}を最優先要素として選択"
        
        # 3. 代替手抽出 (スコア上位2牌)
        alts = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
        alt_tiles = [c["tile"] for c in alts[1:3] if c["tile"] != selected_tile]
        
        return TileExplanation(
            selected_tile=selected_tile,
            total_score=scores.get("total", 0.0),
            weight_contributions=contributions,
            probabilities=probs,
            reasoning=reason,
            alternative_tiles=alt_tiles
        )
        
    @classmethod
    def to_json(cls, exp: TileExplanation) -> str:
        """JSONシリアライズ"""
        return json.dumps(asdict(exp), ensure_ascii=False, indent=2)
