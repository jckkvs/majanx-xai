"""
方向性3: Mortal推奨牌の戦術意図逆推論・パターンマッチング・言語化エンジン
牌形状・場況フィルタ・確信度重み・複数解釈統合を実装
"""
from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.models import GameState

@dataclass
class InterpretationRule:
    rule_id: str
    tile_pattern: str
    context_filter: str
    template: str
    confidence: float

@dataclass
class MortalInterpretationResult:
    primary_interpretation: str
    matched_rules: List[str]
    confidence: float
    alternatives: List[str]
    raw_data: Dict[str, Any] = field(default_factory=dict)

class MortalInterpreter:
    def __init__(self, rules_path: str = "server/rules/mortal_rules.yaml"):
        self.rules: List[InterpretationRule] = []
        self._load_rules(rules_path)
        self.templates = {
            "efficiency": "牌効率最適化による形状維持",
            "defense": "危険度回避・降り移行判断",
            "value": "打点形成・逆転条件確保",
            "reading": "他家待ち筋回避・牌山読み介入",
        }

    def _load_rules(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for r in data.get("rules", []):
            self.rules.append(InterpretationRule(**r))

    def match_rules(self, game_state: GameState, recommended_tile: str, mortal_prob: float) -> List[InterpretationRule]:
        matched = []
        turn = game_state.turn_count
        riichi_cnt = sum(1 for p in game_state.players if p.is_riichi)
        danger = min(0.9, turn * 0.04 + riichi_cnt * 0.15)

        for rule in self.rules:
            cond_match = True
            if "CTX_TURN" in rule.context_filter:
                if "<=6" in rule.context_filter and turn > 6: cond_match = False
                elif ">=7" in rule.context_filter and turn < 7: cond_match = False
                elif ">=8" in rule.context_filter and turn < 8: cond_match = False
            if "CTX_RIICHI" in rule.context_filter:
                if ">=1" in rule.context_filter and riichi_cnt < 1: cond_match = False
            if "CTX_DANGER" in rule.context_filter:
                if ">=0.6" in rule.context_filter and danger < 0.6: cond_match = False

            if cond_match and (rule.tile_pattern.lower() in recommended_tile.lower() or rule.tile_pattern == "*"):
                matched.append(rule)
        return sorted(matched, key=lambda x: x.confidence, reverse=True)

    def interpret(self, game_state: GameState, recommended_tile: str, mortal_prob: float) -> MortalInterpretationResult:
        matched = self.match_rules(game_state, recommended_tile, mortal_prob)
        if not matched:
            return MortalInterpretationResult(
                primary_interpretation=f"「{recommended_tile}」の意図は場況依存の標準判断。確率{mortal_prob:.1%}の根拠は形状維持と危険度回避の均衡",
                matched_rules=[],
                confidence=0.4,
                alternatives=["牌効率優先", "安全度調整"],
                raw_data={"fallback": True},
            )

        primary = matched[0]
        alts = [r.template.split("：")[0] if "：" in r.template else "代替解釈" for r in matched[1:3]]
        conf = primary.confidence * (0.8 + 0.2 * min(mortal_prob, 1.0))

        explanation = primary.template.format(tile=recommended_tile)
        return MortalInterpretationResult(
            primary_interpretation=explanation,
            matched_rules=[r.rule_id for r in matched],
            confidence=conf,
            alternatives=alts,
            raw_data={"prob": mortal_prob, "turn": game_state.turn_count, "riichi": sum(1 for p in game_state.players if p.is_riichi)},
        )
