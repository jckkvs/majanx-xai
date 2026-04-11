from typing import List, Set, Optional
from dataclasses import dataclass, field

@dataclass
class FuritenState:
    discarded: Set[str] = field(default_factory=set)
    same_turn_passed: bool = False
    is_riichi: bool = False

    def can_ron(self, wait_tiles: Set[str]) -> bool:
        if self.is_riichi:
            return not bool(wait_tiles & self.discarded)
        if self.same_turn_passed:
            return False
        return not bool(wait_tiles & self.discarded)

    def record_discard(self, tile: str):
        self.discarded.add(tile)
        self.same_turn_passed = False

    def pass_ron(self):
        self.same_turn_passed = True


@dataclass
class DoraTracker:
    indicators: List[str] = field(default_factory=list)
    _kan_pending: int = 0

    def resolve_kan(self, kan_type: str, wall: List[str]) -> Optional[str]:
        if not wall: 
            return None
        if kan_type == "open_kan" or (kan_type == "added_kan" and self._kan_pending == 0):
            self._kan_pending = 1
        if self._kan_pending > 0:
            new_ind = wall.pop(0)
            self.indicators.append(new_ind)
            self._kan_pending -= 1
            return new_ind
        return None


class WinValidator:
    @staticmethod
    def validate_ron(tile: str, hand: List[str], furiten: FuritenState, 
                     yaku_calculator) -> bool:
        waits = yaku_calculator.get_waits(hand)
        if tile not in waits: 
            return False
        if not furiten.can_ron(waits): 
            return False
        return yaku_calculator.has_yaku(hand, tile, is_ron=True)

    @staticmethod
    def validate_tsumo(tile: str, hand: List[str], furiten: FuritenState,
                       yaku_calculator) -> bool:
        furiten.same_turn_passed = False # ツモで同巡フリテン解除
        return yaku_calculator.has_yaku(hand, tile, is_ron=False)
