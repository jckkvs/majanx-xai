"""
server/game_loop.py
MVP用: 簡易辞書ステートを利用するゲームループ
"""
from enum import Enum
from server.tile_wall import TileWall

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
    
    def __init__(self, config: dict = None):
        self.state = self.STATE.INIT
        self.wall = TileWall()
        self.players = [Player() for _ in range(4)]
        self.turn_idx = 0
        self.turn_count = 0
        self.discards: list[list[str]] = [[] for _ in range(4)]
        self.riichi_flags = [False]*4
        self.honba = 0
        self.round_number = 0
        self.scores = [25000, 25000, 25000, 25000]

    def start(self) -> dict:
        self.wall.build()
        
        # 簡易配牌
        for _ in range(13):
            for i in range(4):
                self.players[i].add(self.wall.draw())
                
        # 最初のツモはturn_idx=0が引いた体で
        self.players[0].add(self.wall.draw())
        
        self.state = self.STATE.DISCARDING
        return self._get_state_snapshot()

    def process_discard(self, player_idx: int, tile: str) -> dict:
        self.players[player_idx].discard(tile)
        self.discards[player_idx].append(tile)
        
        # 次のターンの準備
        self.turn_idx = (self.turn_idx + 1) % 4
        self.turn_count += 1
        
        next_tile = self.wall.draw()
        if not next_tile:
            return self.handle_ryukyoku()
            
        self.players[self.turn_idx].add(next_tile)
        self.state = self.STATE.DISCARDING
        
        return self._get_state_snapshot()
        
    def handle_ryukyoku(self):
        # 1. 簡易版の流局処理（MVP用なので点数計算・聴牌判定は省略または仮）
        self.honba += 1
        self.turn_idx = 0
        self.turn_count = 0
        self.round_number += 1
        
        # 3. ゲーム終了判定 (今回は無限ループを防ぐため簡易リセット)
        if self.round_number >= 8 or any(s <= 0 for s in self.scores):
            self.state = self.STATE.ROUND_END
            snapshot = self._get_state_snapshot()
            snapshot["phase"] = "game_end"
            return snapshot
        self.discards = [[] for _ in range(4)]
        self.wall.build()
        for p in self.players:
            p.hand = []
        for _ in range(13):
            for i in range(4):
                self.players[i].add(self.wall.draw())
        self.players[0].add(self.wall.draw())
        self.state = self.STATE.DISCARDING
        
        snapshot = self._get_state_snapshot()
        # 通知用に ryukyoku フェーズであることを付与
        snapshot["phase"] = "ryukyoku"
        return snapshot
        
    def _get_state_snapshot(self) -> dict:
        return {
            "type": "state_update",
            "game_state": self.state.name,
            "current_player": self.turn_idx,
            "turn": self.turn_count,
            "hand": self.players[0].hand, # UIはPlayer 0視点を想定
            "discards": self.discards,
            "dora_indicator": self.wall.dora_indicator,
            "riichi_sticks": sum(self.riichi_flags),
            "scores": self.scores,
            "available_actions": [
                {"type": "discard", "tiles": list(set(self.players[0].hand))}
            ] if self.turn_idx == 0 and self.state == self.STATE.DISCARDING else []
        }
