import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from server.models import Tile, GameState

@dataclass
class OpponentState:
    seat: int
    discards: List[str]
    is_riichi: bool
    call_count: int
    tenpai_prob: float = 0.05
    danger_map: Dict[str, float] = field(default_factory=dict)
    wait_shape: str = "unknown"

class OpponentModel:
    def __init__(self, num_seats: int = 4):
        self.players = [OpponentState(seat=i, discards=[], is_riichi=False, call_count=0) for i in range(num_seats)]

    def update(self, game_state: GameState) -> None:
        for i, p in enumerate(game_state.players):
            opp = self.players[i]
            opp.discards = [t.id for t in p.discards]
            opp.is_riichi = p.is_riichi
            opp.call_count = len(p.melds)
            self._update_tenpai_prob(opp, game_state.turn_count)
            self._update_danger_map(opp, game_state)
            self._estimate_wait_shape(opp, game_state.turn_count)

    def _update_tenpai_prob(self, opp: OpponentState, turn: int) -> None:
        base = min(0.9, 0.05 + turn * 0.045)
        if opp.is_riichi: 
            base = 0.95
        elif opp.call_count > 0: 
            base += 0.15
            
        recent = opp.discards[-5:]
        if any(t in recent for t in ['1m','9m','1p','9p','1s','9s']): 
            base -= 0.10
            
        opp.tenpai_prob = float(np.clip(base, 0.05, 0.95))

    def _update_danger_map(self, opp: OpponentState, gs: GameState) -> None:
        tile_counts = self._count_visible_tiles(gs)
        danger = {}
        for suit, nums in [('m', range(1,10)), ('p', range(1,10)), ('s', range(1,10)), ('z', range(1,8))]:
            for n in nums:
                tid = f"{n}{suit}"
                # 振聴/現物判定
                if f"{n}{suit}" in opp.discards or f"{n}{suit}r" in opp.discards:
                    danger[tid] = 0.0
                    continue
                
                wall = tile_counts.get(tid, 0)
                if wall >= 3: 
                    danger[tid] = 0.05
                    continue
                if wall == 2: 
                    danger[tid] = 0.25
                    continue
                
                base = 0.5 if suit != 'z' else 0.4
                if opp.is_riichi:
                    for dj in opp.discards:
                        if len(dj) > 1 and dj[-1] == suit:
                            djn = int(dj[:-1])
                            # 筋判定
                            if abs(djn - n) == 3: 
                                base = min(base, 0.35)
                
                danger[tid] = min(0.90, base + gs.turn_count * 0.015)
        opp.danger_map = danger

    def _count_visible_tiles(self, gs: GameState) -> Dict[str, int]:
        counts = {}
        for p in gs.players:
            for t in p.discards + [c for m in p.melds for c in m.tiles]:
                counts[t.id] = counts.get(t.id, 0) + 1
        for t in gs.wall + gs.dead_wall:
            counts[t.id] = counts.get(t.id, 0) + 1
        return counts

    def _estimate_wait_shape(self, opp: OpponentState, turn: int) -> None:
        if opp.is_riichi:
            opp.wait_shape = "riichi_multi" if len(opp.discards) < 10 else "riichi_single"
            return
            
        mid_cuts = sum(1 for d in opp.discards[-8:] if d and d[0] in '34567')
        term_cuts = sum(1 for d in opp.discards[-8:] if d and d[0] in '1289')
        
        if mid_cuts >= 4: 
            opp.wait_shape = "multi_shape"
        elif term_cuts >= 4: 
            opp.wait_shape = "pair_kanchan"
        else: 
            opp.wait_shape = "mixed"
