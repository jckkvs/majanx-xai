"""
CPUプレイヤー: AdvancedCPUPlayer に委譲するラッパー
Implements: F-003 | CPU対戦機能

AdvancedCPUPlayer (advanced_ai.py) の強力なAIを内部で使用。
既存インターフェースを維持しつつ、判断品質を大幅に向上。
"""
from __future__ import annotations

import random
from typing import Optional

from .models import (
    Tile, TileSuit, GameState, PlayerState, ActionType, GameAction,
)
from .engine import GameEngine
from .advanced_ai import AdvancedCPUPlayer, AIDecision
from server.mortal import MortalAgent


class CPUPlayer:
    """
    AdvancedCPUPlayer に委譲するCPUプレイヤー。

    戦略(AdvancedCPUPlayerが実装):
    1. 攻撃: 牌効率(shanten+ukeire+良形率) + 期待打点
    2. 守備: 現物/筋/壁による安全度計算 + ベタオリ
    3. 押し引き: 攻撃EV vs 放銃リスクの比較判定
    4. 鳴き: 役牌ポン/ドラポン/副露テンパイ/チー判断
    5. 場況: 巡目/点差/残り枚数による戦略修正
    """

    def __init__(self, seat: int, engine: GameEngine,
                 rng: Optional[random.Random] = None):
        self.seat = seat
        self.engine = engine
        self.rng = rng or random.Random()
        self._ai = AdvancedCPUPlayer(seat, engine, self.rng)
        self._mortal = MortalAgent(seat, engine, self.rng)

    @property
    def last_decision(self) -> Optional[AIDecision]:
        """最後のAI判断結果を取得(解説エンジン連携用)"""
        return self._ai.last_decision

    def choose_discard(self) -> Tile:
        """打牌を選択"""
        try:
            return self._mortal.choose_discard()
        except Exception as e:
            print(f"[CPU {self.seat}] Mortalエラー、AdvancedAIにフォールバック: {e}")
            try:
                return self._ai.choose_discard()
            except Exception as e2:
                return self._fallback_discard()

    def decide_call(self, options: list[GameAction]) -> GameAction:
        """鳴きの判定"""
        try:
            return self._mortal.decide_call(options)
        except Exception as e:
            try:
                return self._ai.decide_call(options)
            except Exception as e2:
                return self._fallback_call(options)

    def decide_tsumo_action(self, options: list[GameAction]) -> Optional[GameAction]:
        """ツモ後のアクション判定"""
        try:
            return self._mortal.decide_tsumo_action(options)
        except Exception as e:
            try:
                return self._ai.decide_tsumo_action(options)
            except Exception:
                return self._fallback_tsumo(options)

    # ============================================================
    # フォールバック (AI障害時の最低限の動作保証)
    # ============================================================

    def _fallback_discard(self) -> Tile:
        """フォールバック打牌: 手牌の末尾を切る"""
        player = self.engine.state.players[self.seat]
        if player.hand:
            return player.hand[-1]
        raise ValueError("手牌が空です")

    def _fallback_call(self, options: list[GameAction]) -> GameAction:
        """フォールバック鳴き: ロンのみ受ける"""
        for opt in options:
            if opt.action_type == ActionType.HORA:
                return opt
        return GameAction(action_type=ActionType.SKIP, player=self.seat)

    def _fallback_tsumo(self, options: list[GameAction]) -> Optional[GameAction]:
        """フォールバックツモ: 和了のみ"""
        for opt in options:
            if opt.action_type == ActionType.HORA:
                return opt
        return None
