# server/tile_eval/risk_estimator.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from functools import lru_cache
import json

@dataclass(frozen=True)
class RiskScore:
    deal_in_probability: float  # 0.0 (完全安全) 〜 1.0 (確定放銃)
    danger_level: str           # "safe" | "caution" | "danger" | "fatal"
    primary_factor: str         # 判定根拠ラベル

class RiskEstimator:
    """牌の危険度を局所的な牌理・統計・状況から推定するモジュール"""
    
    SUJI_MAP = {
        1: {4, 7}, 2: {5, 8}, 3: {6, 9},
        4: {1, 7}, 5: {2, 8}, 6: {3, 9},
        7: {1, 4}, 8: {2, 5}, 9: {3, 6}
    }
    
    TERMINAL_NUMBERS = {'1', '9'}
    HONOR_TILES = {'1z', '2z', '3z', '4z', '5z', '6z', '7z'}
    
    @classmethod
    @lru_cache(maxsize=512)
    def evaluate(
        cls,
        tile: str,
        river_str: str,
        riichi_player_count: int,
        turn: int,
        visible_counts_str: str
    ) -> RiskScore:
        """
        牌の危険度評価
        
        Args:
            tile: 評価対象牌 (例: "3m")
            river_str: 河の文字列結合 (例: "1m5s2p...")
            riichi_player_count: リーチ宣言者数
            turn: 現在巡目
            visible_counts_str: 牌ごとの表示枚数JSON文字列
        """
        risk_val = 0.0
        factors = []
        
        visible_counts = json.loads(visible_counts_str)
        river_set = set(river_str[i:i+2] for i in range(0, len(river_str), 2))
        
        # 1. 現物判定
        if tile in river_set:
            return RiskScore(0.0, "safe", "現物")
            
        # 2. スジ判定
        is_suji_safe = cls._check_suji(tile, river_set)
        if is_suji_safe:
            risk_val += 0.05
            factors.append("スジ")
            
        # 3. ターム・字牌判定
        is_terminal_or_honor = cls._is_terminal_or_honor(tile)
        if is_terminal_or_honor:
            risk_val += 0.15
            factors.append("端牌/字牌")
            
        # 4. カベ判定 (簡易: 4枚見えていれば安全度上昇)
        remaining = 4 - visible_counts.get(tile, 0)
        if remaining <= 1:
            risk_val += 0.10
            factors.append("カベ")
            
        # 5. リーチ他家による危険度スケーリング
        if riichi_player_count > 0:
            risk_val += 0.30 * riichi_player_count
            if turn >= 8 and not is_terminal_or_honor:
                risk_val += 0.15
                factors.append("リーチ後中張")
            if turn >= 12:
                risk_val += 0.10
                factors.append("終盤リーチ")
                
        # 6. 正規化 (0.0 〜 1.0)
        risk_val = max(0.0, min(1.0, risk_val))
        
        # 7. 危険度レベル分類
        level = cls._classify_level(risk_val)
        primary = factors[0] if factors else "統計ベース"
        
        return RiskScore(risk_val, level, primary)
        
    @classmethod
    def _check_suji(cls, tile: str, river_set: Set[str]) -> bool:
        if len(tile) < 2 or tile[0] in ['z']:
            return False
        num = int(tile[1])
        if not (1 <= num <= 9):
            return False
        suji_targets = cls.SUJI_MAP.get(num, set())
        for s in suji_targets:
            if f"{tile[0]}{s}" in river_set:
                return True
        return False
        
    @classmethod
    def _is_terminal_or_honor(cls, tile: str) -> bool:
        if len(tile) < 2:
            return False
        return tile in cls.HONOR_TILES or tile[1] in cls.TERMINAL_NUMBERS
        
    @classmethod
    def _classify_level(cls, risk: float) -> str:
        if risk < 0.15: return "safe"
        if risk < 0.35: return "caution"
        if risk < 0.65: return "danger"
        return "fatal"
