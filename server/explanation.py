"""
打牌推奨 & 理由解説エンジン (強化版)
Implements: F-010 | 「何を切るべきか」「なぜか」を解説する機能

AdvancedCPUPlayer の内部判断を活用し、以下を構造化して提示:
- 牌効率分析 (shanten + ukeire + 良形率)
- 期待打点推定
- 守備安全度 (現物/筋/壁)
- 押し引き判定根拠 (攻撃EV vs 放銃リスク)
- 場況分析結果
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mahjong.shanten import Shanten

from .models import (
    Tile, TileSuit, Wind, GameState, PlayerState,
    MeldType, create_full_tileset,
)
from .engine import GameEngine
from .advanced_ai import (
    AdvancedCPUPlayer, OffenseEngine, DefenseEngine,
    PushFoldJudge, SituationAnalyzer,
    DiscardCandidate, AIDecision, DecisionReason,
)


# ============================================================
# 評価結果のデータ構造
# ============================================================

@dataclass
class TileEvaluation:
    """1枚の牌を捨てた場合の評価"""
    tile: Tile
    shanten_after: int
    ukeire: int
    ukeire_tiles: list[Tile]
    danger_score: float
    value_score: float
    total_score: float
    discard_score: float
    good_shape_ratio: float = 0.0
    expected_points: float = 0.0
    safety_score: float = 1.0


@dataclass
class DiscardReason:
    """打牌理由の構造化データ"""
    category: str
    importance: float
    description: str
    detail: Optional[str] = None


@dataclass
class DiscardRecommendation:
    """打牌推奨の最終結果"""
    recommended_tile: Tile
    all_evaluations: list[TileEvaluation]
    reasons: list[DiscardReason]
    summary: str
    detailed_explanation: str
    shanten_current: int
    is_tenpai: bool
    waiting_tiles: list[Tile]
    push_fold_state: str = "push"
    attack_ev: float = 0.0
    defense_risk: float = 0.0
    situation_summary: str = ""


# ============================================================
# 解説エンジン (強化版)
# ============================================================

class ExplanationEngine:
    """
    打牌の推奨と理由を生成するエンジン。
    AdvancedCPUPlayer の内部ロジックを活用。

    評価軸:
    1. 牌効率 (shanten + ukeire + 良形率)
    2. 期待打点 (役種・ドラ・翻数による推定)
    3. 守備安全度 (現物/筋/壁/巡目)
    4. 押し引き判定 (攻撃EV vs 放銃リスク)
    5. 場況 (巡目・点差・残り枚数)
    """

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.shanten_calc = Shanten()
        # 内部で使うサブエンジン群
        self._offense = OffenseEngine(engine)
        self._defense = DefenseEngine(engine)
        self._push_fold = PushFoldJudge(engine)
        self._situation = SituationAnalyzer(engine)

    def analyze(self, player_seat: int) -> DiscardRecommendation:
        """手牌を分析し、打牌推奨と理由を生成"""
        st = self.engine.state
        player = st.players[player_seat]
        hand = player.hand

        if len(hand) < 2 or len(hand) % 3 != 2:
            return self._empty_recommendation(hand)

        # 見えている牌を収集
        visible = self._collect_visible_tiles()

        # 現在の向聴数
        tiles_34 = self.engine._hand_to_34(hand)
        current_shanten = self.shanten_calc.calculate_shanten(tiles_34)

        # 1. 全候補の攻撃評価
        candidates = self._offense.evaluate_all_discards(player, visible)

        # 2. 守備評価
        safety_map = self._defense.calc_safety_scores(player, visible)

        # 3. 場況分析
        sit = self._situation.analyze(player_seat)

        # 4. 押し引き判定
        best_offense = max(candidates, key=lambda x: x.offense_score) if candidates else None
        pf_decision, attack_ev, defense_risk, pf_reasons = "push", 0.0, 0.0, []
        if best_offense:
            pf_decision, attack_ev, defense_risk, pf_reasons = self._push_fold.judge(
                player, current_shanten, best_offense.ukeire,
                best_offense.expected_points, safety_map, sit
            )

        # 5. 各候補に守備スコアを統合して最終評価
        for c in candidates:
            key = (c.tile.suit, c.tile.number, c.tile.is_red)
            c.safety_score = safety_map.get(key, 0.5)
            c.defense_score = c.safety_score * 1000

            if pf_decision == "fold":
                c.final_score = c.defense_score * 10 - abs(c.offense_score) * 0.01
            elif pf_decision == "neutral":
                c.final_score = c.offense_score * 0.4 + c.defense_score * 0.6
            else:
                c.final_score = c.offense_score * 0.85 + c.defense_score * 0.15

        candidates.sort(key=lambda x: x.final_score, reverse=True)

        # ★ 候補を1〜3択に絞り込む
        # 向聴数が上がる牌は除外し、上位からスコア差で絞る
        viable = [c for c in candidates if c.shanten_after <= current_shanten]
        if not viable:
            viable = candidates[:1]

        narrowed = [viable[0]]  # 最善手は必ず含む
        if len(viable) >= 2:
            top_score = viable[0].final_score
            for c in viable[1:]:
                # スコアが最善手の70%以内なら選択肢に入れる(最大2つ追加)
                if len(narrowed) >= 3:
                    break
                score_ratio = c.final_score / top_score if top_score != 0 else 0
                # 向聴数が同じで受入が異なる or 安全度が大きく違う場合は候補
                is_different = (c.shanten_after != narrowed[0].shanten_after or
                               abs(c.ukeire - narrowed[0].ukeire) >= 2 or
                               abs(c.safety_score - narrowed[0].safety_score) >= 0.2)
                if is_different or score_ratio > 0.5:
                    narrowed.append(c)

        # TileEvaluation形式に変換(絞り込み済み候補のみ)
        evaluations: list[TileEvaluation] = []
        for c in narrowed:
            evaluations.append(TileEvaluation(
                tile=c.tile,
                shanten_after=c.shanten_after,
                ukeire=c.ukeire,
                ukeire_tiles=c.ukeire_tiles,
                danger_score=1.0 - c.safety_score,
                value_score=min(1.0, c.expected_points / 8000),
                total_score=c.offense_score,
                discard_score=c.final_score,
                good_shape_ratio=c.good_shape_ratio,
                expected_points=c.expected_points,
                safety_score=c.safety_score,
            ))

        best = evaluations[0]

        # 理由生成
        reasons = self._generate_reasons(
            best, evaluations, player, current_shanten,
            pf_decision, attack_ev, defense_risk, pf_reasons, sit
        )

        # テキスト生成
        summary = self._generate_summary(best, current_shanten, player, pf_decision)
        detailed = self._generate_detailed_explanation(
            best, evaluations, reasons, current_shanten, player,
            pf_decision, attack_ev, defense_risk, sit
        )

        # テンパイ時の待ち牌
        waiting = []
        is_tenpai = current_shanten == 0
        if is_tenpai:
            waiting = self.engine.get_waiting_tiles(player_seat)

        return DiscardRecommendation(
            recommended_tile=best.tile,
            all_evaluations=evaluations,
            reasons=reasons,
            summary=summary,
            detailed_explanation=detailed,
            shanten_current=current_shanten,
            is_tenpai=is_tenpai,
            waiting_tiles=waiting,
            push_fold_state=pf_decision,
            attack_ev=attack_ev,
            defense_risk=defense_risk,
            situation_summary=self._build_situation_summary(sit),
        )

    # ============================================================
    # 理由生成 (強化版)
    # ============================================================

    def _generate_reasons(self, best: TileEvaluation,
                          all_evals: list[TileEvaluation],
                          player: PlayerState,
                          current_shanten: int,
                          pf_decision: str,
                          attack_ev: float,
                          defense_risk: float,
                          pf_reasons: list,
                          sit: dict) -> list[DiscardReason]:
        """推奨理由を構造化して生成"""
        reasons: list[DiscardReason] = []
        tile = best.tile
        st = self.engine.state

        # (1) 押し引き判定結果
        pf_label = {"push": "🔥 攻撃", "fold": "🛡️ 守備(オリ)", "neutral": "🔄 回し打ち"}
        reasons.append(DiscardReason(
            category="戦略",
            importance=1.0,
            description=f"判断: {pf_label.get(pf_decision, pf_decision)}",
            detail=f"攻撃EV={attack_ev:.0f} vs 防御リスク={defense_risk:.0f}"
                   if sit.get("has_riichi") else "リーチ者なし・攻撃優先"
        ))

        # (2) 向聴数
        if best.shanten_after < current_shanten:
            reasons.append(DiscardReason(
                category="牌効率",
                importance=0.95,
                description=f"向聴数前進！({current_shanten}→{best.shanten_after}向聴)",
                detail=f"{tile.name_ja}を切ると手が進みます。"
            ))
        elif best.shanten_after == current_shanten:
            reasons.append(DiscardReason(
                category="牌効率",
                importance=0.7,
                description=f"向聴数維持（{current_shanten}向聴）",
            ))

        # (3) 受入枚数
        if best.ukeire > 0:
            others_ukeire = [e.ukeire for e in all_evals
                             if e.tile != tile and e.shanten_after <= current_shanten]
            max_other = max(others_ukeire) if others_ukeire else 0
            if best.ukeire >= max_other:
                reasons.append(DiscardReason(
                    category="受入",
                    importance=0.85,
                    description=f"受入{best.ukeire}枚（最大）",
                    detail=f"有効牌: {', '.join(t.name_ja for t in best.ukeire_tiles[:6])}"
                           + (f"...他{len(best.ukeire_tiles)-6}種"
                              if len(best.ukeire_tiles) > 6 else ""),
                ))

        # (4) 期待打点
        if best.expected_points > 0:
            reasons.append(DiscardReason(
                category="打点",
                importance=0.6,
                description=f"期待打点: 約{best.expected_points:.0f}点",
            ))

        # (5) 安全度 (リーチ者がいる場合)
        if sit.get("has_riichi"):
            if best.safety_score >= 0.95:
                reasons.append(DiscardReason(
                    category="守備",
                    importance=0.9,
                    description=f"🔒 {tile.name_ja}は現物（安全牌）",
                    detail="リーチ者の捨て牌にある牌のため、放銃リスク0%です。"
                ))
            elif best.safety_score >= 0.7:
                reasons.append(DiscardReason(
                    category="守備",
                    importance=0.7,
                    description=f"🛡️ {tile.name_ja}は筋/壁で比較的安全(安全度{best.safety_score*100:.0f}%)",
                ))
            elif best.safety_score < 0.4:
                reasons.append(DiscardReason(
                    category="守備",
                    importance=0.5,
                    description=f"⚠ {tile.name_ja}はやや危険(安全度{best.safety_score*100:.0f}%)",
                    detail="攻撃価値を考慮して押しています。"
                ))

        # (6) 不要牌の理由
        if tile.is_honor and not tile.is_dragon:
            relative_seat = (player.seat - st.dealer) % 4
            is_own = tile.number == relative_seat + 1
            is_round = tile.number == st.round_wind.value + 1
            if not is_own and not is_round:
                count = sum(1 for t in player.hand
                           if t.suit == tile.suit and t.number == tile.number)
                if count == 1:
                    reasons.append(DiscardReason(
                        category="不要牌",
                        importance=0.6,
                        description=f"{tile.name_ja}は客風牌（役にならない字牌）",
                        detail="1枚では面子にならず、残す価値が低い。"
                    ))

        if tile.is_terminal and not tile.is_red:
            neighbors = [t for t in player.hand
                        if t.suit == tile.suit and abs(t.number - tile.number) <= 2
                        and t != tile]
            if not neighbors:
                reasons.append(DiscardReason(
                    category="不要牌",
                    importance=0.55,
                    description=f"{tile.name_ja}は孤立端牌",
                    detail="周囲に関連牌がなく、順子を作りにくい。"
                ))

        # (7) ドラ注意
        if tile.is_red:
            reasons.append(DiscardReason(
                category="注意",
                importance=0.4,
                description=f"⚠ 赤ドラ({tile.name_ja})を切ります",
                detail="打点が1翻下がりますが、形の良さを優先。"
            ))
        for dora in st.dora_tiles:
            if tile.suit == dora.suit and tile.number == dora.number:
                reasons.append(DiscardReason(
                    category="注意",
                    importance=0.45,
                    description=f"⚠ {tile.name_ja}はドラです",
                ))

        reasons.sort(key=lambda r: r.importance, reverse=True)
        return reasons

    # ============================================================
    # テキスト生成
    # ============================================================

    def _generate_summary(self, best: TileEvaluation, current_shanten: int,
                          player: PlayerState, pf_decision: str) -> str:
        shanten_names = {
            -1: "和了形", 0: "テンパイ", 1: "イーシャンテン",
            2: "リャンシャンテン", 3: "サンシャンテン",
        }
        name = shanten_names.get(current_shanten, f"{current_shanten}向聴")
        tile = best.tile

        pf_icon = {"push": "🔥", "fold": "🛡️", "neutral": "🔄"}.get(pf_decision, "")

        if pf_decision == "fold":
            return f"{pf_icon}【オリ】{tile.name_ja} 切り → 安全度{best.safety_score*100:.0f}%"
        elif best.shanten_after < current_shanten:
            return f"{pf_icon}【推奨】{tile.name_ja} 切り → {name}に前進（受入{best.ukeire}枚）"
        else:
            return f"{pf_icon}【推奨】{tile.name_ja} 切り → {name}維持（受入{best.ukeire}枚, 約{best.expected_points:.0f}点）"

    def _generate_detailed_explanation(self, best: TileEvaluation,
                                       all_evals: list[TileEvaluation],
                                       reasons: list[DiscardReason],
                                       current_shanten: int,
                                       player: PlayerState,
                                       pf_decision: str,
                                       attack_ev: float,
                                       defense_risk: float,
                                       sit: dict) -> str:
        lines: list[str] = []
        tile = best.tile

        shanten_names = {
            0: "テンパイ", 1: "イーシャンテン",
            2: "リャンシャンテン", 3: "サンシャンテン",
        }
        name = shanten_names.get(current_shanten, f"{current_shanten}向聴")

        lines.append("━━━ 打牌解析 ━━━")
        lines.append(f"現在: {name} | {sit.get('phase','?')}({sit.get('turn',0)//4}巡目)")
        lines.append(f"推奨: {tile.name_ja} 切り")
        lines.append("")

        # 押し引き判定
        pf_label = {"push": "🔥攻撃", "fold": "🛡️オリ", "neutral": "🔄回し打ち"}
        lines.append(f"【戦略】{pf_label.get(pf_decision, pf_decision)}")
        if sit.get("has_riichi"):
            lines.append(f"  攻撃EV: {attack_ev:.0f} / 放銃リスク: {defense_risk:.0f}")
        lines.append("")

        # 理由
        lines.append("【理由】")
        for reason in reasons[:6]:
            icon = {"牌効率": "📊", "受入": "🎯", "不要牌": "🗑️",
                    "守備": "🛡️", "注意": "⚠️", "戦略": "🧠",
                    "打点": "💰"}.get(reason.category, "•")
            lines.append(f"  {icon} {reason.description}")
            if reason.detail:
                lines.append(f"     → {reason.detail}")

        # 候補比較
        lines.append("")
        lines.append("【候補比較】")
        for i, ev in enumerate(all_evals[:5]):
            marker = "★" if i == 0 else f"{i+1}."
            sh_change = ""
            if ev.shanten_after < current_shanten:
                sh_change = " ↓進"
            elif ev.shanten_after > current_shanten:
                sh_change = " ↑退"

            safety_label = ""
            if ev.safety_score >= 0.95:
                safety_label = " 🔒安"
            elif ev.safety_score >= 0.7:
                safety_label = " 🛡安"
            elif ev.safety_score < 0.4:
                safety_label = " ⚠危"

            lines.append(
                f"  {marker} {ev.tile.name_ja:4s} "
                f"受入:{ev.ukeire:2d}枚 "
                f"打点:{ev.expected_points:.0f}"
                f"{sh_change}{safety_label}"
            )

        # テンパイ時の待ち
        if current_shanten == 0:
            waiting = self.engine.get_waiting_tiles(player.seat)
            if waiting:
                lines.append("")
                lines.append(f"【待ち】{', '.join(t.name_ja for t in waiting)}")

        return "\n".join(lines)

    # ============================================================
    # 場況サマリ構築
    # ============================================================

    def _build_situation_summary(self, sit: dict) -> str:
        """場況の1行サマリを構築"""
        stance = sit.get("stance", "balanced")
        stance_icons = {
            "absolute_attack": "🔥全力攻撃",
            "absolute_defense": "🛡️絶対守り",
            "balanced": "⚖バランス",
        }
        stance_label = stance_icons.get(stance, stance)
        reason = sit.get("stance_reason", "")

        phase_map = {"early": "序盤", "middle": "中盤", "late": "終盤"}
        phase_label = phase_map.get(sit.get("phase", ""), "")

        parts = [
            f"{stance_label}",
            f"{phase_label}({sit.get('turn', 0)//4}巡目)",
            f"順位{sit.get('my_rank', '?')}",
        ]
        if sit.get("is_dealer"):
            parts.append("親")
        if sit.get("has_riichi"):
            parts.append("⚠リーチ者あり")

        summary = " | ".join(parts)
        if reason:
            summary += f"\n  → {reason}"
        return summary

    # ============================================================
    # ユーティリティ
    # ============================================================

    def _collect_visible_tiles(self) -> list[Tile]:
        visible: list[Tile] = []
        for p in self.engine.state.players:
            visible.extend(p.discards)
            for meld in p.melds:
                visible.extend(meld.tiles)
        return visible

    def _empty_recommendation(self, hand: list[Tile]) -> DiscardRecommendation:
        return DiscardRecommendation(
            recommended_tile=hand[0] if hand else Tile(TileSuit.MAN, 1),
            all_evaluations=[],
            reasons=[],
            summary="解析不可",
            detailed_explanation="手牌が打牌状態ではありません。",
            shanten_current=-1,
            is_tenpai=False,
            waiting_tiles=[],
        )

    def to_dict(self, rec: DiscardRecommendation) -> dict:
        """推奨結果をJSON互換のdictに変換"""
        # 各候補に攻め/守りの両面解説を付与
        choice_details = []
        for i, ev in enumerate(rec.all_evaluations[:3]):
            # 攻め面の解説
            atk_points = []
            if ev.shanten_after < rec.shanten_current:
                atk_points.append(f"向聴数が{rec.shanten_current}→{ev.shanten_after}に前進")
            atk_points.append(f"受入{ev.ukeire}枚")
            if ev.expected_points > 0:
                atk_points.append(f"期待打点 約{ev.expected_points:.0f}点")
            if ev.ukeire_tiles:
                atk_points.append(f"有効牌: {', '.join(t.name_ja for t in ev.ukeire_tiles[:5])}")

            # 守り面の解説
            def_points = []
            sp = ev.safety_score
            if sp >= 0.95:
                def_points.append("現物 → 放銃リスク0%")
            elif sp >= 0.7:
                def_points.append(f"安全度{sp*100:.0f}%（筋/壁で比較的安全）")
            elif sp >= 0.4:
                def_points.append(f"安全度{sp*100:.0f}%（やや注意）")
            else:
                def_points.append(f"安全度{sp*100:.0f}%（危険・放銃注意）")

            if ev.tile.is_terminal_or_honor:
                def_points.append("么九牌 → 比較的安全")
            elif ev.tile.number in (4, 5, 6):
                def_points.append("中張牌 → 放銃しやすい")

            choice_details.append({
                "tile": ev.tile.id,
                "tile_name": ev.tile.name_ja,
                "rank": i + 1,
                "is_recommended": i == 0,
                "shanten_after": ev.shanten_after,
                "ukeire": ev.ukeire,
                "ukeire_tiles": [t.name_ja for t in ev.ukeire_tiles[:8]],
                "danger_score": round(ev.danger_score, 2),
                "safety_score": round(ev.safety_score, 2),
                "expected_points": round(ev.expected_points, 0),
                "attack_analysis": atk_points,
                "defense_analysis": def_points,
            })

        return {
            "recommended_tile": rec.recommended_tile.id,
            "recommended_tile_name": rec.recommended_tile.name_ja,
            "summary": rec.summary,
            "detailed_explanation": rec.detailed_explanation,
            "shanten": rec.shanten_current,
            "is_tenpai": rec.is_tenpai,
            "waiting_tiles": [t.id for t in rec.waiting_tiles],
            "waiting_tiles_names": [t.name_ja for t in rec.waiting_tiles],
            "push_fold_state": rec.push_fold_state,
            "attack_ev": round(rec.attack_ev, 1),
            "defense_risk": round(rec.defense_risk, 1),
            "situation_summary": rec.situation_summary,
            "num_choices": len(choice_details),
            "reasons": [
                {
                    "category": r.category,
                    "importance": r.importance,
                    "description": r.description,
                    "detail": r.detail,
                }
                for r in rec.reasons
            ],
            "choices": choice_details,
            # 後方互換のため evaluations も残す
            "evaluations": [
                {
                    "tile": ev.tile.id,
                    "tile_name": ev.tile.name_ja,
                    "shanten_after": ev.shanten_after,
                    "ukeire": ev.ukeire,
                    "ukeire_tiles": [t.name_ja for t in ev.ukeire_tiles[:8]],
                    "danger_score": round(ev.danger_score, 2),
                    "value_score": round(ev.value_score, 2),
                    "safety_score": round(ev.safety_score, 2),
                    "expected_points": round(ev.expected_points, 0),
                    "good_shape_ratio": round(ev.good_shape_ratio, 2),
                }
                for ev in rec.all_evaluations[:3]
            ],
        }
