"""
PriorityWeightAdapter: ルール戦略タグと局面コンテキストから
5次元評価重みベクトルを動的に決定するアダプター
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import os
import yaml


@dataclass
class ExtendedWeightVector:
    """5次元評価重みベクトル"""
    shape: float   # 形状価値 (0.0-1.0)
    ukeire: float  # 受入枚数 (0.0-1.0)
    honor: float   # 字牌・役牌・防御価値 (0.0-1.0)
    risk: float    # 放銃リスク評価 (0.0-1.0)
    form: float    # 形勢判断 (0.0-1.0)

    def normalize(self) -> 'ExtendedWeightVector':
        """重みの合計を1.0に正規化"""
        total = self.shape + self.ukeire + self.honor + self.risk + self.form
        if total == 0:
            return ExtendedWeightVector(0.2, 0.2, 0.2, 0.2, 0.2)
        return ExtendedWeightVector(
            shape=self.shape / total,
            ukeire=self.ukeire / total,
            honor=self.honor / total,
            risk=self.risk / total,
            form=self.form / total,
        )

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'ExtendedWeightVector':
        return cls(
            shape=d.get('shape', 0.2),
            ukeire=d.get('ukeire', 0.2),
            honor=d.get('honor', 0.2),
            risk=d.get('risk', 0.2),
            form=d.get('form', 0.2),
        )

    def blend(self, other: 'ExtendedWeightVector', alpha: float) -> 'ExtendedWeightVector':
        """
        2つの重みベクトルをブレンド。
        alpha=0.0 なら self、alpha=1.0 なら other を返す。
        """
        inv = 1.0 - alpha
        return ExtendedWeightVector(
            shape=self.shape * inv + other.shape * alpha,
            ukeire=self.ukeire * inv + other.ukeire * alpha,
            honor=self.honor * inv + other.honor * alpha,
            risk=self.risk * inv + other.risk * alpha,
            form=self.form * inv + other.form * alpha,
        )

    def scale(self, factors: 'ExtendedWeightVector') -> 'ExtendedWeightVector':
        """各次元に係数を乗算（ターンフェーズ調整用）"""
        return ExtendedWeightVector(
            shape=self.shape * factors.shape,
            ukeire=self.ukeire * factors.ukeire,
            honor=self.honor * factors.honor,
            risk=self.risk * factors.risk,
            form=self.form * factors.form,
        )


@dataclass
class WeightContext:
    """重み決定に必要な局面コンテキスト"""
    turn: int = 1
    score_diff: float = 0.0       # 自分の点数 - トップとの点差
    rank: int = 2                  # 現在順位 (1-4)
    remaining_rounds: int = 8      # 残り局数
    riichi_count: int = 0          # 他家リーチ数
    is_dealer: bool = False
    honba: int = 0                 # 本場数

    @property
    def turn_phase(self) -> str:
        if self.turn <= 4:
            return 'early'
        elif self.turn <= 9:
            return 'middle'
        elif self.turn <= 14:
            return 'late'
        return 'end'


class PriorityWeightAdapter:
    """ルール戦略タグから5次元重みベクトルを決定するアダプター"""

    _CONFIG_PATH = os.path.join('config', 'efficiency_weights.yaml')

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path or self._CONFIG_PATH
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """YAML設定ファイルをロード"""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            # フォールバック: デフォルト重みを返す
            return {
                'defaults': {'shape': 0.3, 'ukeire': 0.25, 'honor': 0.2, 'risk': 0.15, 'form': 0.1},
                'strategy_weights': {},
                'turn_adjustments': {
                    'early': {'shape': 1.0, 'ukeire': 1.0, 'honor': 1.0, 'risk': 0.5, 'form': 0.8},
                    'middle': {'shape': 1.0, 'ukeire': 0.9, 'honor': 1.1, 'risk': 1.2, 'form': 1.0},
                    'late': {'shape': 0.8, 'ukeire': 0.6, 'honor': 1.3, 'risk': 1.8, 'form': 1.2},
                    'end': {'shape': 0.5, 'ukeire': 0.3, 'honor': 1.5, 'risk': 2.5, 'form': 1.5},
                },
                'conflict_resolution': {'decay_factor': 0.5, 'max_rules_to_merge': 5},
            }

    def reload_config(self):
        """設定を再読み込み（ホットリロード対応）"""
        self._config = self._load_config()

    @property
    def default_weights(self) -> ExtendedWeightVector:
        return ExtendedWeightVector.from_dict(self._config.get('defaults', {}))

    @property
    def decay_factor(self) -> float:
        return self._config.get('conflict_resolution', {}).get('decay_factor', 0.5)

    @property
    def max_rules_to_merge(self) -> int:
        return self._config.get('conflict_resolution', {}).get('max_rules_to_merge', 5)

    def get_strategy_weights(self, strategy_tag: str) -> ExtendedWeightVector:
        """戦略タグに対応するベース重みを取得"""
        strategy_map = self._config.get('strategy_weights', {})
        if strategy_tag in strategy_map:
            return ExtendedWeightVector.from_dict(strategy_map[strategy_tag])
        return self.default_weights

    def get_turn_adjustments(self, phase: str) -> ExtendedWeightVector:
        """ターンフェーズに対応する調整係数を取得"""
        adj_map = self._config.get('turn_adjustments', {})
        if phase in adj_map:
            return ExtendedWeightVector.from_dict(adj_map[phase])
        return ExtendedWeightVector(1.0, 1.0, 1.0, 1.0, 1.0)

    def compute_weights(
        self,
        strategy_tag: str,
        context: WeightContext,
    ) -> ExtendedWeightVector:
        """
        戦略タグと局面コンテキストから最終的な5次元重みを計算

        1. 戦略タグからベース重みを取得
        2. ターンフェーズ調整を適用
        3. 正規化して返す
        """
        # 1. ベース重み
        base = self.get_strategy_weights(strategy_tag)

        # 2. ターンフェーズ調整
        phase = context.turn_phase
        adjustments = self.get_turn_adjustments(phase)
        adjusted = base.scale(adjustments)

        # 3. 正規化
        return adjusted.normalize()
