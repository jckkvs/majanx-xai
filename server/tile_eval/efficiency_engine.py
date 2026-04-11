"""
牌効率評価の統合エンジン（エントリーポイント）
5次元評価重み（shape/ukeire/honor/risk/form）対応版
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .tile_analyzer import TileAnalyzer, TileConnection
from .shape_evaluator import ShapeEvaluator, ShapeScore, EvalContext
from .ukeire_calculator import UkeireCalculator, UkeireResult
from .honor_evaluator import HonorEvaluator, HonorScore, HonorContext
from .weight_adapter import PriorityWeightAdapter, ExtendedWeightVector, WeightContext
from .risk_estimator import RiskEstimator, RiskScore, RiskContext
from .form_analyzer import FormAnalyzer, FormScore, FormContext

@dataclass
class TileEvaluation:
    """牌の総合評価結果"""
    tile_id: str
    shape_score: ShapeScore
    ukeire_result: UkeireResult
    honor_score: Optional[HonorScore]
    risk_score: Optional[RiskScore] = None
    final_score: float = 0.0
    discard_priority: float = 0.0  # 低いほど切るべき
    reasoning: str = ""  # 判定根拠
    weights_used: Optional[ExtendedWeightVector] = None

class TileEfficiencyEngine:
    """牌効率評価の統合エンジン（5次元重み対応）"""
    
    def __init__(self):
        self.analyzer = TileAnalyzer()
        self.shape_eval = ShapeEvaluator()
        self.honor_eval = HonorEvaluator()
        self.risk_estimator = RiskEstimator()
        self.form_analyzer = FormAnalyzer()
        self.weight_adapter = PriorityWeightAdapter()
    
    def evaluate_discards(
        self,
        hand: List[str],
        context: 'EngineContext',
        strategy_tag: str = 'balanced',
    ) -> List[TileEvaluation]:
        """手牌から各打牌候補を評価（5次元重み適用）"""
        # 1. 連結関係解析
        connections = self.analyzer.analyze_hand(hand)
        
        # 2. 形状価値評価
        shape_scores = self.shape_eval.evaluate(connections, context.shape_context)
        
        # 3. 受入計算
        visible = context.visible_tiles
        ukeire_calc = UkeireCalculator(visible)
        
        # 4. リスク推定
        risk_ctx = RiskContext(
            turn=context.turn,
            riichi_players=context.riichi_seats,
            discarded_tiles=context.discarded_tiles_by_seat,
            visible_tile_counts=visible,
            current_seat=context.current_seat,
        )
        risk_scores = self.risk_estimator.estimate_all(hand, risk_ctx)
        
        # 5. 形勢判断
        form_ctx = FormContext(
            score_diff=context.score_diff,
            rank=context.rank,
            remaining_rounds=context.remaining_rounds,
            is_dealer=context.is_dealer,
            honba=context.honba,
        )
        form_score = self.form_analyzer.analyze(form_ctx)
        
        # 6. 5次元重みの決定
        weight_ctx = WeightContext(
            turn=context.turn,
            score_diff=context.score_diff,
            rank=context.rank,
            remaining_rounds=context.remaining_rounds,
            riichi_count=context.riichi_count,
            is_dealer=context.is_dealer,
            honba=context.honba,
        )
        weights = self.weight_adapter.compute_weights(strategy_tag, weight_ctx)
        
        # 7. 評価統合
        results = []
        for tile in set(hand):
            # 形状スコア
            shape = shape_scores[tile]
            
            # 受入結果
            ukeire = ukeire_calc.calculate(hand, tile, connections)
            
            # 字牌評価
            honor = None
            if tile[-1] == 'z':
                honor_ctx = HonorContext(
                    turn=context.turn,
                    bakaze_val=context.bakaze_val,
                    jikaze_val=context.jikaze_val,
                    riichi_count=context.riichi_count,
                    safe_tiles_remaining=context.safe_tiles_remaining
                )
                honor = self.honor_eval.evaluate(tile, hand.count(tile), honor_ctx)
            
            # リスクスコア
            risk = risk_scores.get(tile)
            
            # 総合スコア計算（5次元重み）
            final = self._calc_final_score(shape, ukeire, honor, risk, form_score, weights, context)
            
            # 判定根拠の生成
            reasoning = self._generate_reasoning(tile, shape, ukeire, honor, risk, context)
            
            results.append(TileEvaluation(
                tile_id=tile,
                shape_score=shape,
                ukeire_result=ukeire,
                honor_score=honor,
                risk_score=risk,
                final_score=final,
                discard_priority=1.0 / (final + 0.01),
                reasoning=reasoning,
                weights_used=weights,
            ))
        
        # 最終スコアでソート（低い順＝価値が低い＝切るべき）
        return sorted(results, key=lambda x: x.final_score)
    
    def _calc_final_score(
        self,
        shape: ShapeScore,
        ukeire: UkeireResult,
        honor: Optional[HonorScore],
        risk: Optional[RiskScore],
        form: FormScore,
        weights: ExtendedWeightVector,
        context: 'EngineContext',
    ) -> float:
        """5次元重みによる総合スコアの計算 (スコアが高いほど手牌に残すべき)"""
        # === 各次元のスコアを0.0〜1.0に正規化 ===

        # 形状価値 (shape): total_scoreを上限3.0で正規化
        shape_val = min(1.0, shape.total_score / 3.0)

        # 受入保持価値 (ukeire): 受入が大きい＝その牌は不要 → 保持価値は逆
        max_assumed_ukeire = 40.0
        ukeire_val = max(0.0, (max_assumed_ukeire - ukeire.effective_ukeire) / max_assumed_ukeire)

        # 字牌・役牌価値 (honor)
        honor_val = min(1.0, honor.total_score / 2.0) if honor else 0.0

        # リスク安全度 (risk): danger が高い = 切りたい = 保持価値は低い
        # → 安全度 = 1 - danger を保持価値とする
        risk_val = (1.0 - risk.danger) if risk else 0.5

        # 形勢スコア (form): 攻勢度が高いほど攻撃的な牌の保持価値が上がる
        # 攻撃的な牌 = shape/ukeire価値が高い牌 → formは攻撃牌のブースト係数として作用
        form_val = form.aggression

        # === 5次元加重和 ===
        score = (
            weights.shape * shape_val
            + weights.ukeire * ukeire_val
            + weights.honor * honor_val
            + weights.risk * risk_val
            + weights.form * form_val
        )

        return max(0.0, score)

    def _generate_reasoning(
        self,
        tile: str,
        shape: ShapeScore,
        ukeire: UkeireResult,
        honor: Optional[HonorScore],
        risk: Optional[RiskScore],
        context: 'EngineContext',
    ) -> str:
        """判定根拠の自然言語生成"""
        parts = []
        
        # 孤立牌の特別ルール
        if shape.base_value < 0.5 and shape.shape_bonus <= 0:
            parts.append(f"{tile}は役なし孤立客風牌")
        elif shape.shape_bonus > 0.3:
            parts.append(f"{tile}は形状価値が高い")
        elif shape.shape_bonus < 0:
            parts.append(f"{tile}は孤立牌")
        
        # 受入評価
        if ukeire.effective_ukeire >= 8:
            parts.append(f"受入{ukeire.raw_ukeire}枚で速度優位")
        elif ukeire.effective_ukeire <= 2:
            parts.append(f"受入が狭く速度劣位")
        
        # 字牌評価
        if honor:
            if honor.pair_value > 0.5:
                parts.append(f"{tile}は役牌対子候補")
            if honor.defensive_value > 0.3:
                parts.append(f"終盤安牌としての価値")
        
        # リスク評価
        if risk:
            if risk.genbutsu:
                parts.append(f"{tile}は現物で安全")
            elif risk.danger >= 0.6:
                parts.append(f"{tile}は危険度{risk.danger:.0%}")
            elif risk.suji:
                parts.append(f"{tile}は筋牌")
        
        # 状況補足
        if context.riichi_count > 0 and context.turn >= 8:
            parts.append("他家リーチ下・終盤")
        
        return "。".join(parts) + "。" if parts else "標準的な牌効率判断。"

@dataclass
class EngineContext:
    """評価エンジンコンテキスト（5次元重み対応）"""
    turn: int
    bakaze_val: Optional[int]
    jikaze_val: Optional[int]
    is_dealer: bool
    riichi_count: int
    visible_tiles: Dict[str, int]
    safe_tiles_remaining: int
    shape_context: EvalContext
    # --- 5次元重み用の追加フィールド ---
    score_diff: float = 0.0               # 自分 - トップの点差
    rank: int = 2                          # 現在順位 (1-4)
    remaining_rounds: int = 8              # 残り局数
    honba: int = 0                         # 本場
    current_seat: int = 0                  # 自分の座席
    riichi_seats: List[int] = field(default_factory=list)  # リーチ者の座席
    discarded_tiles_by_seat: Dict[int, List[str]] = field(default_factory=dict)  # seat -> [捨牌]
    
    @classmethod
    def from_game_state(cls, gs: 'GameState', current_seat: int) -> 'EngineContext':
        """GameStateからコンテキストを構築"""
        player = gs.players[current_seat]
        visible = cls._count_visible_tiles(gs)
        
        shape_ctx = EvalContext(
            turn=gs.turn_count,
            bakaze=gs.bakaze.name.lower() if hasattr(gs.bakaze, 'name') else gs.bakaze,
            jikaze=player.wind.name.lower() if hasattr(player, 'wind') else 'east',
            dora_indicators=[t.id for t in gs.dora_indicators]
        )
        
        riichi_seats = [p.seat for p in gs.players if p.is_riichi]
        discards_by_seat = {
            p.seat: [t.id for t in p.discards] for p in gs.players
        }
        
        # 点差計算（自分 - トップ）
        scores = [p.score for p in gs.players]
        top_score = max(scores)
        my_score = player.score
        score_diff = my_score - top_score
        
        # 順位計算
        rank = sorted(scores, reverse=True).index(my_score) + 1
        
        return cls(
            turn=gs.turn_count,
            bakaze_val=shape_ctx.bakaze_val,
            jikaze_val=shape_ctx.jikaze_val,
            is_dealer=(gs.dealer == current_seat),
            riichi_count=len(riichi_seats),
            visible_tiles=visible,
            safe_tiles_remaining=cls._count_safe_tiles(gs, current_seat),
            shape_context=shape_ctx,
            score_diff=score_diff,
            rank=rank,
            remaining_rounds=getattr(gs, 'remaining_rounds', 8),
            honba=getattr(gs, 'honba', 0),
            current_seat=current_seat,
            riichi_seats=riichi_seats,
            discarded_tiles_by_seat=discards_by_seat,
        )
    
    @staticmethod
    def _count_visible_tiles(gs: 'GameState') -> Dict[str, int]:
        """公開牌のカウント"""
        counts = {}
        for p in gs.players:
            for t in p.discards:
                counts[t.id] = counts.get(t.id, 0) + 1
            for meld in p.melds:
                for t in meld.tiles:
                    counts[t.id] = counts.get(t.id, 0) + 1
        return counts
    
    @staticmethod
    def _count_safe_tiles(gs: 'GameState', seat: int) -> int:
        """安全牌の残り枚数を概算"""
        safe = 0
        for p in gs.players:
            if p.seat == seat: continue
            if p.is_riichi:
                safe += 1
                safe += 2
        return min(safe, 10)
