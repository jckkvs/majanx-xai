"""
強化麻雀AI: 統計的期待値ベース + ルールベース守備のハイブリッド
Implements: F-003+ | 強力なCPU対戦AI

サブシステム:
  1. OffenseEngine   - 牌効率・期待打点・手役追求
  2. DefenseEngine   - 現物・筋・壁・危険度テーブル
  3. PushFoldJudge   - 攻守バランス判定
  4. CallJudge       - 鳴き判断（攻撃的/守備的）
  5. SituationAnalyzer - 場況分析（巡目・点差・残り枚数）

参考: Suphx (arXiv:2003.13590), 天鳳統計データ, 牌理理論
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from mahjong.shanten import Shanten

from .models import (
    Tile, TileSuit, Wind, GameState, PlayerState,
    ActionType, GameAction, MeldType, Meld,
)
from .engine import GameEngine


# ============================================================
# 判断根拠データ構造
# ============================================================

@dataclass
class DecisionReason:
    """AI判断の根拠を記録するデータ構造"""
    category: str           # offense / defense / push_fold / call / situation
    description: str        # 日本語説明
    values: dict = field(default_factory=dict)  # 数値根拠

@dataclass
class DiscardCandidate:
    """打牌候補の評価結果"""
    tile: Tile
    shanten_after: int
    ukeire: int              # 受入枚数
    ukeire_tiles: list[Tile] = field(default_factory=list)
    good_shape_ratio: float = 0.0   # 良形率 (両面待ちの割合)
    expected_points: float = 0.0    # 期待打点
    safety_score: float = 1.0       # 安全度 (0=超危険, 1=完全安全)
    offense_score: float = 0.0      # 攻撃スコア
    defense_score: float = 0.0      # 守備スコア
    final_score: float = 0.0        # 最終評価スコア
    reasons: list[DecisionReason] = field(default_factory=list)

@dataclass
class AIDecision:
    """AIの最終判断"""
    action: str                        # discard / call / tsumo_hora / riichi
    tile: Optional[Tile] = None
    candidates: list[DiscardCandidate] = field(default_factory=list)
    reasons: list[DecisionReason] = field(default_factory=list)
    push_fold_state: str = "push"      # push / fold / neutral
    attack_ev: float = 0.0
    defense_risk: float = 0.0
    situation_summary: str = ""


# ============================================================
# 1. OffenseEngine - 攻撃エンジン
# ============================================================

class OffenseEngine:
    """牌効率・期待打点・手役追求"""

    HAND_VALUE_TABLE = {
        1: {20: 700, 25: 1000, 30: 1000, 40: 1300, 50: 1600, 60: 2000, 70: 2300},
        2: {20: 1300, 25: 1600, 30: 2000, 40: 2600, 50: 3200, 60: 3900, 70: 4500},
        3: {20: 2600, 25: 3200, 30: 3900, 40: 5200, 50: 6400, 60: 7700},
        4: {20: 5200, 25: 6400, 30: 7700, 40: 8000, 50: 8000},
        5: {0: 8000}, 6: {0: 12000}, 7: {0: 12000}, 8: {0: 16000},
        9: {0: 16000}, 10: {0: 16000}, 11: {0: 24000}, 12: {0: 24000},
        13: {0: 32000},
    }

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.shanten_calc = Shanten()

    def evaluate_all_discards(self, player: PlayerState,
                              visible_tiles: list[Tile]) -> list[DiscardCandidate]:
        """全候補牌を評価"""
        hand = player.hand
        tiles_34 = self.engine._hand_to_34(hand)
        current_shanten = self.shanten_calc.calculate_shanten(tiles_34)

        candidates: list[DiscardCandidate] = []
        seen: set[tuple] = set()

        for tile in hand:
            key = (tile.suit, tile.number, tile.is_red)
            if key in seen:
                continue
            seen.add(key)

            candidate = self._evaluate_single(
                player, tile, current_shanten, visible_tiles
            )
            candidates.append(candidate)

        return candidates

    def _evaluate_single(self, player: PlayerState, tile: Tile,
                         current_shanten: int,
                         visible_tiles: list[Tile]) -> DiscardCandidate:
        """1枚の牌を切った場合の攻撃評価"""
        test_hand = list(player.hand)
        for i, t in enumerate(test_hand):
            if t.suit == tile.suit and t.number == tile.number and t.is_red == tile.is_red:
                test_hand.pop(i)
                break

        tiles_34 = self.engine._hand_to_34(test_hand)
        shanten_after = self.shanten_calc.calculate_shanten(tiles_34)

        # 受入枚数計算（見えている牌を除外）
        ukeire, ukeire_tiles = self._calc_ukeire(
            tiles_34, shanten_after, visible_tiles
        )

        # 良形率（テンパイ時のみ）
        good_shape = 0.0
        if shanten_after == 0:
            good_shape = self._calc_good_shape_ratio(test_hand, tiles_34, visible_tiles)

        # 期待打点
        expected_pts = self._estimate_points(player, test_hand, tile)

        # 攻撃スコア計算
        offense = self._calc_offense_score(
            shanten_after, current_shanten, ukeire, good_shape, expected_pts, tile
        )

        reasons = []
        if shanten_after < current_shanten:
            reasons.append(DecisionReason(
                "offense", f"向聴数前進 {current_shanten}→{shanten_after}",
                {"shanten_delta": current_shanten - shanten_after}
            ))
        if ukeire > 0:
            reasons.append(DecisionReason(
                "offense", f"受入{ukeire}枚",
                {"ukeire": ukeire}
            ))

        return DiscardCandidate(
            tile=tile,
            shanten_after=shanten_after,
            ukeire=ukeire,
            ukeire_tiles=ukeire_tiles,
            good_shape_ratio=good_shape,
            expected_points=expected_pts,
            offense_score=offense,
            reasons=reasons,
        )

    def _calc_ukeire(self, tiles_34: list[int], shanten: int,
                     visible_tiles: list[Tile]) -> tuple[int, list[Tile]]:
        """受入枚数(実枚数ベース)"""
        if shanten < 0:
            return 0, []

        visible_34 = [0] * 34
        for t in visible_tiles:
            idx = self.engine._tile_to_34_index(t)
            visible_34[idx] += 1

        ukeire = 0
        ukeire_tiles: list[Tile] = []

        for idx in range(34):
            if tiles_34[idx] >= 4:
                continue
            test_34 = list(tiles_34)
            test_34[idx] += 1
            new_shanten = self.shanten_calc.calculate_shanten(test_34)
            if new_shanten < shanten:
                remaining = 4 - tiles_34[idx] - visible_34[idx]
                if remaining > 0:
                    ukeire += remaining
                    ukeire_tiles.append(self._idx_to_tile(idx))

        return ukeire, ukeire_tiles

    def _calc_good_shape_ratio(self, hand: list[Tile], tiles_34: list[int],
                                visible_tiles: list[Tile]) -> float:
        """テンパイ時の良形率(両面待ちの比率)"""
        waiting = []
        for idx in range(34):
            if tiles_34[idx] >= 4:
                continue
            test_34 = list(tiles_34)
            test_34[idx] += 1
            if self.shanten_calc.calculate_shanten(test_34) == -1:
                waiting.append(idx)

        if not waiting:
            return 0.0

        # 待ち枚数が多い=良形の近似
        visible_34 = [0] * 34
        for t in visible_tiles:
            visible_34[self.engine._tile_to_34_index(t)] += 1

        total_remaining = 0
        for idx in waiting:
            total_remaining += max(0, 4 - tiles_34[idx] - visible_34[idx])

        # 5枚以上 = 良形、2枚以下 = 悪形
        if total_remaining >= 5:
            return 1.0
        elif total_remaining >= 3:
            return 0.6
        else:
            return 0.2

    def _estimate_points(self, player: PlayerState,
                         remaining_hand: list[Tile], discarded: Tile) -> float:
        """期待打点の推定"""
        st = self.engine.state
        base_han = 0

        # ドラ枚数
        dora_count = 0
        for t in remaining_hand:
            if t.is_red:
                dora_count += 1
            for dora in st.dora_tiles:
                if t.suit == dora.suit and t.number == dora.number:
                    dora_count += 1
        base_han += dora_count

        # リーチ可能かチェック
        if player.is_menzen:
            base_han += 1  # リーチ分

        # 平和判定(簡易)
        non_honor_count = sum(1 for t in remaining_hand if not t.is_terminal_or_honor)
        if player.is_menzen and non_honor_count >= 10:
            base_han += 0.5  # 平和の可能性

        # タンヤオ判定(簡易)
        tanyao_tiles = sum(1 for t in remaining_hand
                          if not t.is_terminal_or_honor)
        if tanyao_tiles == len(remaining_hand):
            base_han += 1

        # 役牌
        relative_seat = (player.seat - st.dealer) % 4
        for t in remaining_hand:
            if t.suit == TileSuit.WIND:
                count = sum(1 for h in remaining_hand
                           if h.suit == t.suit and h.number == t.number)
                if count >= 2:
                    is_yaku = (t.number == relative_seat + 1 or
                              t.number == st.round_wind.value + 1 or
                              t.number >= 5)
                    if is_yaku:
                        base_han += 0.5

        # 翻数→点数 (子のデフォルト)
        effective_han = max(1, int(base_han + 0.5))
        if effective_han >= 13:
            return 32000
        elif effective_han >= 11:
            return 24000
        elif effective_han >= 8:
            return 16000
        elif effective_han >= 6:
            return 12000
        elif effective_han >= 5:
            return 8000
        elif effective_han >= 4:
            return 6400
        elif effective_han >= 3:
            return 3900
        elif effective_han >= 2:
            return 2000
        else:
            return 1000

    def _calc_offense_score(self, shanten_after: int, current_shanten: int,
                            ukeire: int, good_shape: float,
                            expected_pts: float, tile: Tile) -> float:
        """攻撃総合スコア"""
        score = 0.0

        # 向聴数が上がる場合は大幅ペナルティ
        if shanten_after > current_shanten:
            score -= 10000
        elif shanten_after < current_shanten:
            score += 5000  # 向聴数前進は最優先

        # 受入枚数 (主要因子)
        score += ukeire * 100

        # 良形ボーナス
        score += good_shape * 500

        # 期待打点 (正規化して加算)
        score += expected_pts * 0.1

        # 赤ドラペナルティ (切りたくない)
        if tile.is_red:
            score -= 800

        # ドラペナルティ
        for dora in self.engine.state.dora_tiles:
            if tile.suit == dora.suit and tile.number == dora.number:
                score -= 600

        return score

    def _idx_to_tile(self, idx: int) -> Tile:
        if idx < 9:
            return Tile(suit=TileSuit.MAN, number=idx + 1)
        elif idx < 18:
            return Tile(suit=TileSuit.PIN, number=idx - 9 + 1)
        elif idx < 27:
            return Tile(suit=TileSuit.SOU, number=idx - 18 + 1)
        else:
            return Tile(suit=TileSuit.WIND, number=idx - 27 + 1)


# ============================================================
# 2. DefenseEngine - 守備エンジン
# ============================================================

class DefenseEngine:
    """現物・筋・壁に基づく安全度計算"""

    # 巡目別・牌種別の放銃確率ベース (天鳳統計に基づく近似値)
    DANGER_BASE = {
        "terminal": 0.03,    # 1,9
        "near_terminal": 0.06,  # 2,8
        "middle": 0.10,      # 3-7
        "honor_1": 0.04,     # 字牌(1枚切れ)
        "honor_0": 0.08,     # 字牌(生牌)
        "honor_2": 0.02,     # 字牌(2枚切れ)
    }

    def __init__(self, engine: GameEngine):
        self.engine = engine

    def calc_safety_scores(self, player: PlayerState,
                           visible_tiles: list[Tile]) -> dict[tuple, float]:
        """手牌の各牌の安全度を計算。返り値: {(suit, number, is_red): safety_score}"""
        st = self.engine.state
        safety_map: dict[tuple, float] = {}

        riichi_players = [p for p in st.players
                         if p.seat != player.seat and p.is_riichi]

        if not riichi_players:
            # リーチ者がいない場合は全て比較的安全
            for tile in player.hand:
                key = (tile.suit, tile.number, tile.is_red)
                if key not in safety_map:
                    safety_map[key] = self._calc_no_riichi_safety(tile, st, visible_tiles)
            return safety_map

        for tile in player.hand:
            key = (tile.suit, tile.number, tile.is_red)
            if key in safety_map:
                continue

            worst_safety = 1.0
            for rp in riichi_players:
                s = self._calc_safety_against(tile, rp, st, visible_tiles)
                worst_safety = min(worst_safety, s)

            safety_map[key] = worst_safety

        return safety_map

    def _calc_no_riichi_safety(self, tile: Tile, st: GameState,
                                visible_tiles: list[Tile]) -> float:
        """リーチ者なし時の安全度 (副露者のダマテンリスク等)"""
        # 基本的に高めの安全度
        if tile.is_terminal_or_honor:
            return 0.95
        if tile.number in (2, 8):
            return 0.85
        return 0.75  # 中張牌はやや注意

    def _calc_safety_against(self, tile: Tile, riichi_player: PlayerState,
                              st: GameState, visible_tiles: list[Tile]) -> float:
        """特定リーチ者に対する安全度"""
        # 1. 現物チェック (完全安全)
        for d in riichi_player.discards:
            if d.suit == tile.suit and d.number == tile.number:
                return 1.0

        # 2. 同巡現物(他家の切った牌)チェック - 簡易版
        # リーチ後に他家が切って通った牌も安全
        riichi_turn = riichi_player.riichi_turn
        for p in st.players:
            if p.seat == riichi_player.seat:
                continue
            for i, d in enumerate(p.discards):
                if (d.suit == tile.suit and d.number == tile.number):
                    return 0.98  # ほぼ安全

        # 3. 字牌の安全度
        if tile.suit == TileSuit.WIND:
            visible_count = sum(1 for v in visible_tiles
                               if v.suit == tile.suit and v.number == tile.number)
            if visible_count >= 3:
                return 0.99  # 3枚見え = ほぼ安全
            elif visible_count >= 2:
                return 0.85
            elif visible_count >= 1:
                return 0.65
            else:
                return 0.40  # 生牌字牌はやや危険

        # 4. 筋(suji)チェック
        suji_safety = self._calc_suji_safety(tile, riichi_player, visible_tiles)

        # 5. 壁(kabe)チェック
        kabe_safety = self._calc_kabe_safety(tile, visible_tiles)

        # 6. 牌種別の基本危険度
        base = self._get_base_danger(tile)

        # 統合: 各安全要因の最大値を取る (最も安全な根拠を採用)
        safety_from_analysis = max(suji_safety, kabe_safety)

        # 基本安全度と分析結果を統合
        final = max(1.0 - base, safety_from_analysis)

        # 巡目による補正(終盤ほど危険度上昇)
        turn_ratio = min(1.0, st.turn_count / 72.0)
        final *= (1.0 - turn_ratio * 0.15)

        return max(0.0, min(1.0, final))

    def _calc_suji_safety(self, tile: Tile, riichi_player: PlayerState,
                           visible_tiles: list[Tile]) -> float:
        """筋の安全度"""
        if tile.suit == TileSuit.WIND:
            return 0.0  # 字牌には筋は適用されない

        num = tile.number
        suit = tile.suit
        discards = riichi_player.discards

        def has_discard(n: int) -> bool:
            return any(d.suit == suit and d.number == n for d in discards)

        # 両筋 (4m切り→1m安全 & 7m安全 みたいに)
        if num in (1, 2, 3):
            if has_discard(num + 3):  # 片筋
                return 0.70
        elif num in (7, 8, 9):
            if has_discard(num - 3):  # 片筋
                return 0.70
        elif num in (4, 5, 6):
            has_lower = has_discard(num - 3)
            has_upper = has_discard(num + 3)
            if has_lower and has_upper:
                return 0.80  # 両筋
            elif has_lower or has_upper:
                return 0.55  # 片筋

        return 0.0  # 筋に該当しない

    def _calc_kabe_safety(self, tile: Tile, visible_tiles: list[Tile]) -> float:
        """壁の安全度"""
        if tile.suit == TileSuit.WIND:
            return 0.0

        num = tile.number
        suit = tile.suit

        def visible_count(n: int) -> int:
            return sum(1 for v in visible_tiles
                      if v.suit == suit and v.number == n)

        # 隣接牌が4枚見え→両面待ちが不可能
        safety = 0.0

        if num >= 2:
            if visible_count(num - 1) >= 4:
                safety = max(safety, 0.75)
        if num <= 8:
            if visible_count(num + 1) >= 4:
                safety = max(safety, 0.75)

        # 両方の壁
        if num >= 2 and num <= 8:
            if visible_count(num - 1) >= 4 and visible_count(num + 1) >= 4:
                safety = 0.90  # 両側壁 = 非常に安全

        return safety

    def _get_base_danger(self, tile: Tile) -> float:
        """牌種別の基本危険度"""
        if tile.suit == TileSuit.WIND:
            return self.DANGER_BASE["honor_0"]

        if tile.number in (1, 9):
            return self.DANGER_BASE["terminal"]
        elif tile.number in (2, 8):
            return self.DANGER_BASE["near_terminal"]
        else:
            return self.DANGER_BASE["middle"]

    def get_safest_discard_order(self, player: PlayerState,
                                  visible_tiles: list[Tile]) -> list[Tile]:
        """最も安全な順に牌をソート (ベタオリ用)"""
        safety_map = self.calc_safety_scores(player, visible_tiles)
        hand_with_safety = []
        seen = set()
        for tile in player.hand:
            key = (tile.suit, tile.number, tile.is_red)
            if key in seen:
                continue
            seen.add(key)
            safety = safety_map.get(key, 0.5)
            hand_with_safety.append((tile, safety))

        hand_with_safety.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in hand_with_safety]


# ============================================================
# 3. PushFoldJudge - 押し引き判定
# ============================================================

class PushFoldJudge:
    """攻守バランスを判定"""

    def __init__(self, engine: GameEngine):
        self.engine = engine

    def judge(self, player: PlayerState, shanten: int, ukeire: int,
              expected_points: float, safety_map: dict[tuple, float],
              situation: dict) -> tuple[str, float, float, list[DecisionReason]]:
        """
        押し引き判定

        Returns: (decision, attack_ev, defense_risk, reasons)
            decision: "push" / "fold" / "neutral"
        """
        st = self.engine.state
        reasons: list[DecisionReason] = []

        riichi_players = [p for p in st.players
                         if p.seat != player.seat and p.is_riichi]

        if not riichi_players:
            reasons.append(DecisionReason(
                "push_fold", "リーチ者なし → 攻撃優先", {}
            ))
            return "push", expected_points, 0.0, reasons

        # 攻撃期待値
        win_prob = self._estimate_win_probability(shanten, ukeire, st)
        attack_ev = win_prob * expected_points

        # リーチ棒・本場ボーナス
        bonus = st.riichi_sticks * 1000 + st.honba * 300
        attack_ev += win_prob * bonus

        # 放銃リスク
        defense_risk = 0.0
        for rp in riichi_players:
            avg_danger = self._avg_hand_danger(player, safety_map)
            estimated_loss = self._estimate_riichi_points(rp)
            defense_risk += avg_danger * estimated_loss

        # 押し引き係数 (状況による調整)
        k = self._calc_push_fold_threshold(player, st, situation)

        reasons.append(DecisionReason(
            "push_fold",
            f"攻撃EV={attack_ev:.0f}, 防御リスク={defense_risk:.0f}, K={k:.1f}",
            {"attack_ev": attack_ev, "defense_risk": defense_risk, "k": k}
        ))

        if attack_ev > defense_risk * k:
            decision = "push"
            reasons.append(DecisionReason(
                "push_fold", "攻撃期待値が上回る → 押し",
                {"margin": attack_ev - defense_risk * k}
            ))
        elif shanten >= 2:
            decision = "fold"
            reasons.append(DecisionReason(
                "push_fold", f"{shanten}向聴 + リーチ者あり → オリ", {}
            ))
        elif shanten == 1 and ukeire < 6:
            decision = "fold"
            reasons.append(DecisionReason(
                "push_fold", "イーシャンテンだが受入少ない → オリ",
                {"ukeire": ukeire}
            ))
        elif shanten == 0:
            decision = "push"
            reasons.append(DecisionReason(
                "push_fold", "テンパイ → 基本押し", {}
            ))
        else:
            decision = "neutral"
            reasons.append(DecisionReason(
                "push_fold", "微妙な状況 → 回し打ち", {}
            ))

        return decision, attack_ev, defense_risk, reasons

    def _estimate_win_probability(self, shanten: int, ukeire: int,
                                   st: GameState) -> float:
        """和了確率の推定"""
        remaining = max(1, st.tiles_remaining)
        if shanten < 0:
            return 1.0
        elif shanten == 0:
            return min(0.6, ukeire * remaining / 500.0)
        elif shanten == 1:
            return min(0.3, ukeire * remaining / 1500.0)
        elif shanten == 2:
            return min(0.1, ukeire * remaining / 3000.0)
        else:
            return 0.02

    def _avg_hand_danger(self, player: PlayerState,
                          safety_map: dict[tuple, float]) -> float:
        """手牌の平均危険度"""
        if not safety_map:
            return 0.1
        safeties = list(safety_map.values())
        if not safeties:
            return 0.1
        avg_safety = sum(safeties) / len(safeties)
        return 1.0 - avg_safety

    def _estimate_riichi_points(self, riichi_player: PlayerState) -> float:
        """リーチ者の推定打点"""
        return 5200  # リーチ+α の平均的な打点

    def _calc_push_fold_threshold(self, player: PlayerState,
                                    st: GameState, situation: dict) -> float:
        """押し引きの閾値K"""
        k = 1.5  # デフォルト

        # トップ目 → 守備的
        scores = [p.score for p in st.players]
        my_rank = sum(1 for s in scores if s > player.score) + 1
        if my_rank == 1:
            k += 0.5
        elif my_rank == 4:
            k -= 0.5  # ラス目は攻撃的

        # 終盤 → 守備的
        if situation.get("phase") == "late":
            k += 0.3

        return max(0.5, k)


# ============================================================
# 4. CallJudge - 鳴き判断
# ============================================================

class CallJudge:
    """鳴きの判断"""

    def __init__(self, engine: GameEngine):
        self.engine = engine

    def decide(self, player: PlayerState, options: list[GameAction],
               shanten_before: int, situation: dict) -> GameAction:
        """鳴きの判断を返す"""
        st = self.engine.state

        # ロンは常に受ける
        for opt in options:
            if opt.action_type == ActionType.HORA:
                return opt

        # 大明槓は基本的に実行
        for opt in options:
            if opt.action_type == ActionType.DAIMINKAN:
                return opt

        # ポン判断
        for opt in options:
            if opt.action_type == ActionType.PON:
                if self._should_pon(player, opt, shanten_before, st, situation):
                    return opt

        # チー判断
        for opt in options:
            if opt.action_type == ActionType.CHI:
                if self._should_chi(player, opt, shanten_before, st, situation):
                    return opt

        return GameAction(action_type=ActionType.SKIP, player=player.seat)

    def _should_pon(self, player: PlayerState, opt: GameAction,
                     shanten_before: int, st: GameState, situation: dict) -> bool:
        """ポンすべきか"""
        tile = opt.tile
        if tile is None:
            return False

        # 役牌は常にポン
        relative_seat = (player.seat - st.dealer) % 4
        if tile.suit == TileSuit.WIND:
            is_yaku = (tile.number == relative_seat + 1 or
                      tile.number == st.round_wind.value + 1 or
                      tile.number >= 5)
            if is_yaku:
                return True

        # ドラ対子のポン
        for dora in st.dora_tiles:
            if tile.suit == dora.suit and tile.number == dora.number:
                return True

        # ポン後に向聴数が下がるかチェック
        if opt.consumed:
            test_hand = list(player.hand)
            for c in opt.consumed:
                for i, t in enumerate(test_hand):
                    if t.suit == c.suit and t.number == c.number:
                        test_hand.pop(i)
                        break

            tiles_34 = self.engine._hand_to_34(test_hand)
            shanten_after = Shanten().calculate_shanten(tiles_34)
            if shanten_after < shanten_before:
                return True

        return False

    def _should_chi(self, player: PlayerState, opt: GameAction,
                     shanten_before: int, st: GameState, situation: dict) -> bool:
        """チーすべきか"""
        if opt.consumed is None:
            return False

        # チー後に向聴数が下がるかチェック
        test_hand = list(player.hand)
        for c in opt.consumed:
            for i, t in enumerate(test_hand):
                if t.suit == c.suit and t.number == c.number:
                    test_hand.pop(i)
                    break

        tiles_34 = self.engine._hand_to_34(test_hand)
        shanten_after = Shanten().calculate_shanten(tiles_34)

        if shanten_after < shanten_before:
            # 副露テンパイは強力
            if shanten_after == 0:
                return True
            # イーシャンテンへの前進も場況次第で可
            if situation.get("phase") != "early":
                return True

        return False


# ============================================================
# 5. SituationAnalyzer - 場況分析
# ============================================================

class SituationAnalyzer:
    """場況の分析 + ベイズ的他家推定"""

    def __init__(self, engine: GameEngine):
        self.engine = engine

    def analyze(self, player_seat: int) -> dict:
        """場況を総合分析して辞書で返す"""
        st = self.engine.state
        player = st.players[player_seat]

        # 巡目フェーズ
        turn = st.turn_count
        if turn <= 24:
            phase = "early"    # 序盤(~6巡)
        elif turn <= 48:
            phase = "middle"   # 中盤(7-12巡)
        else:
            phase = "late"     # 終盤(13巡~)

        # 点数状況
        scores = [p.score for p in st.players]
        my_rank = sum(1 for s in scores if s > player.score) + 1

        # 親判定
        is_dealer = (st.dealer == player_seat)

        # 残り局数の推定
        is_east = st.round_wind == Wind.EAST
        remaining_rounds = max(1, (4 - st.round_number) + (4 if is_east else 0))

        # 他家分析 (ベイズ的推定)
        opponents_analysis = []
        for p in st.players:
            if p.seat == player_seat:
                continue
            opp = self._analyze_opponent(p, st, turn)
            opponents_analysis.append(opp)

        # 総合戦略スタンス判定
        stance, stance_reason = self._determine_stance(
            player, st, phase, turn, my_rank, is_dealer,
            remaining_rounds, opponents_analysis
        )

        return {
            "phase": phase,
            "turn": turn,
            "danger_players": [o for o in opponents_analysis if o["threat_level"] >= 2],
            "has_riichi": any(p.is_riichi for p in st.players if p.seat != player_seat),
            "my_rank": my_rank,
            "my_score": player.score,
            "is_dealer": is_dealer,
            "score_diff_to_top": max(scores) - player.score,
            "remaining_rounds": remaining_rounds,
            "tiles_remaining": st.tiles_remaining,
            "opponents": opponents_analysis,
            "stance": stance,           # "absolute_attack" / "absolute_defense" / "balanced"
            "stance_reason": stance_reason,
        }

    def _analyze_opponent(self, opp: PlayerState, st: GameState,
                           turn: int) -> dict:
        """他家1人のベイズ的推定"""
        # リーチ者は最高脅威
        if opp.is_riichi:
            # リーチ者の推定打点 (巡目とドラを考慮)
            est_points = self._estimate_riichi_hand_value(opp, st)
            return {
                "seat": opp.seat,
                "threat_level": 3,
                "estimated_points": est_points,
                "stance": "attack",
                "reason": f"リーチ宣言(推定打点{est_points:.0f}点)",
            }

        # 副露者の脅威推定
        num_melds = len(opp.melds)
        if num_melds >= 3:
            # 3副露 → テンパイの可能性大
            est_pts = self._estimate_meld_hand_value(opp, st)
            return {
                "seat": opp.seat,
                "threat_level": 2,
                "estimated_points": est_pts,
                "stance": "attack",
                "reason": f"{num_melds}副露(テンパイ濃厚, 推定{est_pts:.0f}点)",
            }
        elif num_melds >= 2:
            est_pts = self._estimate_meld_hand_value(opp, st)
            return {
                "seat": opp.seat,
                "threat_level": 1,
                "estimated_points": est_pts,
                "stance": "attack" if est_pts >= 3900 else "neutral",
                "reason": f"{num_melds}副露(推定{est_pts:.0f}点)",
            }

        # 門前で捨て牌パターンから推定
        # 早い巡目に中張牌を大量に切っている → 染め手/特殊手の可能性
        discard_count = len(opp.discards)
        if discard_count > 0:
            honor_discards = sum(1 for d in opp.discards if d.is_terminal_or_honor)
            middle_discards = sum(1 for d in opp.discards
                                if not d.is_terminal_or_honor)
            # 字牌・端牌が極端に多い → タンヤオ方向
            # 中張牌が極端に多い → 染め手 or 国士方向
            if middle_discards > discard_count * 0.7 and discard_count >= 6:
                return {
                    "seat": opp.seat,
                    "threat_level": 1,
                    "estimated_points": 8000,
                    "stance": "attack",
                    "reason": "中張牌大量切り(染め手/特殊手の可能性)",
                }

        # デフォルト: 脅威低い
        return {
            "seat": opp.seat,
            "threat_level": 0,
            "estimated_points": 2000,
            "stance": "neutral",
            "reason": "通常の手作り中",
        }

    def _estimate_riichi_hand_value(self, opp: PlayerState,
                                     st: GameState) -> float:
        """リーチ者の推定打点 (ベイズ的)"""
        base = 3900  # リーチ+ツモの最低ライン

        # ドラ表示牌との関連推定
        # 早い巡目のリーチ → 高打点の可能性が高い
        if opp.riichi_turn and opp.riichi_turn <= 6:
            base = 5200  # 早いリーチは好形・好手が多い

        # 副露なしリーチ → 裏ドラ期待もある
        base += 1000  # 裏ドラ期待値

        # 親リーチは1.5倍
        if st.dealer == opp.seat:
            base *= 1.5

        return base

    def _estimate_meld_hand_value(self, opp: PlayerState,
                                   st: GameState) -> float:
        """副露者の推定打点"""
        base = 1000
        for meld in opp.melds:
            for tile in meld.tiles:
                # 役牌チェック
                if tile.suit == TileSuit.WIND and tile.number >= 5:
                    base += 1000  # 三元牌
                    break
                relative = (opp.seat - st.dealer) % 4
                if tile.suit == TileSuit.WIND:
                    if (tile.number == relative + 1 or
                        tile.number == st.round_wind.value + 1):
                        base += 1000  # 自風/場風
                        break
                # ドラチェック
                for dora in st.dora_tiles:
                    if tile.suit == dora.suit and tile.number == dora.number:
                        base += 1000
                        break

        # 親は1.5倍
        if st.dealer == opp.seat:
            base *= 1.5

        return min(base, 12000)

    def _determine_stance(self, player: PlayerState, st: GameState,
                           phase: str, turn: int, my_rank: int,
                           is_dealer: bool, remaining_rounds: int,
                           opponents: list[dict]) -> tuple[str, str]:
        """
        総合戦略スタンスを決定

        Returns: (stance, reason)
            stance: "absolute_attack" / "absolute_defense" / "balanced"
        """
        # 高脅威の他家がいるか
        max_threat = max((o["threat_level"] for o in opponents), default=0)
        riichi_count = sum(1 for o in opponents if o.get("stance") == "attack"
                          and o["threat_level"] >= 3)

        # === 絶対守り条件 ===
        # ダブルリーチに対してリャンシャンテン以遠
        if riichi_count >= 2:
            return "absolute_defense", "複数リーチ → 絶対オリ"

        # トップ目 + オーラス + リーチ者あり
        if my_rank == 1 and remaining_rounds <= 1 and max_threat >= 3:
            return "absolute_defense", "トップ目オーラスでリーチ者あり → 守り切り"

        # === 絶対攻め条件 ===
        # ラス目 + 南場 + 残り局数少ない
        score_diff = max(p.score for p in st.players) - player.score
        if my_rank == 4 and remaining_rounds <= 2 and score_diff > 8000:
            return "absolute_attack", f"ラス目で{score_diff}点差 → 攻めるしかない"

        # 親番 (連荘チャンス)
        if is_dealer and max_threat < 3:
            return "absolute_attack", "親番 → 連荘狙いで攻撃的に"

        # === バランス判定 ===
        if max_threat >= 3:
            if phase == "early":
                return "balanced", "序盤リーチ → 手牌次第で判断"
            else:
                return "balanced", "リーチ者あり → 手牌との天秤"

        if phase == "late" and my_rank <= 2:
            return "balanced", "終盤トップ付近 → 慎重に"

        # デフォルト: バランス
        if max_threat >= 1:
            return "balanced", "副露者あり → 警戒しつつ手作り"

        return "absolute_attack", "脅威なし → 全力で手作り"


# ============================================================
# 統合: AdvancedCPUPlayer
# ============================================================

class AdvancedCPUPlayer:
    """5つのサブエンジンを統合した強力なCPU AI"""

    def __init__(self, seat: int, engine: GameEngine,
                 rng: Optional[random.Random] = None):
        self.seat = seat
        self.engine = engine
        self.rng = rng or random.Random()

        self.offense = OffenseEngine(engine)
        self.defense = DefenseEngine(engine)
        self.push_fold = PushFoldJudge(engine)
        self.call_judge = CallJudge(engine)
        self.situation = SituationAnalyzer(engine)

        self.last_decision: Optional[AIDecision] = None

    def choose_discard(self) -> Tile:
        """打牌を選択 (メインエントリポイント)"""
        player = self.engine.state.players[self.seat]
        hand = player.hand

        if not hand:
            raise ValueError("手牌が空です")

        # 1. 場況分析
        sit = self.situation.analyze(self.seat)

        # 2. 見えている牌を収集
        visible = self._collect_visible_tiles()

        # 3. 全候補の攻撃評価
        candidates = self.offense.evaluate_all_discards(player, visible)

        # 4. 守備評価
        safety_map = self.defense.calc_safety_scores(player, visible)
        for c in candidates:
            key = (c.tile.suit, c.tile.number, c.tile.is_red)
            c.safety_score = safety_map.get(key, 0.5)
            c.defense_score = c.safety_score * 1000

        # 5. 押し引き判定
        best_offense = max(candidates, key=lambda x: x.offense_score)
        current_shanten = Shanten().calculate_shanten(
            self.engine._hand_to_34(hand)
        )

        pf_decision, attack_ev, defense_risk, pf_reasons = self.push_fold.judge(
            player, current_shanten, best_offense.ukeire,
            best_offense.expected_points, safety_map, sit
        )

        # 6. 最終スコア計算
        for c in candidates:
            if pf_decision == "fold":
                # ベタオリモード: 安全度が最重要
                c.final_score = c.defense_score * 10 - abs(c.offense_score) * 0.01
            elif pf_decision == "neutral":
                # 回し打ち: 攻守バランス
                c.final_score = c.offense_score * 0.4 + c.defense_score * 0.6
            else:
                # 攻撃モード: 牌効率最優先、安全度は副次的
                c.final_score = c.offense_score * 0.85 + c.defense_score * 0.15

        # 最終ソート
        candidates.sort(key=lambda x: x.final_score, reverse=True)

        # 最善手を選択（向聴数が上がる牌は除外、ただしオリ時は例外）
        chosen = candidates[0]

        # 決定を記録
        self.last_decision = AIDecision(
            action="discard",
            tile=chosen.tile,
            candidates=candidates,
            reasons=pf_reasons + chosen.reasons,
            push_fold_state=pf_decision,
            attack_ev=attack_ev,
            defense_risk=defense_risk,
            situation_summary=f"{sit['phase']}(巡目{sit['turn']//4}),"
                             f"順位{sit['my_rank']},"
                             f"{'リーチ者あり' if sit['has_riichi'] else '安全'}",
        )

        return chosen.tile

    def decide_call(self, options: list[GameAction]) -> GameAction:
        """鳴きの判定"""
        player = self.engine.state.players[self.seat]
        tiles_34 = self.engine._hand_to_34(player.hand)
        shanten_before = Shanten().calculate_shanten(tiles_34)
        sit = self.situation.analyze(self.seat)

        return self.call_judge.decide(player, options, shanten_before, sit)

    def decide_tsumo_action(self, options: list[GameAction]) -> Optional[GameAction]:
        """ツモ後のアクション判定"""
        st = self.engine.state
        player = st.players[self.seat]

        # ツモ和了は常に受ける
        for opt in options:
            if opt.action_type == ActionType.HORA:
                return opt

        # リーチ判断
        riichi_options = [o for o in options if o.action_type == ActionType.RIICHI]
        if riichi_options:
            sit = self.situation.analyze(self.seat)
            if self._should_riichi(player, riichi_options, sit):
                # 最も受入の多い打牌でリーチ
                best_riichi = self._best_riichi_tile(player, riichi_options)
                if best_riichi:
                    return best_riichi

        # 暗槓
        for opt in options:
            if opt.action_type == ActionType.ANKAN:
                return opt

        return None

    def _should_riichi(self, player: PlayerState,
                        riichi_options: list[GameAction], sit: dict) -> bool:
        """リーチすべきか"""
        # 基本的にテンパイしたらリーチ
        # ダマの方が得な場合: 既に高打点 or 残り巡数少ない
        if sit["tiles_remaining"] < 8:
            return False  # 残り少ないならダマ

        # 点数がラスで追いかける状況 → リーチで裏ドラ狙い
        if sit["my_rank"] == 4:
            return True

        return True  # 基本はリーチ

    def _best_riichi_tile(self, player: PlayerState,
                           riichi_options: list[GameAction]) -> Optional[GameAction]:
        """リーチ時に最善の打牌を選ぶ"""
        visible = self._collect_visible_tiles()
        best = None
        best_ukeire = -1

        for opt in riichi_options:
            if opt.tile is None:
                continue
            test_hand = list(player.hand)
            for i, t in enumerate(test_hand):
                if t.suit == opt.tile.suit and t.number == opt.tile.number:
                    test_hand.pop(i)
                    break

            tiles_34 = self.engine._hand_to_34(test_hand)
            ukeire, _ = self.offense._calc_ukeire(tiles_34, 0, visible)
            if ukeire > best_ukeire:
                best_ukeire = ukeire
                best = opt

        return best

    def _collect_visible_tiles(self) -> list[Tile]:
        """見えている牌を収集"""
        visible: list[Tile] = []
        st = self.engine.state
        for p in st.players:
            visible.extend(p.discards)
            for meld in p.melds:
                visible.extend(meld.tiles)
        return visible
