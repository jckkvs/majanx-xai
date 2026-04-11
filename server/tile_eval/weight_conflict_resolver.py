"""
WeightConflictResolver: 複数ルール同時発火時の階層的重み統合
"""
from __future__ import annotations
from typing import Dict, List, Optional
from .weight_adapter import ExtendedWeightVector, PriorityWeightAdapter, WeightContext


class WeightConflictResolver:
    """複数ルール発火時の重み統合エンジン"""

    def __init__(self, adapter: PriorityWeightAdapter):
        self.adapter = adapter

    def resolve(
        self,
        triggered_rules: List[dict],
        context: WeightContext,
    ) -> ExtendedWeightVector:
        """
        複数の発火ルールから統合済み重みベクトルを生成。

        Args:
            triggered_rules: 発火したルールリスト。
                各要素は {"tile_selection": str, "priority": int, ...} を含む辞書。
                priority の降順（高い方が優先）でソートされている想定。
            context: 局面コンテキスト

        Returns:
            正規化済み ExtendedWeightVector
        """
        if not triggered_rules:
            return self.adapter.compute_weights('balanced', context)

        # 優先度順にソート（降順）
        sorted_rules = sorted(
            triggered_rules,
            key=lambda r: r.get('priority', 0),
            reverse=True,
        )

        # 統合対象を制限
        max_merge = self.adapter.max_rules_to_merge
        sorted_rules = sorted_rules[:max_merge]

        # 最優先ルールのベース重みを取得
        primary_tag = sorted_rules[0].get('tile_selection', 'balanced')
        result = self.adapter.compute_weights(primary_tag, context)

        # 2番目以降のルールを減衰加重平均で統合
        decay = self.adapter.decay_factor
        for i, rule in enumerate(sorted_rules[1:], start=1):
            tag = rule.get('tile_selection', 'balanced')
            secondary = self.adapter.compute_weights(tag, context)
            alpha = decay ** i  # i=1 → 0.5, i=2 → 0.25, ...
            result = result.blend(secondary, alpha)

        return result.normalize()

    def resolve_with_report(
        self,
        triggered_rules: List[dict],
        context: WeightContext,
    ) -> Dict:
        """
        統合処理を行い、デバッグ用レポートも返す。

        Returns:
            {
                "final_weights": ExtendedWeightVector,
                "primary_rule": str,
                "merged_count": int,
                "contributions": [{"rule_id": str, "tag": str, "alpha": float}, ...]
            }
        """
        if not triggered_rules:
            return {
                "final_weights": self.adapter.compute_weights('balanced', context),
                "primary_rule": None,
                "merged_count": 0,
                "contributions": [],
            }

        sorted_rules = sorted(
            triggered_rules,
            key=lambda r: r.get('priority', 0),
            reverse=True,
        )[:self.adapter.max_rules_to_merge]

        contributions = []
        decay = self.adapter.decay_factor

        primary_tag = sorted_rules[0].get('tile_selection', 'balanced')
        result = self.adapter.compute_weights(primary_tag, context)
        contributions.append({
            "rule_id": sorted_rules[0].get('id', 'unknown'),
            "tag": primary_tag,
            "alpha": 1.0,
        })

        for i, rule in enumerate(sorted_rules[1:], start=1):
            tag = rule.get('tile_selection', 'balanced')
            secondary = self.adapter.compute_weights(tag, context)
            alpha = decay ** i
            result = result.blend(secondary, alpha)
            contributions.append({
                "rule_id": rule.get('id', 'unknown'),
                "tag": tag,
                "alpha": alpha,
            })

        return {
            "final_weights": result.normalize(),
            "primary_rule": sorted_rules[0].get('id', 'unknown'),
            "merged_count": len(sorted_rules),
            "contributions": contributions,
        }
