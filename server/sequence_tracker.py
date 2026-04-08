from collections import deque
from dataclasses import dataclass
from typing import List
from server.models import GameState, Tile

@dataclass
class DiscardEvent:
    turn: int
    tile_id: str
    is_tsumogiri: bool
    intent_tag: str
    sequence_tag: str

class SequenceTracker:
    def __init__(self, window_size: int = 5):
        self.history: deque[DiscardEvent] = deque(maxlen=window_size)
        
    def update(self, gs: GameState, seat: int, drawn: Tile = None) -> DiscardEvent:
        p = gs.players[seat]
        if not p.discards:
            # 安全のため空の場合は何もしない（通常呼ばれない）
            raise ValueError("No discards found")
            
        discarded = p.discards[-1]
        
        # ツモ切り判定: drawn が明示的に与えられているか、またはGameモデル側で
        # last_drawn_tile のトラッキングがあればそれを使用。
        # なければ近似ロジック。
        is_tsumo = False
        if drawn and drawn.id == discarded.id:
            is_tsumo = True
            
        intent = self._classify_intent(discarded, gs, seat)
        seq_tag = self._tag_sequence(is_tsumo, intent)
        
        evt = DiscardEvent(gs.turn_count, discarded.id, is_tsumo, intent, seq_tag)
        self.history.append(evt)
        return evt
        
    def _classify_intent(self, discarded: Tile, gs: GameState, seat: int) -> str:
        # TODO: より詳細な分類処理
        if discarded.suit.value == 'z':
            return "DEFENSIVE"
        elif discarded.number in [4,5,6]:
            return "CHANGE"
        return "NORMAL"
        
    def _tag_sequence(self, is_tsumo: bool, intent: str) -> str:
        # TODO: 履歴に基づくタグ付け（例：TSUMO_STREAK_3+ など）
        if is_tsumo:
            return "TSUMO_STREAK"
        return "ISOLATED"
