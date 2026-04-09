"""
server/recommendation_aggregator.py
複数AIの推奨手エージェントからの意見を統合・競合判定する
"""
from __future__ import annotations

from collections import Counter
from typing import List, Dict, Optional

from server.ai_adapters.base import AIRecommendation

class RecommendationAggregator:
    """複数AIの推奨手を統合し、ユーザーに提示可能な形式で出力"""
    
    def aggregate(
        self,
        recommendations: List[AIRecommendation],
        legal_actions: List[str]
    ) -> Dict:
        """
        AIからのレコメンドリストを受け取り、コンセンサス・対立・定性理由をまとめて返す
        """
        tile_votes = Counter()
        reasoning_map = {}
        
        for rec in recommendations:
            if rec.recommended_action and rec.recommended_action.type == "dahai":
                tile = rec.recommended_action.params.get("pai")
                if not tile:
                    continue
                    
                tile_votes[tile] += 1
                if tile not in reasoning_map:
                    reasoning_map[tile] = []
                reasoning_map[tile].append({
                    "ai": rec.ai_name,
                    "reasoning": rec.reasoning or "理由は提供されていません"
                })
        
        # 1. コンセンサス推奨の評価
        if tile_votes:
            # most_common(1) は [(tile, count)] を返す
            top_candidate = tile_votes.most_common(1)[0]
            consensus_tile = top_candidate[0]
            vote_count = top_candidate[1]
            agreement_ratio = vote_count / len(recommendations)
        else:
            consensus_tile, agreement_ratio = None, 0.0
            
        # 2. 対立がある場合を明示
        conflicts = []
        if len(tile_votes) >= 2:
            top_two = tile_votes.most_common(2)
            if top_two[0][1] == top_two[1][1]:  # 上位2つの票数が同数の場合
                conflicts = [t for t, c in top_two]
                
        # 3. 定性フレームワーク抽出
        qualitative_frame = self._extract_qualitative_frame(recommendations)
                
        return {
            "consensus": {
                "tile": consensus_tile,
                "agreement_ratio": agreement_ratio,
                "reasoning_sources": reasoning_map.get(consensus_tile, [])
            },
            "alternatives": [
                {
                    "tile": tile,
                    "vote_count": count,
                    "reasoning_sources": reasoning_map[tile]
                }
                for tile, count in tile_votes.most_common()
                if tile != consensus_tile
            ],
            "conflicts": conflicts,
            "qualitative_frame": qualitative_frame,
            "boundary_condition": self._generate_boundary_condition(consensus_tile, legal_actions)
        }
        
    def _extract_qualitative_frame(self, recs: List[AIRecommendation]) -> Optional[str]:
        """複数AIの理由から共通する定性フレームを抽出（Rulebase優先）"""
        for rec in recs:
            if "Rulebase" in rec.ai_name and rec.reasoning:
                return rec.reasoning
        return None
        
    def _generate_boundary_condition(self, tile: Optional[str], legal: List[str]) -> str:
        """「盤面がΔ変わると推奨が反転する」条件の簡易スタブ"""
        if not tile:
            return "推奨牌が未確定のため、境界条件は計算できません"
        return (
            f"もし「{tile}が場に見えて3枚（残り1枚）」になれば、受入が物理的に消滅→防御軸へ反転。\n"
            f"実戦確認: 切る前に「場に見える{tile}の枚数」を最初にカウントしてください。"
        )
