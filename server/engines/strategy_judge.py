"""
server/engines/strategy_judge.py
方向性2: 戦略判断ルールエンジン - 盤面評価・攻守バランス判定
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class StrategyResult:
    tile: str
    judgment: str
    strategy_type: str
    scores: Dict[str, float]
    triggered_rules: List[str]

class StrategyJudge:
    """ルールベースによる盤面評価・攻守判断エンジン"""
    
    def __init__(self, catalog_path: str = "server/rules/strategy_catalog.json"):
        self.catalog = self._load_catalog(catalog_path)
        
    def _load_catalog(self, path: str) -> List[Dict]:
        if not os.path.exists(path):
            logger.warning(f"Strategy catalog not found: {path}. Using empty.")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def judge(self, context: Dict) -> StrategyResult:
        """盤面コンテキストから戦略判断を出力"""
        matched = self._filter_rules(context)
        
        if not matched:
            return StrategyResult(tile="5m", judgment="標準判断", strategy_type="BALANCE",
                                  scores={"attack": 0.5, "defense": 0.5, "situation": 0.5}, triggered_rules=[])
                                  
        # 重み集計
        atk = sum(r.get("w", {}).get("attack", 0.0) for r in matched) / len(matched)
        def_ = sum(r.get("w", {}).get("defense", 0.0) for r in matched) / len(matched)
        sit = sum(r.get("w", {}).get("situation", 0.0) for r in matched) / len(matched)
        
        stype = "ATTACK" if atk > def_ + 0.1 else "DEFEND" if def_ > atk + 0.1 else "BALANCE"
        tile = self._aggregate_recommendation(matched)
        judgment = self._build_judgment(context, stype, matched)
        
        return StrategyResult(tile=tile, judgment=judgment, strategy_type=stype,
                              scores={"attack": atk, "defense": def_, "situation": sit},
                              triggered_rules=[r["id"] for r in matched[:3]])

    def _filter_rules(self, ctx: Dict) -> List[Dict]:
        res = []
        for r in self.catalog:
            cond = r.get("cond", {})
            # 条件すべてが満たされるか (AND条件)
            match = True
            if cond.get("turn_min", 0) > ctx.get("turn", 0) or cond.get("turn_max", 24) < ctx.get("turn", 0):
                match = False
            if cond.get("riichi_min", 0) > ctx.get("riichi", 0):
                match = False
            if ctx.get("score_diff", 0) < cond.get("score_min", -99999) or ctx.get("score_diff", 0) > cond.get("score_max", 99999):
                match = False
            if "rank" in cond and cond["rank"] != ctx.get("rank", 1):
                match = False
            if "honba_min" in cond and cond["honba_min"] > ctx.get("honba", 0):
                match = False
            if "dealer" in cond and cond["dealer"] != ctx.get("dealer_status", False):
                match = False
            
            if match:
                res.append(r)
        return res

    def _aggregate_recommendation(self, rules: List[Dict]) -> str:
        tiles = [r.get("rec", "5m") for r in rules if r.get("rec")]
        return max(set(tiles), key=tiles.count) if tiles else "5m"

    def _build_judgment(self, ctx: Dict, stype: str, rules: List[Dict]) -> str:
        base = f"巡目{ctx.get('turn', 1)}・"
        if stype == "ATTACK":
            return f"{base}攻め優先。受入最大化のため{rules[0].get('rec', '中張')}を推奨" if rules else f"{base}攻め判断"
        if stype == "DEFEND":
            return f"{base}守り優先。他家圧力に対し安全牌切りを決定"
        return f"{base}攻防バランス維持。形状改良を優先"
