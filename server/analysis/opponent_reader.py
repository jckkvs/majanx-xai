# server/analysis/opponent_reader.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
from collections import defaultdict, Counter

@dataclass(frozen=True)
class OpponentState:
    player_id: int
    tenpai_probability: float
    likely_waits: List[str]
    discard_pattern: str  # "early_safety" | "value_seek" | "balanced"
    risk_multiplier: float

class OpponentReader:
    """他家の捨牌・鳴き・宣言から手牌状態を推定"""
    
    def __init__(self):
        self.river_history: Dict[int, List[str]] = defaultdict(list)
        self.call_history: Dict[int, List[dict]] = defaultdict(list)
        self.visible_tiles: Dict[str, int] = defaultdict(int)
        
    def update_river(self, player_id: int, tile: str):
        self.river_history[player_id].append(tile)
        self.visible_tiles[tile] += 1
        
    def update_call(self, player_id: int, call_type: str, exposed: List[str]):
        self.call_history[player_id].append({"type": call_type, "tiles": exposed})
        for t in exposed:
            self.visible_tiles[t] += 1
            
    def estimate(self, player_id: int, current_turn: int) -> OpponentState:
        discards = self.river_history.get(player_id, [])
        calls = self.call_history.get(player_id, [])
        
        tenpai_prob = self._estimate_tenpai_prob(discards, calls, current_turn)
        waits = self._infer_waits(discards, calls)
        pattern = self._classify_pattern(discards)
        
        # 聴牌確率に応じた危険度係数
        risk_mult = 1.0 + (tenpai_prob * 0.8)
        
        return OpponentState(
            player_id=player_id,
            tenpai_probability=tenpai_prob,
            likely_waits=waits,
            discard_pattern=pattern,
            risk_multiplier=risk_mult
        )
        
    def _estimate_tenpai_prob(self, discards: List[str], calls: List[dict], turn: int) -> float:
        if turn < 4:
            return 0.05 + len(calls) * 0.1
        if turn < 8:
            base = 0.2 + (len(calls) * 0.15)
        else:
            base = 0.5 + (len(calls) * 0.12)
            
        # 終盤リーチ宣言があれば確定
        if turn >= 10 and not discards:
            base += 0.3
            
        return max(0.0, min(1.0, base))
        
    def _infer_waits(self, discards: List[str], calls: List[dict]) -> List[str]:
        # 簡易推論: 捨てられていない中張牌を候補とする
        # 実運用時はテンパイ形データベース照合或いはベイズ推定を適用
        all_tiles = {f"{s}{n}" for s in ['m','p','s'] for n in range(1,10)} | {f"{i}z" for i in range(1,8)}
        discarded_set = set(discards)
        exposed = {t for c in calls for t in c["tiles"]}
        visible = discarded_set | exposed
        
        candidates = [t for t in all_tiles if t not in visible]
        # 役牌・ドラは除外、中張両面待ちを優先
        prioritized = sorted(candidates, key=lambda x: (x[0]!='z', x[1] not in ['1','9']))
        return prioritized[:5]
        
    def _classify_pattern(self, discards: List[str]) -> str:
        if len(discards) < 5:
            return "balanced"
        early = discards[:5]
        honor_count = sum(1 for t in early if t.endswith('z'))
        if honor_count >= 3:
            return "value_seek"
        terminal_count = sum(1 for t in early if t[1] in ['1','9'] and not t.endswith('z'))
        if terminal_count >= 3:
            return "early_safety"
        return "balanced"
