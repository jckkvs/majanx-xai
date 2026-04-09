"""
server/engines/boundary_detector.py
境界条件（Counterfactual）検出エンジン

盤面の微差による判断反転を検出し、ユーザーが
「条件のわずかな変化で判断が反転する感覚」を習得するための
境界条件を1つ提示する。

検出軸:
  1. 枚数枯れ — 受入牌の場見え枚数変化
  2. 巡目進行 — 終盤防御閾値への接近
  3. 他家状態 — リーチ宣言・副露完了
  4. 順位圧力 — 点差の変動
  5. 手牌構成 — 暗刻スジ・序盤5切り罠
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BoundaryCondition:
    """境界条件の構造化出力"""
    boundary_id: str
    change_axis: str          # 変化軸
    description: str          # 自然言語の説明
    check_instruction: str    # 実戦での確認手順
    flip_to: str              # 反転先パラダイム
    sensitivity: float        # 感度（0.0〜1.0、高いほど早期に発現）

    def to_dict(self) -> Dict:
        return {
            "id": self.boundary_id,
            "axis": self.change_axis,
            "description": self.description,
            "check": self.check_instruction,
            "flip_to": self.flip_to,
            "sensitivity": round(self.sensitivity, 2),
        }


class BoundaryDetector:
    """
    盤面の現在状態と推奨打牌を受け取り、
    「わずかな盤面変化で判断が反転する条件」を1つ検出する。
    """

    def __init__(self, catalog_path: str = "server/rules/boundary_catalog.json"):
        self.catalog = self._load_catalog(catalog_path)

    def _load_catalog(self, path: str) -> List[Dict]:
        if not os.path.exists(path):
            logger.warning(f"Boundary catalog not found: {path}")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def detect(self, ctx: Dict, recommended_tile: str,
               paradigm_id: str) -> Optional[BoundaryCondition]:
        """
        最も早期に発現する境界条件を1つ検出して返す。
        """
        candidates = []

        # 軸1: 枚数枯れ
        bc_exhaust = self._check_tile_exhaustion(ctx, recommended_tile)
        if bc_exhaust:
            candidates.append(bc_exhaust)

        # 軸2: 巡目進行
        bc_turn = self._check_turn_advance(ctx, paradigm_id)
        if bc_turn:
            candidates.append(bc_turn)

        # 軸3: 他家状態
        bc_riichi = self._check_riichi_addition(ctx, paradigm_id)
        if bc_riichi:
            candidates.append(bc_riichi)

        # 軸4: 順位圧力
        bc_rank = self._check_rank_pressure(ctx, paradigm_id)
        if bc_rank:
            candidates.append(bc_rank)

        # 軸5: 暗刻スジ罠
        bc_anko = self._check_anko_suji(ctx, recommended_tile)
        if bc_anko:
            candidates.append(bc_anko)

        # 軸6: 序盤5切り罠
        bc_5cut = self._check_early_5_cut(ctx, recommended_tile)
        if bc_5cut:
            candidates.append(bc_5cut)

        if not candidates:
            return None

        # 感度順（高いほど早期発現）で最も感度の高い条件を1つ選択
        candidates.sort(key=lambda bc: bc.sensitivity, reverse=True)
        return candidates[0]

    # ═══════════════════════════════════════════════
    # 軸1: 枚数枯れ
    # ═══════════════════════════════════════════════

    def _check_tile_exhaustion(self, ctx: Dict,
                                tile: str) -> Optional[BoundaryCondition]:
        """推奨牌の受入先が枯れかけているかチェック"""
        gs = ctx.get("_gs")
        if not gs:
            return None

        # 推奨牌自体の場見え枚数ではなく、推奨牌を切った後の
        # 受入牌（待ち牌）の場見え枚数を検査する
        # ここでは簡易的に推奨牌自体が手牌以外で何枚見えているかで近似
        visible = self._count_visible_tile(gs, tile, ctx.get("_seat", 0))
        remaining = 4 - visible  # 赤ドラ含まず最大4枚

        if remaining <= 1:
            tpl = self._get_template("BOUNDARY_TILE_EXHAUST")
            desc = tpl["template"].format(
                tile=tile, visible=visible, remaining=remaining,
                current_paradigm=ctx.get("_paradigm", "速度軸"),
                flip_paradigm="防御軸"
            )
            return BoundaryCondition(
                boundary_id="BOUNDARY_TILE_EXHAUST",
                change_axis="枚数枯れ",
                description=desc,
                check_instruction=tpl["check_instruction"].format(tile=tile),
                flip_to="PAR_DEF",
                sensitivity=0.95
            )
        elif remaining <= 2:
            return BoundaryCondition(
                boundary_id="BOUNDARY_TILE_EXHAUST",
                change_axis="枚数枯れ",
                description=f"{tile}が場に{visible}枚見え（残り{remaining}枚）。"
                            f"あと1枚見えれば受入が大幅に減少する。",
                check_instruction=f"{tile}の場見え枚数を確認すること",
                flip_to="PAR_DEF",
                sensitivity=0.70
            )
        return None

    def _count_visible_tile(self, gs, tile_id: str, seat: int) -> int:
        """指定牌IDの場見え枚数を計算"""
        count = 0
        for p in gs.players:
            for d in p.discards:
                if d.id == tile_id:
                    count += 1
            for m in p.melds:
                for t in m.tiles:
                    if t.id == tile_id:
                        count += 1
        for di in gs.dora_indicators:
            if di.id == tile_id:
                count += 1
        return count

    # ═══════════════════════════════════════════════
    # 軸2: 巡目進行
    # ═══════════════════════════════════════════════

    def _check_turn_advance(self, ctx: Dict,
                             paradigm: str) -> Optional[BoundaryCondition]:
        """終盤防御閾値(12巡)への接近をチェック"""
        turn = ctx.get("turn", 1)

        if paradigm in ("PAR_SPEED", "PAR_VALUE") and 10 <= turn <= 12:
            delta = 12 - turn + 1
            tpl = self._get_template("BOUNDARY_TURN_ADVANCE")
            desc = tpl["template"].format(delta=delta)
            return BoundaryCondition(
                boundary_id="BOUNDARY_TURN_ADVANCE",
                change_axis="巡目進行",
                description=desc,
                check_instruction=tpl["check_instruction"],
                flip_to="PAR_DEF",
                sensitivity=0.80 + (turn - 10) * 0.05
            )
        return None

    # ═══════════════════════════════════════════════
    # 軸3: 他家リーチ
    # ═══════════════════════════════════════════════

    def _check_riichi_addition(self, ctx: Dict,
                                paradigm: str) -> Optional[BoundaryCondition]:
        """リーチ0本→1本の反転リスクをチェック"""
        riichi = ctx.get("riichi", 0)

        if riichi == 0 and paradigm in ("PAR_SPEED", "PAR_VALUE"):
            tpl = self._get_template("BOUNDARY_RIICHI_ADD")
            return BoundaryCondition(
                boundary_id="BOUNDARY_RIICHI_ADD",
                change_axis="他家状態",
                description=tpl["template"],
                check_instruction=tpl["check_instruction"],
                flip_to="PAR_DEF",
                sensitivity=0.65
            )
        return None

    # ═══════════════════════════════════════════════
    # 軸4: 順位圧力
    # ═══════════════════════════════════════════════

    def _check_rank_pressure(self, ctx: Dict,
                              paradigm: str) -> Optional[BoundaryCondition]:
        """点差変動による判断反転をチェック"""
        rank = ctx.get("rank", 1)
        score_diff = ctx.get("score_diff", 0)

        # ラス圏で防御中 → 点差が開けば押しに転換
        if rank >= 3 and paradigm == "PAR_DEF":
            tpl = self._get_template("BOUNDARY_RANK_PRESSURE")
            desc = tpl["template"].format(threshold=8000)
            return BoundaryCondition(
                boundary_id="BOUNDARY_RANK_PRESSURE",
                change_axis="順位圧力",
                description=desc,
                check_instruction=tpl["check_instruction"],
                flip_to="PAR_POS",
                sensitivity=0.55
            )
        return None

    # ═══════════════════════════════════════════════
    # 軸5: 暗刻スジ罠
    # ═══════════════════════════════════════════════

    def _check_anko_suji(self, ctx: Dict,
                          tile: str) -> Optional[BoundaryCondition]:
        """推奨牌がスジだが暗刻スジの罠に該当するかチェック"""
        hand_tiles = ctx.get("hand_tiles", [])
        if not hand_tiles or len(tile) < 2:
            return None

        suit = tile[-1]
        if suit == 'z':
            return None

        try:
            num = int(tile[0])
        except (ValueError, IndexError):
            return None

        # スジの元牌（例: 3mのスジ元は6m）
        suji_sources = {
            1: [4], 2: [5], 3: [6], 4: [1, 7], 5: [2, 8],
            6: [3, 9], 7: [4], 8: [5], 9: [6]
        }
        sources = suji_sources.get(num, [])

        for src_num in sources:
            src_id = f"{src_num}{suit}"
            count = sum(1 for t in hand_tiles
                        if t.id == src_id or
                        (t.suit.value == suit and t.number == src_num))
            if count >= 3:
                tpl = self._get_template("BOUNDARY_ANKO_SUJI_TRAP")
                desc = tpl["template"].format(
                    anko_tile=src_id, suji_tile=tile
                )
                return BoundaryCondition(
                    boundary_id="BOUNDARY_ANKO_SUJI_TRAP",
                    change_axis="手牌構成",
                    description=desc,
                    check_instruction=tpl["check_instruction"],
                    flip_to="PAR_DEF",
                    sensitivity=0.88
                )
        return None

    # ═══════════════════════════════════════════════
    # 軸6: 序盤5切り罠
    # ═══════════════════════════════════════════════

    def _check_early_5_cut(self, ctx: Dict,
                            tile: str) -> Optional[BoundaryCondition]:
        """推奨牌が1/9で、他家が同色の5を序盤に切っているかチェック"""
        if not tile or len(tile) < 2:
            return None

        suit = tile[-1]
        if suit == 'z':
            return None

        try:
            num = int(tile[0])
        except (ValueError, IndexError):
            return None

        if num not in (1, 9):
            return None

        gs = ctx.get("_gs")
        seat = ctx.get("_seat", 0)
        if not gs:
            return None

        five_tile = f"5{suit}"
        for p in gs.players:
            if p.seat == seat:
                continue
            # 序盤（最初の6巡以内）に5を切っているか
            early_discards = p.discards[:6]
            for d in early_discards:
                if d.suit.value == suit and d.number == 5:
                    tpl = self._get_template("BOUNDARY_EARLY_5_CUT")
                    desc = tpl["template"].format(five_tile=five_tile)
                    return BoundaryCondition(
                        boundary_id="BOUNDARY_EARLY_5_CUT",
                        change_axis="他家状態",
                        description=desc,
                        check_instruction=tpl["check_instruction"],
                        flip_to="PAR_DEF",
                        sensitivity=0.85
                    )
        return None

    # ═══════════════════════════════════════════════
    # ヘルパー
    # ═══════════════════════════════════════════════

    def _get_template(self, boundary_id: str) -> Dict:
        """カタログから境界条件テンプレートを取得"""
        for bc in self.catalog:
            if bc["id"] == boundary_id:
                return bc
        return {"template": "", "check_instruction": "", "flip_to": "PAR_DEF"}
