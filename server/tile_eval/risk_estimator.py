"""
牌単位の放銃リスク推定モジュール
現物・筋牌・壁牌・リーチタイミングを考慮して0.0〜1.0のリスクスコアを返す
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class RiskScore:
    """牌の放銃リスク評価結果"""
    tile_id: str
    danger: float          # 総合危険度 (0.0=安全, 1.0=極危険)
    genbutsu: bool         # 現物かどうか
    suji: bool             # 筋牌かどうか
    kabe: bool             # 壁判定（残り0枚の隣接牌）
    reasoning: str


@dataclass
class RiskContext:
    """リスク推定コンテキスト"""
    turn: int
    riichi_players: List[int]       # リーチ宣言済みプレイヤー座席
    discarded_tiles: Dict[int, List[str]]  # seat -> [捨牌ID]
    visible_tile_counts: Dict[str, int]    # 牌ID -> 見えている枚数
    current_seat: int


class RiskEstimator:
    """牌ごとの放銃リスクを推定するエンジン"""

    # 全34種の牌ID
    ALL_TILES = (
        [f"{n}{s}" for s in "mps" for n in range(1, 10)]
        + [f"{n}z" for n in range(1, 8)]
    )

    def estimate_all(self, tiles: List[str], ctx: RiskContext) -> Dict[str, RiskScore]:
        """手牌中の各牌のリスクを推定"""
        return {t: self.estimate(t, ctx) for t in set(tiles)}

    def estimate(self, tile_id: str, ctx: RiskContext) -> RiskScore:
        """単一牌のリスクを推定"""
        base_id = tile_id.replace('r', '')

        # リーチ者がいなければリスクは低い
        if not ctx.riichi_players:
            return RiskScore(tile_id=tile_id, danger=0.1, genbutsu=False,
                             suji=False, kabe=False, reasoning="リーチ者なし")

        max_danger = 0.0
        worst_reasoning = ""
        is_genbutsu = False
        is_suji = False
        is_kabe = False

        for seat in ctx.riichi_players:
            if seat == ctx.current_seat:
                continue
            discards = ctx.discarded_tiles.get(seat, [])
            discard_bases = [d.replace('r', '') for d in discards]

            # --- 現物チェック ---
            if base_id in discard_bases:
                is_genbutsu = True
                continue  # この相手に対しては完全安全

            # --- 字牌 ---
            if 'z' in base_id:
                visible = ctx.visible_tile_counts.get(base_id, 0)
                if visible >= 3:
                    is_kabe = True
                    continue  # 壁: 残り1枚以下、ほぼ安全
                danger = 0.4 + 0.05 * ctx.turn
                worst_reasoning = f"{base_id}は字牌・無スジ"
                max_danger = max(max_danger, min(danger, 0.85))
                continue

            # --- 筋牌チェック ---
            num = int(base_id[0])
            suit = base_id[1]
            suji_safe = self._check_suji(num, suit, discard_bases)
            if suji_safe:
                is_suji = True
                # 筋は比較的安全だが完全ではない
                danger = 0.15 + 0.02 * max(0, ctx.turn - 6)
                worst_reasoning = f"{base_id}は筋牌"
                max_danger = max(max_danger, min(danger, 0.35))
                continue

            # --- 壁チェック ---
            kabe_safe = self._check_kabe(num, suit, ctx.visible_tile_counts)
            if kabe_safe:
                is_kabe = True
                danger = 0.1
                worst_reasoning = f"{base_id}は壁牌"
                max_danger = max(max_danger, danger)
                continue

            # --- 無筋（最も危険） ---
            # ターンが進むほど危険度上昇
            base_danger = 0.35
            turn_factor = min(0.45, 0.03 * max(0, ctx.turn - 4))
            # 中張牌（3-7）は待ちになりやすい
            if 3 <= num <= 7:
                center_penalty = 0.1
            elif num in [2, 8]:
                center_penalty = 0.05
            else:
                center_penalty = 0.0  # 端牌

            danger = base_danger + turn_factor + center_penalty
            worst_reasoning = f"{base_id}は無筋({ctx.turn}巡目)"
            max_danger = max(max_danger, min(danger, 0.95))

        # 現物判定（全リーチ者に対して現物ならdanger=0）
        if is_genbutsu and max_danger == 0.0:
            return RiskScore(tile_id=tile_id, danger=0.0, genbutsu=True,
                             suji=is_suji, kabe=is_kabe, reasoning="全リーチ者の現物")

        return RiskScore(
            tile_id=tile_id,
            danger=round(max_danger, 3),
            genbutsu=is_genbutsu,
            suji=is_suji,
            kabe=is_kabe,
            reasoning=worst_reasoning or "標準リスク"
        )

    @staticmethod
    def _check_suji(num: int, suit: str, discards: List[str]) -> bool:
        """筋牌かどうかを判定"""
        if num <= 3:
            return f"{num + 3}{suit}" in discards
        elif num >= 7:
            return f"{num - 3}{suit}" in discards
        else:  # 4-6: 両方の筋が切れていること
            return f"{num - 3}{suit}" in discards and f"{num + 3}{suit}" in discards

    @staticmethod
    def _check_kabe(num: int, suit: str, visible: Dict[str, int]) -> bool:
        """壁牌（隣接牌が4枚見え）かどうかを判定"""
        # 隣接する牌が全て見えていれば壁 = その牌で待つことは不可能
        neighbors = []
        if num > 1:
            neighbors.append(f"{num - 1}{suit}")
        if num < 9:
            neighbors.append(f"{num + 1}{suit}")

        for n in neighbors:
            if visible.get(n, 0) >= 4:
                return True
        return False
