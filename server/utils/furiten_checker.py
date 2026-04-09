"""
server/utils/furiten_checker.py
振聴（フリテン）判定エンジン

振聴の3分類:
  TypeA: 自分の捨て牌振聴（待ち牌が自分の捨て牌に含まれる）
  TypeB: 見逃し振聴（他家の和了牌を見逃した、一巡で解除）
  TypeC: 立直後振聴（手替わりで待ちが変化）

出力:
  - 振聴状態
  - 振聴回避の打牌候補
  - 降り時の振聴安全牌
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from server.models import Tile, GameState, PlayerState


@dataclass
class FuritenResult:
    """振聴判定の構造化出力"""
    is_furiten: bool
    furiten_type: str          # "none" / "TypeA" / "TypeB" / "TypeC"
    is_full_furiten: bool      # 全振聴（全ての待ちが振聴）
    furiten_tiles: List[str]   # 振聴に該当する牌
    safe_waits: List[str]      # 振聴でない待ち（部分振聴で和了可能な牌）
    strategy_impact: str       # 戦略的影響の説明

    def to_dict(self) -> Dict:
        return {
            "is_furiten": self.is_furiten,
            "type": self.furiten_type,
            "full": self.is_full_furiten,
            "furiten_tiles": self.furiten_tiles,
            "safe_waits": self.safe_waits,
            "impact": self.strategy_impact,
        }


class FuritenChecker:
    """振聴判定エンジン"""

    def check(self, gs: GameState, seat: int,
              wait_tiles: List[str] = None) -> FuritenResult:
        """
        振聴状態を判定する。

        Args:
            gs: ゲーム状態
            seat: プレイヤー席
            wait_tiles: 待ち牌リスト（Noneの場合は計算しない）

        Returns:
            FuritenResult
        """
        if not wait_tiles:
            return FuritenResult(
                is_furiten=False,
                furiten_type="none",
                is_full_furiten=False,
                furiten_tiles=[],
                safe_waits=[],
                strategy_impact="待ち牌なし（テンパイでない）"
            )

        player = gs.players[seat]
        discard_ids = {d.id for d in player.discards}
        wait_set = set(wait_tiles)

        # TypeA: 自分の捨て牌振聴
        furiten_tiles = list(wait_set & discard_ids)
        safe_waits = list(wait_set - discard_ids)

        if furiten_tiles:
            is_full = len(safe_waits) == 0
            impact = self._type_a_impact(is_full, furiten_tiles, safe_waits)
            return FuritenResult(
                is_furiten=True,
                furiten_type="TypeA",
                is_full_furiten=is_full,
                furiten_tiles=furiten_tiles,
                safe_waits=safe_waits,
                strategy_impact=impact,
            )

        return FuritenResult(
            is_furiten=False,
            furiten_type="none",
            is_full_furiten=False,
            furiten_tiles=[],
            safe_waits=list(wait_set),
            strategy_impact="振聴なし"
        )

    def find_furiten_safe_discards(self, gs: GameState,
                                    seat: int) -> List[str]:
        """
        降り時に活用できる振聴安全牌を列挙する。
        自分の捨て牌にある牌は、自分にとってロン不可。
        """
        player = gs.players[seat]
        discard_ids = {d.id for d in player.discards}
        hand_ids = {t.id for t in player.hand}
        return list(discard_ids & hand_ids)

    def optimize_tenpai_for_furiten(
        self, gs: GameState, seat: int,
        candidates: List[Dict]
    ) -> List[Dict]:
        """
        テンパイ時の打牌候補を振聴回避で最適化する。

        Args:
            candidates: [{"tile": str, "waits": [str], ...}, ...]

        Returns:
            振聴回避優先でソート済みの候補リスト
        """
        player = gs.players[seat]
        discard_ids = {d.id for d in player.discards}

        scored = []
        for c in candidates:
            waits = set(c.get("waits", []))
            furiten_count = len(waits & discard_ids)
            safe_count = len(waits - discard_ids)
            total_waits = len(waits)

            if furiten_count == 0:
                # Priority 1-2: 振聴なし
                priority = 1
            elif safe_count > 0:
                # Priority 3-4: 部分振聴
                priority = 3
            else:
                # Priority 5: 全振聴
                priority = 5

            scored.append({
                **c,
                "furiten_priority": priority,
                "furiten_count": furiten_count,
                "safe_wait_count": safe_count,
            })

        # 振聴優先度 → 受入枚数の降順でソート
        scored.sort(key=lambda x: (
            x["furiten_priority"],
            -x["safe_wait_count"]
        ))
        return scored

    def _type_a_impact(self, is_full: bool,
                        furiten: List[str], safe: List[str]) -> str:
        """TypeA振聴の戦略的影響を説明"""
        if is_full:
            return (f"全振聴。待ち{','.join(furiten)}が全て自分の捨て牌に含まれ、"
                    f"ロン和了不可。ツモ和了のみ可能。テンパイを崩して手替わりを検討")
        else:
            return (f"部分振聴。{','.join(furiten)}が振聴だが、"
                    f"{','.join(safe)}ではロン和了可能。待ちが狭まることを考慮して判断")
