"""
server/engines/output_formatter.py
4層出力フォーマッター

4エンジン(XAI/戦略/解釈/読み)の出力 + パラダイム + 境界条件を統合し、
「実戦で強くなる」ための4層構造に変換する。

出力4層:
  ① 定性フレームワーク — 思考の型・パラダイム・ヒューリスティック
  ② 実践チェックリスト — YES/NO形式、≤3項目、10秒以内で実行可能
  ③ 定量バックアップ  — 鳳凰位参照（実データ注入待ち）
  ④ 境界条件         — 盤面微差による判断反転の可視化
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════
# 出力データ構造
# ════════════════════════════════════════════

@dataclass
class QualitativeLayer:
    """① 定性フレームワーク"""
    paradigm_id: str
    paradigm_name: str
    core_principle: str
    heuristics: List[str]
    memory_phrase: str
    triggers: List[str]
    meta_question: str

    def to_dict(self) -> Dict:
        return {
            "paradigm": self.paradigm_id,
            "paradigm_name": self.paradigm_name,
            "principle": self.core_principle,
            "heuristics": self.heuristics,
            "memory_phrase": self.memory_phrase,
            "triggers": self.triggers,
            "meta_question": self.meta_question,
        }


@dataclass
class ChecklistItem:
    """チェックリストの1項目"""
    question: str
    answer: str   # "YES" / "NO" / "確認済み"
    detail: str = ""

    def to_dict(self) -> Dict:
        d = {"q": self.question, "a": self.answer}
        if self.detail:
            d["detail"] = self.detail
        return d


@dataclass
class ChecklistLayer:
    """② 実践チェックリスト（≤3項目）"""
    items: List[ChecklistItem] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {"items": [i.to_dict() for i in self.items[:3]]}


@dataclass
class QuantitativeLayer:
    """③ 定量バックアップ（鳳凰位参照）"""
    available: bool = False
    memory_anchor: str = ""
    stat_id: str = ""
    context: str = ""
    disclaimer: str = "この数値は思考の代替ではなく、判断の検証材料です"

    def to_dict(self) -> Dict:
        if not self.available:
            return {"available": False,
                    "note": "定量データ未注入。鳳凰位牌譜解析後に更新予定"}
        return {
            "available": True,
            "memory_anchor": self.memory_anchor,
            "stat_id": self.stat_id,
            "context": self.context,
            "disclaimer": self.disclaimer,
        }


@dataclass
class BoundaryLayer:
    """④ 境界条件"""
    has_boundary: bool = False
    axis: str = ""
    description: str = ""
    check_instruction: str = ""
    flip_to: str = ""

    def to_dict(self) -> Dict:
        if not self.has_boundary:
            return {"has_boundary": False}
        return {
            "has_boundary": True,
            "axis": self.axis,
            "description": self.description,
            "check": self.check_instruction,
            "flip_to": self.flip_to,
        }


@dataclass
class FourLayerOutput:
    """4層統合出力"""
    tile: str
    qualitative: QualitativeLayer
    checklist: ChecklistLayer
    quantitative: QuantitativeLayer
    boundary: BoundaryLayer

    def to_dict(self) -> Dict:
        return {
            "tile": self.tile,
            "qualitative": self.qualitative.to_dict(),
            "checklist": self.checklist.to_dict(),
            "quantitative": self.quantitative.to_dict(),
            "boundary": self.boundary.to_dict(),
        }


# ════════════════════════════════════════════
# フォーマッター本体
# ════════════════════════════════════════════

class OutputFormatter:
    """
    4エンジンの出力をユーザー学習最適化された4層構造に変換する。

    入力:
      - paradigm_result: パラダイムエンジンの出力
      - strategy_result: 戦略判断エンジンの出力
      - reading_result: 読みエンジンの出力
      - boundary_result: 境界条件エンジンの出力
      - ctx: 盤面コンテキスト

    出力:
      - FourLayerOutput: 4層構造化出力
    """

    def __init__(self, quant_path: str = "server/rules/quantitative_catalog.json"):
        self.quant_catalog = self._load_quant(quant_path)

    def _load_quant(self, path: str) -> Dict:
        if not os.path.exists(path):
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def format(self, tile: str, paradigm_result, strategy_result,
               reading_result, boundary_result, ctx: Dict) -> FourLayerOutput:
        """4層出力を生成"""

        # ① 定性フレームワーク
        qualitative = self._build_qualitative(paradigm_result)

        # ② 実践チェックリスト
        checklist = self._build_checklist(
            tile, paradigm_result, strategy_result, reading_result, ctx
        )

        # ③ 定量バックアップ
        quantitative = self._build_quantitative(
            tile, paradigm_result, ctx
        )

        # ④ 境界条件
        boundary = self._build_boundary(boundary_result)

        return FourLayerOutput(
            tile=tile,
            qualitative=qualitative,
            checklist=checklist,
            quantitative=quantitative,
            boundary=boundary,
        )

    # ═══════════════════════════════════════════════
    # Layer 1: 定性フレームワーク
    # ═══════════════════════════════════════════════

    def _build_qualitative(self, paradigm) -> QualitativeLayer:
        """パラダイムエンジンの結果を定性フレームワークに変換"""
        return QualitativeLayer(
            paradigm_id=paradigm.primary,
            paradigm_name=paradigm.name_ja,
            core_principle=paradigm.core_principle,
            heuristics=paradigm.heuristics[:3],
            memory_phrase=paradigm.memory_phrase,
            triggers=paradigm.triggers[:3],
            meta_question=paradigm.meta_question,
        )

    # ═══════════════════════════════════════════════
    # Layer 2: 実践チェックリスト
    # ═══════════════════════════════════════════════

    def _build_checklist(self, tile: str, paradigm, strategy,
                          reading, ctx: Dict) -> ChecklistLayer:
        """
        盤面情報のみで構成されたYES/NO確認項目を生成（≤3項目）。
        計算・確率推論は一切含まない。肉眼で確認可能な情報のみ使用。
        """
        items = []
        pid = paradigm.primary

        if pid == "PAR_SPEED":
            items = self._checklist_speed(tile, ctx)
        elif pid == "PAR_VALUE":
            items = self._checklist_value(tile, ctx)
        elif pid == "PAR_DEF":
            items = self._checklist_defense(tile, ctx)
        elif pid == "PAR_READ":
            items = self._checklist_read(tile, ctx, reading)
        elif pid == "PAR_POS":
            items = self._checklist_position(tile, ctx)
        else:  # PAR_FLEX
            items = self._checklist_flex(tile, ctx)

        return ChecklistLayer(items=items[:3])

    def _checklist_speed(self, tile: str, ctx: Dict) -> List[ChecklistItem]:
        """速度軸のチェックリスト"""
        items = []
        shanten = ctx.get("shanten", 6)
        ryanmen = ctx.get("ryanmen_count", 0)
        riichi = ctx.get("riichi", 0)

        # Q1: 向聴数は減るか？
        items.append(ChecklistItem(
            question=f"{tile}を切ると向聴数が減るか？",
            answer="YES" if shanten >= 1 else "確認中",
            detail=f"現在の向聴数: {shanten}"
        ))

        # Q2: 両面待ちは残るか?
        items.append(ChecklistItem(
            question="切った後に両面待ちが残るか？",
            answer="YES" if ryanmen >= 2 else "NO",
            detail=f"現在の両面候補: {ryanmen}つ"
        ))

        # Q3: 安全度の確認
        genbutsu = ctx.get("genbutsu_tiles", [])
        is_safe = tile in genbutsu
        items.append(ChecklistItem(
            question=f"{tile}は他家に対して高危険ではないか？",
            answer="安全" if is_safe else "確認済み（高危険ではない）"
                   if riichi == 0 else "注意（リーチ者あり）",
        ))

        return items

    def _checklist_value(self, tile: str, ctx: Dict) -> List[ChecklistItem]:
        """打点軸のチェックリスト"""
        items = []
        current_han = ctx.get("current_han", 0)
        potential_han = ctx.get("potential_han", 0)
        yakuhai = ctx.get("has_yakuhai_pair", False)

        items.append(ChecklistItem(
            question=f"{tile}を切ると翻数が減るか？",
            answer="NO（翻数維持）" if potential_han >= 3 else "YES（要注意）",
            detail=f"現在{current_han}翻→潜在{potential_han}翻"
        ))

        items.append(ChecklistItem(
            question="役牌対子・ドラは保持できているか？",
            answer="YES" if yakuhai or ctx.get("dora_count", 0) > 0
                   else "NO",
        ))

        items.append(ChecklistItem(
            question="満貫（8000点）到達は可能か？",
            answer="YES" if potential_han >= 5 else "NO",
            detail=f"潜在{potential_han}翻"
        ))

        return items

    def _checklist_defense(self, tile: str, ctx: Dict) -> List[ChecklistItem]:
        """防御軸のチェックリスト"""
        items = []
        genbutsu = ctx.get("genbutsu_tiles", [])
        riichi = ctx.get("riichi", 0)

        items.append(ChecklistItem(
            question=f"{tile}はリーチ者の現物か？",
            answer="YES（現物）" if tile in genbutsu else "NO",
        ))

        if tile not in genbutsu:
            # 壁・スジの確認
            reading_map = ctx.get("reading_danger_map", {})
            danger = reading_map.get(tile, 0.5)
            if danger <= 0.10:
                safety = "壁スジ（安全度A）"
            elif danger <= 0.25:
                safety = "ワンチャンス（安全度B）"
            elif danger <= 0.45:
                safety = "スジ（安全度C）"
            else:
                safety = "無スジ（安全度D）"
            items.append(ChecklistItem(
                question=f"{tile}の安全度ランクは？",
                answer=safety,
            ))

        items.append(ChecklistItem(
            question="現物を切っても聴牌が遠ざからないか？",
            answer="YES（許容範囲）" if ctx.get("shanten", 6) >= 2
                   else "注意（聴牌間近）",
        ))

        return items

    def _checklist_read(self, tile: str, ctx: Dict,
                         reading) -> List[ChecklistItem]:
        """読み軸のチェックリスト"""
        items = []
        override_flags = ctx.get("reading_override_flags", [])

        items.append(ChecklistItem(
            question="読みエンジンが特別な警告を発しているか？",
            answer=f"YES（{len(override_flags)}件）" if override_flags
                   else "NO",
        ))

        reading_map = ctx.get("reading_danger_map", {})
        tile_danger = reading_map.get(tile, 0.5)
        items.append(ChecklistItem(
            question=f"{tile}は読みによる高危険牌か？",
            answer="YES（高危険）" if tile_danger >= 0.65
                   else "NO",
        ))

        items.append(ChecklistItem(
            question="他家の副露パターンに染め手の兆候はあるか？",
            answer="YES" if any("HONITSU" in f for f in override_flags)
                   else "NO",
        ))

        return items

    def _checklist_position(self, tile: str, ctx: Dict) -> List[ChecklistItem]:
        """順位圧力軸のチェックリスト"""
        items = []
        rank = ctx.get("rank", 1)
        score_diff = ctx.get("score_diff", 0)

        items.append(ChecklistItem(
            question="和了して順位が上がるか？",
            answer="YES" if rank >= 2 else "NO（既にトップ）",
            detail=f"現在{rank}位（点差{score_diff:+d}点）"
        ))

        items.append(ChecklistItem(
            question="放銃した場合、順位は下がるか？",
            answer="YES（注意）" if rank <= 2 and score_diff < 8000
                   else "NO（影響小）",
        ))

        items.append(ChecklistItem(
            question="トップ且つ点差十分で、守り切れる局面か？",
            answer="YES" if rank == 1 and score_diff >= 4000
                   else "NO",
        ))

        return items

    def _checklist_flex(self, tile: str, ctx: Dict) -> List[ChecklistItem]:
        """柔軟性軸のチェックリスト"""
        return [
            ChecklistItem(
                question="今の判断は固定観念に基づいていないか？",
                answer="自己確認",
            ),
            ChecklistItem(
                question="盤面に異常なパターンが見えるか？",
                answer="確認中",
            ),
            ChecklistItem(
                question="第二選択肢は何か？",
                answer="検討中",
            ),
        ]

    # ═══════════════════════════════════════════════
    # Layer 3: 定量バックアップ
    # ═══════════════════════════════════════════════

    def _build_quantitative(self, tile: str, paradigm,
                             ctx: Dict) -> QuantitativeLayer:
        """
        定量データカタログから該当統計を検索。
        実データが未注入の場合はavailable=Falseを返す。
        """
        stats = self.quant_catalog.get("contextual_statistics", [])
        presentation = self.quant_catalog.get("presentation_rules", {})

        # パラダイム別に最も関連する統計を検索
        pid = paradigm.primary
        stat_map = {
            "PAR_SPEED": "STAT_SPEED_MID_CHOICE",
            "PAR_DEF": "STAT_BETAORI_PRIORITY",
            "PAR_VALUE": "STAT_SPEED_MID_CHOICE",
            "PAR_READ": "STAT_5CUT_19_RISK",
            "PAR_POS": "STAT_SPEED_MID_CHOICE",
            "PAR_FLEX": "STAT_SPEED_MID_CHOICE",
        }
        target_id = stat_map.get(pid, "STAT_SPEED_MID_CHOICE")

        matched = None
        for s in stats:
            if s.get("stat_id") == target_id:
                matched = s
                break

        if not matched or matched.get("reliability_tier") == "UNVERIFIED":
            return QuantitativeLayer(
                available=False,
                disclaimer=presentation.get("disclaimer", "")
            )

        # 実データが注入されている場合
        pe = matched.get("point_estimate")
        ci = matched.get("confidence_interval_95")
        n = matched.get("sample_size")

        ordinal = self._to_ordinal(pe, presentation)
        anchor_tpl = presentation.get("memory_anchor_template", "")
        anchor = anchor_tpl.format(
            context=matched.get("description", ""),
            ordinal=ordinal
        )

        return QuantitativeLayer(
            available=True,
            memory_anchor=anchor,
            stat_id=target_id,
            context=matched.get("description", ""),
            disclaimer=presentation.get("disclaimer", ""),
        )

    def _to_ordinal(self, value: Optional[float], rules: Dict) -> str:
        """数値を序数スケールに変換（記憶定着支援）"""
        if value is None:
            return "不明"
        ranges = rules.get("ordinal_scale", {}).get("ranges", {})
        if value >= 0.90:
            return "ほぼ確実"
        elif value >= 0.70:
            return "約7-9割"
        elif value >= 0.50:
            return "約半数〜7割"
        elif value >= 0.30:
            return "約3-5割"
        elif value >= 0.10:
            return "低い"
        else:
            return "ごく稀"

    # ═══════════════════════════════════════════════
    # Layer 4: 境界条件
    # ═══════════════════════════════════════════════

    def _build_boundary(self, boundary_result) -> BoundaryLayer:
        """境界条件検出結果をLayer4に変換"""
        if not boundary_result:
            return BoundaryLayer(has_boundary=False)

        return BoundaryLayer(
            has_boundary=True,
            axis=boundary_result.change_axis,
            description=boundary_result.description,
            check_instruction=boundary_result.check_instruction,
            flip_to=boundary_result.flip_to,
        )
