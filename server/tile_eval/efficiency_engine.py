"""
牌効率評価の統合エンジン（エントリーポイント）
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from .tile_analyzer import TileAnalyzer, TileConnection
from .shape_evaluator import ShapeEvaluator, ShapeScore, EvalContext
from .ukeire_calculator import UkeireCalculator, UkeireResult
from .honor_evaluator import HonorEvaluator, HonorScore, HonorContext

@dataclass
class TileEvaluation:
    """牌の総合評価結果"""
    tile_id: str
    shape_score: ShapeScore
    ukeire_result: UkeireResult
    honor_score: Optional[HonorScore]
    final_score: float
    discard_priority: float  # 低いほど切るべき
    reasoning: str  # 判定根拠

class TileEfficiencyEngine:
    """牌効率評価の統合エンジン"""
    
    def __init__(self):
        self.analyzer = TileAnalyzer()
        self.shape_eval = ShapeEvaluator()
        self.honor_eval = HonorEvaluator()
    
    def evaluate_discards(self, hand: List[str], context: 'EngineContext') -> List[TileEvaluation]:
        """手牌から各打牌候補を評価"""
        # 1. 連結関係解析
        connections = self.analyzer.analyze_hand(hand)
        
        # 2. 形状価値評価
        shape_scores = self.shape_eval.evaluate(connections, context.shape_context)
        
        # 3. 受入計算
        visible = context.visible_tiles
        ukeire_calc = UkeireCalculator(visible)
        
        # 4. 評価統合
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
            
            # 総合スコア計算
            final = self._calc_final_score(shape, ukeire, honor, context)
            
            # 判定根拠の生成
            reasoning = self._generate_reasoning(tile, shape, ukeire, honor, context)
            
            results.append(TileEvaluation(
                tile_id=tile,
                shape_score=shape,
                ukeire_result=ukeire,
                honor_score=honor,
                final_score=final,
                discard_priority=1.0 / (final + 0.01),
                reasoning=reasoning
            ))
        
        # 最終スコアでソート（低い順＝価値が低い＝切るべき）
        return sorted(results, key=lambda x: x.final_score)
    
    def _calc_final_score(self, shape: ShapeScore, ukeire: UkeireResult,
                         honor: Optional[HonorScore], context: 'EngineContext') -> float:
        """総合スコアの計算 (スコアが高いほど手牌に残すべき)"""
        # 手牌に残す価値:
        # shape.total_score は単体・局所的な価値
        # ukeire.effective_ukeire は「その牌を切った後の手牌の有効受入」。
        # これが大きい＝その牌は不要。逆に言えば、これが小さい＝その牌を切ると受入が減る＝その牌は必要（残すべき）。
        # 比較が難しいため、基準となる最大受入枚数(例えば全部の平均や定数)から引いた値を「保持価値」とする。
        # 単純にマイナスすると扱いづらいので、ベース価値から引くか、優先度の符号を後で考慮する。
        # ここでは、最終スコアを純粋に「保持価値」にするため、ukeireが大きいほどスコアを下げる。
        max_assumed_ukeire = 40.0 # 仮想の最大受入
        ukeire_retention_value = max(0.0, max_assumed_ukeire - ukeire.effective_ukeire)
        
        score = shape.total_score * 0.6 + ukeire_retention_value * 0.05
        
        # 字牌ボーナス
        if honor:
            score += honor.total_score * 0.4
            
        # 状況補正
        if context.turn >= 10 and context.riichi_count > 0:
            if honor:
                score += honor.defensive_value * 0.5
                
        return max(0.0, score)
    
    def _generate_reasoning(self, tile: str, shape: ShapeScore, 
                           ukeire: UkeireResult, honor: Optional[HonorScore],
                           context: 'EngineContext') -> str:
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
        
        # 状況補足
        if context.riichi_count > 0 and context.turn >= 8:
            parts.append("他家リーチ下・終盤")
        
        return "。".join(parts) + "。" if parts else "標準的な牌効率判断。"

@dataclass
class EngineContext:
    """評価エンジンコンテキスト"""
    turn: int
    bakaze_val: Optional[int]
    jikaze_val: Optional[int]
    is_dealer: bool
    riichi_count: int
    visible_tiles: Dict[str, int]
    safe_tiles_remaining: int
    shape_context: EvalContext
    
    @classmethod
    def from_game_state(cls, gs: 'GameState', current_seat: int) -> 'EngineContext':
        """GameStateからコンテキストを構築"""
        player = gs.players[current_seat]
        visible = cls._count_visible_tiles(gs)
        
        shape_ctx = EvalContext(
            turn=gs.turn_count,
            bakaze=gs.bakaze.name.lower() if hasattr(gs.bakaze, 'name') else gs.bakaze,
            jikaze=player.wind.name.lower() if hasattr(player, 'wind') else 'east', # 簡易化
            dora_indicators=[t.id for t in gs.dora_indicators]
        )
        
        return cls(
            turn=gs.turn_count,
            bakaze_val=shape_ctx.bakaze_val,
            jikaze_val=shape_ctx.jikaze_val,
            is_dealer=(gs.dealer == current_seat),
            riichi_count=sum(1 for p in gs.players if p.is_riichi),
            visible_tiles=visible,
            safe_tiles_remaining=cls._count_safe_tiles(gs, current_seat),
            shape_context=shape_ctx
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
        # 簡易実装：現物・筋・壁をカウント
        safe = 0
        for p in gs.players:
            if p.seat == seat: continue
            if p.is_riichi:
                # リーチ宣言牌は現物
                safe += 1
                # 筋牌を概算
                safe += 2
        return min(safe, 10)  # 最大10枚でクリップ
