"""
server/game_loop.py
MVP用: 簡易辞書ステートを利用するゲームループ
"""
from enum import Enum
from server.core.deterministic_deck import DeterministicDeck
from server.core.agari_validator import AgariValidator, FuritenState
from server.core.score_calculator import ScoreCalculator
from server.core.yaku_identifier import YakuIdentifier
from server.utils.mahjong_logic import hand_to_34
from server.models import tile_from_str

class Player:
    def __init__(self):
        self.hand: list[str] = []
        
    def add(self, tile: str):
        self.hand.append(tile)
        self.hand.sort() # 文字列ソート（簡易）
        
    def discard(self, tile: str):
        if tile in self.hand:
            self.hand.remove(tile)

class GameLoop:
    STATE = Enum("State", "INIT DEALING DRAWING DISCARDING ACTION_CHECK ROUND_END")
    
    def __init__(self, seed: int = 42):
        self.state = self.STATE.INIT
        self.deck = DeterministicDeck(seed)
        self.players = [Player() for _ in range(4)]
        self.furiten_states = [FuritenState() for _ in range(4)]
        self.turn_idx = 0
        self.turn_count = 0
        self.discards: list[list[str]] = [[] for _ in range(4)]
        self.riichi_flags = [False]*4
        self.honba = 0
        self.round_number = 0
        self.scores = [25000, 25000, 25000, 25000]

    def start(self) -> dict:
        # 牌山生成済みなのでshuffle()呼び出しは不要
        
        # 配牌
        for _ in range(13):
            for i in range(4):
                self.players[i].add(self.deck.draw(1)[0])
                
        # 第一ツモ
        self.players[0].add(self.deck.draw(1)[0])
        self.state = self.STATE.DISCARDING
        return self._get_state_snapshot()

    def process_discard(self, player_idx: int, tile: str) -> dict:
        self.players[player_idx].discard(tile)
        self.discards[player_idx].append(tile)
        self.furiten_states[player_idx].record_discard(tile)
        
        # 他家がロンできるかチェック
        # TODO: 実際にはフロントエンドからの要求を待つが、ここではロジック疎通のみ
        
        self.turn_idx = (self.turn_idx + 1) % 4
        self.turn_count += 1
        
        draw_res = self.deck.draw(1)
        if not draw_res:
            return self.handle_ryukyoku()
            
        next_tile = draw_res[0]
        self.players[self.turn_idx].add(next_tile)
        self.state = self.STATE.DISCARDING
        
        return self._get_state_snapshot()
        
    def handle_ryukyoku(self):
        # 途中流局チェック
        # TODO: AgariValidator.check_abortive_draw を呼ぶ
        
        self.honba += 1
        self.turn_idx = 0
        self.turn_count = 0
        self.round_number += 1
        
        if self.round_number >= 8 or any(s <= 0 for s in self.scores):
            self.state = self.STATE.ROUND_END
            snapshot = self._get_state_snapshot()
            snapshot["phase"] = "game_end"
            return snapshot

        self.discards = [[] for _ in range(4)]
        self.deck = DeterministicDeck(seed=self.round_number + 100) # 次局の山
        self.deck.shuffle()
        
        for p in self.players:
            p.hand = []
        for _ in range(13):
            for i in range(4):
                self.players[i].add(self.deck.draw())
        self.players[0].add(self.deck.draw())
        self.state = self.STATE.DISCARDING
        
        snapshot = self._get_state_snapshot()
        snapshot["phase"] = "ryukyoku"
        return snapshot
        
    def _get_state_snapshot(self) -> dict:
        player_hand_tiles = [tile_from_str(t) for t in self.players[0].hand]
        hand_34 = hand_to_34(player_hand_tiles)
        
        return {
            "type": "state_update",
            "game_state": self.state.name,
            "current_player": self.turn_idx,
            "turn": self.turn_count,
            "hand": self.players[0].hand,
            "hand_34": hand_34,
            "discards": self.discards,
            "dora_indicator": self.deck.dora_indicator,
            "riichi_sticks": sum(self.riichi_flags),
            "scores": self.scores,
            "honba": self.honba,
            "riichi_flags": self.riichi_flags,
            "available_actions": [
                {"type": "discard", "tiles": list(set(self.players[0].hand))}
            ] if self.turn_idx == 0 and self.state == self.STATE.DISCARDING else []
        }
