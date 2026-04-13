"""
server/game_loop.py
MVP用: 簡易辞書ステートを利用するゲームループ
"""
from enum import Enum
from server.core.deterministic_deck import DeterministicDeck
from server.core.mahjong_engine import MahjongEngine, MahjongGameState
from server.core.deterministic_deck import DeterministicDeck
from server.models import tile_from_str, GameState as MJGameState, PlayerState as MJPlayerState, TileSuit, Wind
from server.rules.rule_validator import FuritenState

class Player:
    def __init__(self):
        self.hand: list[str] = []
        self._tile_order = ["1m","2m","3m","4m","5m","6m","7m","8m","9m",
                            "1p","2p","3p","4p","5p","6p","7p","8p","9p",
                            "1s","2s","3s","4s","5s","6s","7s","8s","9s",
                            "E","S","W","N","Wh","Gr","Rd", "0m", "0p", "0s"]
        
    def add(self, tile: str):
        self.hand.append(tile)
        self.hand.sort(key=lambda x: self._tile_order.index(x) if x in self._tile_order else 99)
        
    def discard(self, tile: str):
        if tile in self.hand:
            self.hand.remove(tile)

class GameLoop:
    STATE = Enum("State", "INIT DEALING DRAWING DISCARDING ACTION_CHECK ROUND_END")
    
    def __init__(self, seed: int | None = None):
        self.state = self.STATE.INIT
        import time
        if seed is None:
            seed = int(time.time() * 1000) % (2**32)
        self._initial_seed = seed
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
        self.open_melds: list[list[list[str]]] = [[] for _ in range(4)]  # 副露/暗槓

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

    # ── 暗槓処理 ──────────────────────────────
    def check_ankan(self, player_idx: int) -> list[str]:
        """手牌中に同一牌が4枚あるものを検出して返す"""
        from collections import Counter
        counts = Counter(self.players[player_idx].hand)
        return [tile for tile, cnt in counts.items() if cnt >= 4]

    def process_ankan(self, player_idx: int, tile: str) -> dict:
        """暗槓処理: 手牌から4枚除去 → 嶺上ツモ"""
        hand = self.players[player_idx].hand
        # 4枚除去
        for _ in range(4):
            if tile in hand:
                hand.remove(tile)
        # 暗槓として記録
        self.open_melds[player_idx].append([tile, tile, tile, tile])
        
        # 嶺上ツモ (牌山の末尾から引く)
        draw_res = self.deck.draw(1)
        if not draw_res:
            return self.handle_ryukyoku()
        rinshan_tile = draw_res[0]
        self.players[player_idx].add(rinshan_tile)
        # 暗槓後は打牌フェーズ
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
        import time
        next_seed = int(time.time() * 1000) % (2**32)
        self.deck = DeterministicDeck(seed=next_seed)
        
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
        from server.utils.mahjong_logic import hand_to_34
        hand_34 = hand_to_34(player_hand_tiles)
        
        # MahjongEngine を使用した評価 (Player 0 視点)
        m_gs = MahjongGameState(
            hand_34=hand_34,
            river=sum(self.discards, []),
            visible_counts={}, #TODO: 正確なカウントの実装
            turn=self.turn_count,
            riichi_players={i for i, f in enumerate(self.riichi_flags) if f},
            honba=self.honba,
            riichi_sticks=sum(self.riichi_flags),
            is_dealer=(self.turn_idx == 0) # 簡易化
        )
        eval_res = MahjongEngine.evaluate_discard(m_gs)
        
        # 危険度マップの作成
        river_danger_map = []
        for p_idx in range(4):
            p_discards = []
            for d_str in self.discards[p_idx]:
                # 簡易判定
                p_discards.append({"tile": d_str, "danger": 0.0})
            river_danger_map.append(p_discards)

        # 各プレイヤーの手牌枚数
        hand_counts = [len(self.players[i].hand) for i in range(4)]

        # 自分がツモ番で暗槓できるか
        actions = []
        if self.turn_idx == 0 and self.state == self.STATE.DISCARDING:
            actions.append({"type": "discard", "tiles": list(set(self.players[0].hand))})
            ankan_tiles = self.check_ankan(0)
            if ankan_tiles:
                actions.append({"type": "kan", "tiles": ankan_tiles})

        return {
            "type": "state_update",
            "game_state": self.state.name,
            "current_player": self.turn_idx,
            "turn": self.turn_count,
            "hand": self.players[0].hand,
            "hand_34": hand_34,
            "discards": [list(d) for d in self.discards],
            "hand_counts": hand_counts,
            "open_melds": [list(m) for m in self.open_melds],
            "river_danger": river_danger_map,
            "shanten": eval_res["shanten"],
            "ukeire": eval_res["ukeire"],
            "dora_indicator": self.deck.dora_indicator,
            "scores": self.scores,
            "round_number": self.round_number,
            "available_actions": actions
        }
