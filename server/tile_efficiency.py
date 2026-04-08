import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class EvalContext:
    turn: int
    riichi_count: int
    bakaze: str = "東"
    jikaze: str = "東"
    is_dealer: bool = True
    honba: int = 0
    dora_indicators: List[str] = field(default_factory=list)
    dora_tiles: List[str] = field(default_factory=list)
    # 動的評価用
    bakaze_changed_prob: float = 0.0
    opponent_tenpai_probs: List[float] = field(default_factory=list)
    opponents_discards: List[List[str]] = field(default_factory=list)
    visible_tiles: Dict[str, int] = field(default_factory=dict)
    score_gap: int = 0

class TileEfficiencyEvaluator:
    def __init__(self, weights_path: str = "server/weights/honor_tile_eval.yaml", yaku_path: str = "server/weights/yaku_eval.yaml"):
        self.weights = self._load_yaml(weights_path, {
            "alpha": 0.35, "beta": 1.2, "gamma": 0.8,
            "delta": 0.6, "epsilon": 0.4, "zeta": 0.5,
            "beta_late_turn": 1.5, "epsilon_late_turn": 0.6, "beta_dealer_honor": 1.35
        })
        self.yaku_weights = self._load_yaml(yaku_path, {
            "yakuman_base": 0.05, "yakuman_threshold_late": 0.05,
            "iipeiko_base": 0.20, "iipeiko_weight": 0.35,
            "ryanmen": 1.0, "kanchan": 0.7, "excess_shape": 0.6, "collapsed_shape": 0.4
        })
        
    def _load_yaml(self, path: str, fallback: dict) -> dict:
        p = Path(path)
        if not p.exists(): return fallback
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        merged = {}
        if "weights" in data: merged.update(data["weights"])
        if "multipliers" in data: merged.update(data["multipliers"])
        if "yaku_probabilities" in data: merged.update(data["yaku_probabilities"])
        if "shape_stability" in data: merged.update(data["shape_stability"])
        if "risk_weights" in data: merged.update(data["risk_weights"])
        return merged if merged else fallback

    def evaluate_tile_efficiency(self, tile: str, hand_state: List[str], context: EvalContext) -> float:
        ukeire = self.calculate_ukeire_after_discard(tile, hand_state)
        yaku_score = self._calc_yaku_guarantee(tile, hand_state, context)
        dora_score = self._calc_dora_value(tile, context)
        call_speed = self._calc_call_potential(tile, hand_state, context.turn)
        defense = self._calc_defensive_value(tile, context)
        shape_cost = self._calc_opportunity_cost(tile, hand_state, context)
        iipeiko_bonus = self._calc_iipeiko_bonus(tile, hand_state, context)
        
        alpha = self.weights.get("alpha", 0.35)
        beta = self.weights.get("beta", 1.2)
        gamma = self.weights.get("gamma", 0.8)
        delta = self.weights.get("delta", 0.6)
        epsilon = self.weights.get("epsilon", 0.4)
        zeta = self.weights.get("zeta", 0.5)

        if context.turn <= 8:
            beta = 1.2
            epsilon = 0.2 if context.turn >= 5 else 0.05
        else:
            beta = self.weights.get("beta_late_turn", 1.5)
            epsilon = 0.4
            
        if context.riichi_count >= 2:
            epsilon = self.weights.get("epsilon_late_turn", 0.6)
            
        if context.is_dealer and context.honba >= 3:
            beta = self.weights.get("beta_dealer_honor", 1.35)

        # 総合スコア（形状安定性ペナルティと多変量役ボーナス追加）
        base_score = (alpha * ukeire + beta * yaku_score + gamma * dora_score + 
                      delta * call_speed + epsilon * defense - zeta * shape_cost)
        
        return base_score + iipeiko_bonus

    def calculate_ukeire_after_discard(self, tile: str, hand_state: List[str]) -> int:
        return 0

    def _calc_yaku_guarantee(self, tile: str, hand_state: List[str], context: EvalContext) -> float:
        count = hand_state.count(tile)
        score = 0.0
        if count == 2:
            if tile in {context.bakaze, context.jikaze, '白', '發', '中'}:
                score = 1.0
        elif count == 3:
            score = 2.0
            
        # 場風変化リスク（親の切り出し等）による減衰
        if tile == context.bakaze and context.bakaze_changed_prob > 0:
            score *= (1.0 - context.bakaze_changed_prob)
            score = max(0.2, score)
            
        return score

    def _calc_dora_value(self, tile: str, context: EvalContext) -> float:
        if context.dora_tiles and tile in context.dora_tiles:
            return 1.5
        if context.dora_indicators and any(self._is_adjacent_to_indicator(tile, ind) for ind in context.dora_indicators):
            return 0.8
        return 0.0
        
    def _is_adjacent_to_indicator(self, tile: str, indicator: str) -> bool:
        if not tile or not tile[-1] in ('m', 'p', 's'):
            return False
        return False

    def _calc_call_potential(self, tile: str, hand_state: List[str], turn: int) -> float:
        if hand_state.count(tile) == 2:
            turn_rem = max(0, 18 - turn)
            p_pon = min(0.35, turn_rem * 0.12)
            speed_bonus = 0.6
            return p_pon * speed_bonus
        return 0.0

    def _calc_defensive_value(self, tile: str, context: EvalContext) -> float:
        base_def = 0.05
        if context.turn >= 8: base_def = 0.4
        elif context.turn >= 5: base_def = 0.2
        
        # テンパイ確率が高い他家がいる場合は安全牌価値上昇
        max_opp_prob = max(context.opponent_tenpai_probs) if context.opponent_tenpai_probs else 0.0
        if max_opp_prob > 0.6 and context.turn >= 7:
            base_def *= 1.8
            
        # 字牌かつ他家安全の想定ならさらに補正（スタブ）
        if tile and tile[-1] == 'z' and max_opp_prob > 0.8:
            base_def += 0.3
            
        return base_def

    def _calc_opportunity_cost(self, tile: str, hand_state: List[str], context: EvalContext) -> float:
        cost = 0.0
        # 形状進化ボーナス相殺（turn<=8の中張牌孤立は進化余地あり、切るとコストに）
        if context.turn <= 8 and tile and tile[0] in '34567' and hand_state.count(tile) == 1:
            cost += 0.4
            
        # 形状安定性
        # 過剰形を維持して切らない場合のペナルティ等の計算はスタブ
        
        return cost
        
    def _calc_iipeiko_bonus(self, tile: str, hand_state: List[str], context: EvalContext) -> float:
        # 一盃口過大評価の抑制
        # tile切断後に一盃口の可能性があるか（スタブ）
        return 0.0
