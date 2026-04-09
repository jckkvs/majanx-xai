"""
server/engines/paradigm_engine.py
6大判断パラダイム切替エンジン

盤面コンテキストから制約階層(L1〜L4)をスキャンし、
最も強い制約に基づく第一パラダイムを決定する。

パラダイム:
  PAR_SPEED — 速度軸（受入最大化）
  PAR_VALUE — 打点軸（翻数最大化）
  PAR_DEF   — 防御軸（放銃回避）
  PAR_READ  — 読み軸（他家逆推論）
  PAR_POS   — 順位圧力軸（順位点最適化）
  PAR_FLEX  — 柔軟性軸（固定概念排除）

制約階層:
  L1: 物理的制約（現物有無/枚数枯れ/リーチ宣言）→ 全軸を上書き
  L2: 時間的制約（巡目進行）→ 打点・読みを上書き
  L3: 状況的制約（順位/点差）→ 速度・打点を上書き
  L4: 情報的制約（他家打牌/副露パターン）→ 固定定石を上書き
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParadigmResult:
    """パラダイムエンジンの構造化出力"""
    primary: str            # 第一パラダイムID
    secondary: str          # 第二パラダイム（切替先候補）
    constraint_level: str   # L1/L2/L3/L4
    heuristics: List[str]   # 実践ヒューリスティック（計算不要）
    memory_phrase: str      # 記憶用フレーズ
    triggers: List[str]     # 活性化した認知トリガー
    core_principle: str     # 核心原則
    meta_question: str      # メタ認知問い（L4）
    name_ja: str            # 日本語名

    def to_dict(self) -> Dict:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "constraint_level": self.constraint_level,
            "heuristics": self.heuristics[:3],
            "memory_phrase": self.memory_phrase,
            "triggers": self.triggers[:3],
            "core_principle": self.core_principle,
            "meta_question": self.meta_question,
            "name_ja": self.name_ja,
        }


class ParadigmEngine:
    """
    盤面コンテキストから最適なパラダイムを決定する。

    制約をスキャンし、最も強い制約階層に対応するパラダイムを
    第一軸として活性化する。他の軸は「参考情報」へ降格。
    """

    def __init__(self, catalog_path: str = "server/rules/paradigm_catalog.json"):
        self.catalog = self._load_catalog(catalog_path)

    def _load_catalog(self, path: str) -> List[Dict]:
        if not os.path.exists(path):
            logger.warning(f"Paradigm catalog not found: {path}")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def determine(self, ctx: Dict) -> ParadigmResult:
        """盤面コンテキストからパラダイムを決定"""

        # ── L1: 物理的制約（最高優先度） ──
        l1_result = self._check_l1_physical(ctx)
        if l1_result:
            return l1_result

        # ── L2: 時間的制約 ──
        l2_result = self._check_l2_temporal(ctx)

        # ── L3: 状況的制約 ──
        l3_result = self._check_l3_situational(ctx)

        # ── L4: 情報的制約 ──
        l4_result = self._check_l4_informational(ctx)

        # 候補から最強制約を選択
        candidates = [r for r in [l2_result, l3_result, l4_result] if r]
        if not candidates:
            return self._build_result("PAR_SPEED", "PAR_DEF", "L2",
                                      ["序盤・標準形"])

        # 制約階層順で最強を選択（L2 > L3 > L4）
        level_priority = {"L1": 0, "L2": 1, "L3": 2, "L4": 3}
        candidates.sort(key=lambda r: level_priority.get(r.constraint_level, 9))
        return candidates[0]

    # ═══════════════════════════════════════════════
    # L1: 物理的制約
    # ═══════════════════════════════════════════════

    def _check_l1_physical(self, ctx: Dict) -> Optional[ParadigmResult]:
        """
        L1は全軸を上書きする最強制約。

        条件:
        - 他家リーチ≥2本 → PAR_DEF（即オリ）
        - 他家リーチ1本 + 自手が低打点(≤2翻) + 現物あり → PAR_DEF
        - 全牌が高危険 → PAR_DEF
        """
        riichi = ctx.get("riichi", 0)
        current_han = ctx.get("current_han", 0)
        has_genbutsu = ctx.get("is_genbutsu", False)

        # 2本以上リーチ → 無条件で防御
        if riichi >= 2:
            return self._build_result(
                "PAR_DEF", "PAR_FLEX", "L1",
                [f"他家{riichi}本リーチ", "無条件オリ"]
            )

        # 1本リーチ + 低打点 + 現物あり
        if riichi >= 1 and current_han <= 2 and has_genbutsu:
            return self._build_result(
                "PAR_DEF", "PAR_READ", "L1",
                ["他家リーチ", f"自手{current_han}翻（低打点）", "現物あり"]
            )

        return None

    # ═══════════════════════════════════════════════
    # L2: 時間的制約
    # ═══════════════════════════════════════════════

    def _check_l2_temporal(self, ctx: Dict) -> Optional[ParadigmResult]:
        """
        巡目進行による速度→防御の自然遷移。

        序盤(1-5巡): PAR_SPEED（形を作る）
        中盤(6-11巡): PAR_SPEED or PAR_VALUE（受入・打点のバランス）
        終盤(12巡〜): PAR_DEF（安全優先）
        """
        turn = ctx.get("turn", 1)
        shanten = ctx.get("shanten", 6)
        ryanmen = ctx.get("ryanmen_count", 0)

        if turn >= 13:
            # 終盤 → 防御優先
            secondary = "PAR_POS" if ctx.get("rank", 1) >= 3 else "PAR_SPEED"
            return self._build_result(
                "PAR_DEF", secondary, "L2",
                [f"{turn}巡目（終盤）", "安全優先へ移行"]
            )

        if turn <= 5:
            # 序盤 → 速度（形を作る）
            return self._build_result(
                "PAR_SPEED", "PAR_VALUE", "L2",
                [f"{turn}巡目（序盤）", "形作り優先"]
            )

        # 中盤(6-12) → 向聴数/両面数に応じて分岐
        if shanten <= 1 and ryanmen >= 2:
            return self._build_result(
                "PAR_SPEED", "PAR_VALUE", "L2",
                [f"{turn}巡目", f"向聴数{shanten}", "聴牌間近・速度維持"]
            )

        potential_han = ctx.get("potential_han", 0)
        if potential_han >= 5 or ctx.get("has_yakuhai_pair", False):
            return self._build_result(
                "PAR_VALUE", "PAR_SPEED", "L2",
                [f"{turn}巡目", f"潜在{potential_han}翻", "打点構築可能"]
            )

        return self._build_result(
            "PAR_SPEED", "PAR_DEF", "L2",
            [f"{turn}巡目（中盤）", "受入最大化"]
        )

    # ═══════════════════════════════════════════════
    # L3: 状況的制約
    # ═══════════════════════════════════════════════

    def _check_l3_situational(self, ctx: Dict) -> Optional[ParadigmResult]:
        """
        順位・点差・親番による戦略最適化。
        """
        rank = ctx.get("rank", 1)
        score_diff = ctx.get("score_diff", 0)
        is_dealer = ctx.get("dealer_status", False)

        # トップ + 十分な点差 → 守り切り
        if rank == 1 and score_diff >= 4000:
            return self._build_result(
                "PAR_POS", "PAR_DEF", "L3",
                [f"トップ（+{score_diff}点）", "守り切り優先"]
            )

        # ラス目 → 押し
        if rank == 4:
            shanten = ctx.get("shanten", 6)
            if shanten <= 1:
                return self._build_result(
                    "PAR_POS", "PAR_SPEED", "L3",
                    [f"ラス目（{score_diff}点差）", f"向聴数{shanten}", "逆転狙い"]
                )

        # 親番 + 高打点 → 打点重視
        if is_dealer and ctx.get("potential_han", 0) >= 3:
            return self._build_result(
                "PAR_VALUE", "PAR_SPEED", "L3",
                ["親番", f"潜在{ctx.get('potential_han', 0)}翻", "連荘狙い"]
            )

        return None

    # ═══════════════════════════════════════════════
    # L4: 情報的制約
    # ═══════════════════════════════════════════════

    def _check_l4_informational(self, ctx: Dict) -> Optional[ParadigmResult]:
        """
        他家の打牌・副露パターンからの逆推論。
        読みエンジンのoverride_flagsが存在する場合に活性化。
        """
        override_flags = ctx.get("reading_override_flags", [])
        reading_danger = ctx.get("reading_danger_map", {})

        # 染め手(HONITSU)検知
        honitsu_flags = [f for f in override_flags if "HONITSU_SUIT" in f]
        if honitsu_flags:
            suit = honitsu_flags[0].split(":")[-1]
            return self._build_result(
                "PAR_READ", "PAR_DEF", "L4",
                [f"他家の{suit}スート集中（混一色疑い）",
                 "染め手読みによる安全牌調整"]
            )

        # スジ信頼度低下検知
        suji_scale_flags = [f for f in override_flags
                            if "SUJI_CONFIDENCE_SCALE" in f]
        if suji_scale_flags:
            return self._build_result(
                "PAR_READ", "PAR_DEF", "L4",
                ["スジ罠検知", "スジ信頼度低下"]
            )

        # 高危険牌の大量検知
        high_danger_count = sum(1 for v in reading_danger.values() if v >= 0.7)
        if high_danger_count >= 5:
            return self._build_result(
                "PAR_READ", "PAR_DEF", "L4",
                [f"高危険牌{high_danger_count}枚検出", "読みに基づく選択的防御"]
            )

        return None

    # ═══════════════════════════════════════════════
    # ヘルパー
    # ═══════════════════════════════════════════════

    def _build_result(self, primary_id: str, secondary_id: str,
                      level: str, triggers: List[str]) -> ParadigmResult:
        """パラダイムカタログからResultを構築"""
        primary_def = self._get_paradigm(primary_id)
        secondary_def = self._get_paradigm(secondary_id)

        return ParadigmResult(
            primary=primary_id,
            secondary=secondary_id,
            constraint_level=level,
            heuristics=primary_def.get("heuristics", []),
            memory_phrase=primary_def.get("memory_phrase", ""),
            triggers=triggers,
            core_principle=primary_def.get("core_principle", ""),
            meta_question=primary_def.get("meta_question", ""),
            name_ja=primary_def.get("name_ja", primary_id),
        )

    def _get_paradigm(self, pid: str) -> Dict:
        """カタログからパラダイム定義を取得"""
        for p in self.catalog:
            if p["id"] == pid:
                return p
        return {"id": pid, "name_ja": pid, "heuristics": [],
                "memory_phrase": "", "core_principle": "",
                "meta_question": ""}
