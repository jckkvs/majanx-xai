"""
XAI、戦略、解釈（ルール）の3エンジンを統合するファサード (EnsembleAI)
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List

# 本来の型だが依存解決が必要なのでAnyとするものも含める
from server.models import GameState
from server.round_context import MatchConfig
from server.xai_engine import XAIEngine
from server.strategy_engine import StrategyEngine, ActionCandidate
from server.mortal_interpreter import MortalInterpreter

@dataclass
class EnsembleRecommendation:
    primary_action: str
    xai_output: Any
    strategy_output: ActionCandidate
    interpretation_output: Any
    confidence_breakdown: Dict[str, float]
    conflict_resolution_note: str
    expected_value_delta: float

class WeightCalculator:
    """EVや局面から各エンジンの信頼度重みを計算するクラス"""
    def compute(self, gs: GameState, cfg: MatchConfig) -> Dict[str, float]:
        # Brier score や Calibration error のモック値
        calibration_error = 0.05
        ev_consistency = 0.85
        rule_match_confidence = 0.90
        
        weight_xai = 0.4 * (1.0 - calibration_error)
        weight_strat = 0.4 * ev_consistency
        weight_interp = 0.2 * rule_match_confidence
        
        # 正規化
        total = weight_xai + weight_strat + weight_interp
        return {
            'xai': round(weight_xai / total, 3),
            'strategy': round(weight_strat / total, 3),
            'interpret': round(weight_interp / total, 3)
        }

class EnsembleAI:
    def __init__(self, xai: XAIEngine = None, strategy: StrategyEngine = None, interp: MortalInterpreter = None):
        # 実際に注入できるように引数を取る
        self.engines = {
            'xai': xai,
            'strategy': strategy or StrategyEngine(),
            'interpret': interp
        }
        self.evl_calc = self.engines['strategy'].evl_calc if hasattr(self.engines['strategy'], 'evl_calc') else None
        self.weight_calculator = WeightCalculator()
        
    def recommend(self, game_state: GameState, cfg: MatchConfig, hand_tiles: List[Any], candidate_tiles: List[Any]) -> EnsembleRecommendation:
        """3エンジンの推論を統合し、最適な打牌を決定する"""
        
        # --- エンジン独立推論 ---
        strat_out = self.engines['strategy'].evaluate(game_state, hand_tiles, candidate_tiles)
        
        # モールドデータ（実際には各エンジンが走る想定）
        xai_out = {"best_tile": strat_out.tile_id, "score": 0.8, "danger_map": {}} 
        interp_out = {"best_tile": strat_out.tile_id, "reasoning": "ルールマッチ重みによる解釈"}
        
        results = {
            'xai': xai_out,
            'strategy': strat_out,
            'interpret': interp_out
        }
        
        # --- 重み計算・統合 ---
        weights = self.weight_calculator.compute(game_state, cfg)
        
        # 実際にはスコアの加重平均を取り、行動を決定する
        # ここではモック実装として、戦略エンジンの判定をPrimaryとする
        combined_action = strat_out.tile_id
        
        # --- 出力生成 ---
        threshold_info = "BALANCE", 0.0
        if self.evl_calc:
            threshold_info = self.evl_calc.calculate_push_fold_threshold(game_state)
            
        note = f"アンサンブル推論統合: Strategy={strat_out.strategy_type} (EV: {threshold_info[1]:.0f})"
        
        return EnsembleRecommendation(
            primary_action=combined_action,
            xai_output=xai_out,
            strategy_output=strat_out,
            interpretation_output=interp_out,
            confidence_breakdown=weights,
            conflict_resolution_note=note,
            expected_value_delta=threshold_info[1]
        )
