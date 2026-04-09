"""
server/utils/endgame_analyzer.py
終局管理エンジン

オーラス（最終局）の精密打点管理:
  - 必要打点の厳密計算（目標順位×点差）
  - 攻守選択のEV計算（順位変動の価値を加味）
  - 聴牌料の戦略的価値判定
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from server.models import GameState


# ── 翻数→和了点テーブル（子ロン、30符基本） ──
HAN_TO_POINTS_CHILD = {
    1: 1000, 2: 2000, 3: 3900, 4: 7700,
    5: 8000, 6: 12000, 7: 12000, 8: 16000,
    9: 16000, 10: 16000, 11: 24000, 12: 24000, 13: 32000,
}
HAN_TO_POINTS_DEALER = {
    1: 1500, 2: 2900, 3: 5800, 4: 11600,
    5: 12000, 6: 18000, 7: 18000, 8: 24000,
    9: 24000, 10: 24000, 11: 36000, 12: 36000, 13: 48000,
}


@dataclass
class RequiredPoints:
    """必要打点の計算結果"""
    current_rank: int
    current_score: int
    target_rank: int
    target_player_score: int
    required_points: int
    required_han: int
    is_achievable: bool
    note: str

    def to_dict(self) -> Dict:
        return {
            "current_rank": self.current_rank,
            "current_score": self.current_score,
            "target_rank": self.target_rank,
            "required_points": self.required_points,
            "required_han": self.required_han,
            "achievable": self.is_achievable,
            "note": self.note,
        }


@dataclass
class EndgameEV:
    """終局EV計算結果"""
    push_ev: float
    fold_ev: float
    recommended: str  # "push" / "fold" / "balanced"
    reasoning: str

    def to_dict(self) -> Dict:
        return {
            "push_ev": round(self.push_ev, 1),
            "fold_ev": round(self.fold_ev, 1),
            "recommended": self.recommended,
            "reasoning": self.reasoning,
        }


@dataclass
class TenpaiValue:
    """聴牌料の戦略的価値"""
    tenpai_fee: int
    is_tenpai: bool
    should_maintain: bool
    reasoning: str

    def to_dict(self) -> Dict:
        return {
            "fee": self.tenpai_fee,
            "is_tenpai": self.is_tenpai,
            "maintain": self.should_maintain,
            "reasoning": self.reasoning,
        }


@dataclass
class EndgameResult:
    """終局管理の統合出力"""
    is_endgame: bool
    remaining_rounds: int
    required_points: Optional[RequiredPoints]
    ev_analysis: Optional[EndgameEV]
    tenpai_value: Optional[TenpaiValue]

    def to_dict(self) -> Dict:
        d = {
            "is_endgame": self.is_endgame,
            "remaining_rounds": self.remaining_rounds,
        }
        if self.required_points:
            d["required"] = self.required_points.to_dict()
        if self.ev_analysis:
            d["ev"] = self.ev_analysis.to_dict()
        if self.tenpai_value:
            d["tenpai"] = self.tenpai_value.to_dict()
        return d


class EndgameAnalyzer:
    """終局管理エンジン"""

    def analyze(self, gs: GameState, seat: int) -> EndgameResult:
        """終局情報を統合解析"""
        remaining = self._estimate_remaining_rounds(gs)
        is_endgame = remaining <= 2

        if not is_endgame:
            return EndgameResult(
                is_endgame=False,
                remaining_rounds=remaining,
                required_points=None,
                ev_analysis=None,
                tenpai_value=None,
            )

        req = self._calc_required_points(gs, seat)
        ev = self._calc_ev(gs, seat, req)
        tenpai = self._calc_tenpai_value(gs, seat)

        return EndgameResult(
            is_endgame=True,
            remaining_rounds=remaining,
            required_points=req,
            ev_analysis=ev,
            tenpai_value=tenpai,
        )

    # ═══════════════════════════════════════════════
    # 残り局数の推定
    # ═══════════════════════════════════════════════

    def _estimate_remaining_rounds(self, gs: GameState) -> int:
        """残り局数を推定（簡易版）"""
        # round_wind: EAST=0, SOUTH=1, WEST=2, NORTH=3
        # 東風戦: 東4局まで（4局）、半荘: 南4局まで（8局）
        round_num = gs.round_wind.value  # 0=東, 1=南
        dealer = gs.dealer  # 0-3
        current_round = round_num * 4 + dealer + 1  # 1-indexed

        # 半荘（8局）を前提
        total_rounds = 8
        return max(0, total_rounds - current_round)

    # ═══════════════════════════════════════════════
    # 必要打点の厳密計算
    # ═══════════════════════════════════════════════

    def _calc_required_points(self, gs: GameState,
                               seat: int) -> RequiredPoints:
        """現在の点棒状況から必要打点を計算"""
        scores = [(p.seat, p.score) for p in gs.players]
        scores.sort(key=lambda x: x[1], reverse=True)

        my_score = gs.players[seat].score
        my_rank = next(
            (i + 1 for i, (s, _) in enumerate(scores) if s == seat), 4
        )

        is_dealer = gs.dealer == seat
        han_table = HAN_TO_POINTS_DEALER if is_dealer else HAN_TO_POINTS_CHILD

        # 上位目標（1つ上の順位）
        if my_rank == 1:
            return RequiredPoints(
                current_rank=1, current_score=my_score,
                target_rank=1, target_player_score=my_score,
                required_points=0, required_han=0,
                is_achievable=True,
                note="トップ。順位維持が目標"
            )

        target_rank = my_rank - 1
        target_score = scores[target_rank - 1][1]  # 上位者の点数
        margin = 100  # 同点時の安全マージン
        required = target_score - my_score + margin

        # 必要翻数を逆算
        required_han = 0
        for h in range(1, 14):
            pts = han_table.get(h, 32000)
            if pts >= required:
                required_han = h
                break
        if required_han == 0:
            required_han = 13  # 役満必要

        is_achievable = required <= han_table.get(13, 32000)

        # 到達可能な翻数名称
        han_name_map = {
            1: "1翻", 2: "2翻", 3: "3翻", 4: "4翻",
            5: "満貫", 6: "跳満", 7: "跳満", 8: "倍満",
            9: "倍満", 10: "倍満", 11: "三倍満", 12: "三倍満",
            13: "役満",
        }
        han_name = han_name_map.get(required_han, "?")

        note = (f"{my_rank}位({my_score}点)→{target_rank}位({target_score}点)。"
                f"{required}点以上必要。{han_name}({han_table.get(required_han, 0)}点)で到達可能")

        return RequiredPoints(
            current_rank=my_rank, current_score=my_score,
            target_rank=target_rank, target_player_score=target_score,
            required_points=required, required_han=required_han,
            is_achievable=is_achievable,
            note=note,
        )

    # ═══════════════════════════════════════════════
    # 攻守EV計算（終局特化版）
    # ═══════════════════════════════════════════════

    def _calc_ev(self, gs: GameState, seat: int,
                  req: RequiredPoints) -> EndgameEV:
        """順位変動の価値を加味したEV計算"""
        rank = req.current_rank
        required = req.required_points

        # 簡易的な順位変動価値
        # 鳳凰卓基準: +30/+10/-10/-30
        rank_values = {1: 30, 2: 10, 3: -10, 4: -30}
        current_rv = rank_values.get(rank, 0)
        target_rv = rank_values.get(rank - 1, 0) if rank > 1 else 30
        down_rv = rank_values.get(rank + 1, -30) if rank < 4 else -30

        # 押しEV = 和了確率 × (和了点 + 順位上昇価値) - 放銃確率 × (放銃損失 + 順位下降損失)
        # 簡易推定値を使用
        agari_prob = 0.25  # テンパイからの平均和了率
        houjuu_prob = 0.10  # 平均放銃率
        avg_loss = 5200  # 平均放銃損失

        push_ev = (agari_prob * (required + (target_rv - current_rv) * 100)
                   - houjuu_prob * (avg_loss + (current_rv - down_rv) * 100))
        fold_ev = 0.0  # 降りのEVは基本0（現状維持）

        # 判断
        if rank == 1:
            # トップ → 安全第一
            return EndgameEV(
                push_ev=push_ev, fold_ev=fold_ev,
                recommended="fold",
                reasoning="トップ目。放銃の順位下降リスクが和了の追加利益を上回る"
            )
        elif rank == 4:
            # ラス → 攻め
            if not req.is_achievable:
                return EndgameEV(
                    push_ev=push_ev, fold_ev=fold_ev,
                    recommended="fold",
                    reasoning="ラス目だが和了しても逆転不可能。被害軽減を優先"
                )
            return EndgameEV(
                push_ev=push_ev, fold_ev=fold_ev,
                recommended="push",
                reasoning=f"ラス回避。{req.required_han}翻以上で逆転可能"
            )
        else:
            # 2位/3位 → バランス
            if push_ev > fold_ev:
                return EndgameEV(
                    push_ev=push_ev, fold_ev=fold_ev,
                    recommended="push" if push_ev > 500 else "balanced",
                    reasoning=f"{rank}位。押しEVがプラス。{req.required_han}翻で逆転可能"
                )
            else:
                return EndgameEV(
                    push_ev=push_ev, fold_ev=fold_ev,
                    recommended="fold",
                    reasoning=f"{rank}位。放銃の順位下降リスクが大きい"
                )

    # ═══════════════════════════════════════════════
    # 聴牌料の戦略的価値
    # ═══════════════════════════════════════════════

    def _calc_tenpai_value(self, gs: GameState,
                            seat: int) -> TenpaiValue:
        """流局時の聴牌料の価値を判定"""
        turn = gs.turn_count
        is_tenpai = False
        try:
            shanten = gs.get_player_shanten(seat)
            is_tenpai = shanten == 0
        except Exception:
            pass

        rank = next(
            (i + 1 for i, (s, _) in enumerate(
                sorted([(p.seat, p.score) for p in gs.players],
                       key=lambda x: x[1], reverse=True)
            ) if s == seat), 1
        )

        # 聴牌料: テンパイ者数に依存（1人テンパイ=+3000, 2人=+1500, 3人=+1000）
        avg_fee = 1500  # 平均的な聴牌料

        if turn < 12:
            return TenpaiValue(
                tenpai_fee=0, is_tenpai=is_tenpai,
                should_maintain=False,
                reasoning="まだ終盤ではない。聴牌料よりも手作りを優先"
            )

        if is_tenpai:
            should = True
            if rank == 1 and turn >= 15:
                reasoning = "トップ且つテンパイ。安全牌で聴牌維持し聴牌料確保"
            elif rank >= 3:
                reasoning = f"テンパイ維持で聴牌料(約{avg_fee}点)確保。ラス回避に直結"
            else:
                reasoning = f"テンパイ維持。流局時に聴牌料(約{avg_fee}点)獲得可能"
        else:
            should = rank >= 3 and turn >= 14
            if should:
                reasoning = "ノーテンだがラス圏。テンパイを急ぎ聴牌料を確保したい"
            else:
                reasoning = "ノーテン。テンパイ強行のリスクは聴牌料の価値を上回る可能性"

        return TenpaiValue(
            tenpai_fee=avg_fee if is_tenpai else 0,
            is_tenpai=is_tenpai,
            should_maintain=should,
            reasoning=reasoning,
        )
