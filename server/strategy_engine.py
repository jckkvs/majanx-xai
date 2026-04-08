from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from server.models import GameState
from server.round_context import RoundContext, MatchConfig

@dataclass
class StrategyRuleV2:
    id: str
    conditions: Dict[str, Any]
    action: str
    priority: float
    rationale: str
    weight_modifiers: Dict[str, float] = field(default_factory=dict)

@dataclass
class StrategyResultV2:
    strategy: str
    score: float
    rationale: str
    primary_rule_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class StrategyEngineV2:
    def __init__(self, rules_path: str = "server/rules/strategy_rules_v2.yaml"):
        self.rules: List[StrategyRuleV2] = []
        self._load_rules(rules_path)

    def _load_rules(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for r in data.get("rules", []):
            self.rules.append(StrategyRuleV2(
                id=r.get("id", ""),
                conditions=r.get("conditions", {}),
                action=r.get("action", "BALANCE"),
                priority=r.get("priority", 0.0),
                rationale=r.get("rationale", ""),
                weight_modifiers=r.get("weight_modifiers", {})
            ))

    def evaluate_conditions(self, conds: dict, ctx: dict) -> bool:
        for key, op_val in conds.items():
            if isinstance(op_val, dict):
                actual = ctx.get(key)
                if actual is None:
                    return False
                for op, val in op_val.items():
                    if op == "gte" and not (actual >= val): return False
                    if op == "lte" and not (actual <= val): return False
                    if op == "gt" and not (actual > val): return False
                    if op == "lt" and not (actual < val): return False
                    if op == "eq" and not (actual == val): return False
                    if op == "in" and actual not in val: return False
                    if op == "has_any":
                        if not any(v in actual for v in val): return False
                    if op == "has_all":
                        if not all(v in actual for v in val): return False
            else:
                if ctx.get(key) != op_val: return False
        return True

    def score_rule(self, rule: StrategyRuleV2, ctx: dict) -> float:
        if not self.evaluate_conditions(rule.conditions, ctx): 
            return 0.0
            
        base = rule.priority
        mods = rule.weight_modifiers
        
        # 状況に応じた動的重み補正
        if "urgency_index" in mods: 
            base *= (1.0 + (ctx.get("urgency_index", 0.0) * mods["urgency_index"]))
            
        if "danger_threshold" in mods: 
            ctx["danger_tolerance"] = mods["danger_threshold"]
            
        return base

    def compute_base_push_fold(self, game_state: GameState, ctx_metrics: RoundContext) -> str:
        # Expected_Value_Push = (Win_Prob * Avg_Win_Points * Match_Weight) - (Loss_Prob * Avg_Loss_Points * Opponent_Tenpai_Prob)
        # Push_Threshold = 1500 * (1 - Urgency_Index) + 3000 * Urgency_Index
        
        # スタブ近似
        expected_value_push = 2000.0 if ctx_metrics.rank > 2 else 0.0 # ダミー値
        threshold = ctx_metrics.push_fold_threshold
        
        if expected_value_push > threshold:
            return "ATTACK"
        elif expected_value_push < -1000:
            return "DEFEND"
        return "BALANCE"

    def decide_strategy(self, game_state: GameState, cfg: MatchConfig) -> StrategyResultV2:
        ctx_obj = RoundContext.build(game_state, cfg)
        ctx_dict = ctx_obj.__dict__.copy()
        ctx_dict["is_dealer"] = (game_state.dealer == game_state.current_player)
        
        scored_rules = []
        for rule in self.rules:
            score = self.score_rule(rule, ctx_dict)
            if score > 0:
                scored_rules.append((score, rule))
                
        # 同一スコア時の優先度解決はrankなどを考慮可能だが、一旦降順ソート
        scored_rules.sort(key=lambda x: x[0], reverse=True)
        
        if not scored_rules:
            # 適合ルールなし時は数式判定へフォールバック
            base_strat = self.compute_base_push_fold(game_state, ctx_obj)
            return StrategyResultV2(
                strategy=base_strat,
                score=0.5,
                rationale=f"数式ベースの押し引き判定（閾値: {ctx_obj.push_fold_threshold:.0f}）で {base_strat} を選択。",
                primary_rule_id="BASE_EQ",
                metadata={"urgency": ctx_obj.urgency_index}
            )
            
        best_score, best_rule = scored_rules[0]
        
        return StrategyResultV2(
            strategy=best_rule.action,
            score=best_score,
            rationale=best_rule.rationale,
            primary_rule_id=best_rule.id,
            metadata={"ctx": ctx_dict, "evaluated": len(scored_rules)}
        )
