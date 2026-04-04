import json
from typing import List, Dict, Optional

from server.models import (
    GameState, PlayerState, GamePhase, Tile, Wind, TileSuit,
    Meld, MeldType, tile_from_str
)
from server.commentator import CommentatorAI
from server.mortal.mortal_agent import MortalAgent

class ReplayManager:
    """
    mjaiイベント列からGameStateを構築し、再生制御を行うマネージャー。
    """
    def __init__(self, engine_mock=None):
        self.events: List[Dict] = []
        self.current_index = 0
        self.state = GameState()
        # CommentatorはGameEngineインターフェースを要求するので簡易モックとして自分自身等を使用可能
        # 今回は ReplayManager自体の state を参照させられればよい
        
        class EngineMock:
            def __init__(self, rm):
                self.rm = rm
            @property
            def state(self):
                return self.rm.state
            def _hand_to_34(self, hand: List[Tile]) -> List[int]:
                arr = [0]*34
                for t in hand:
                    idx = t.suit.value * 9 + t.number - 1 if t.suit.value < 3 else 27 + t.number - 1
                    arr[idx] += 1
                return arr

        self._engine_mock = EngineMock(self)
        self.commentator = CommentatorAI(self._engine_mock)
        # 解析用のMortalAgent (seat 0をデフォルト評価対象とするか、手番プレイヤーに合わせる)
        self.mortal = MortalAgent(0, self._engine_mock)
        self.last_analysis = None
        self.names = ["Player 1", "Player 2", "Player 3", "Player 4"]

    def load_log(self, mjai_events: List[Dict]):
        """mjaiイベント配列を読み込む"""
        self.events = mjai_events
        self.current_index = 0
        self._init_state()

    def _init_state(self):
        self.state = GameState()
        """プレイヤー状態の初期化"""
        self.state.players = [PlayerState(seat=i) for i in range(4)]
        self.last_analysis = None

    def step_forward(self) -> bool:
        """次のイベントを処理。終了した場合はFalse."""
        if self.current_index >= len(self.events):
            return False
        
        event = self.events[self.current_index]
        self._process_event(event)

        # AI解説の更新: 打牌の直前(ツモ時)、または他家の打牌時(鳴き判定用)
        t = event["type"]
        if t in ["tsumo", "dahai", "chi", "pon", "daiminkan", "ankan", "kakan"]:
            actor = event.get("actor", 0)
            self._update_analysis(actor)

        self.current_index += 1
        return True

    def step_backward(self) -> bool:
        """1手戻る（全体を初期化して、1手前まで再シミュレート）"""
        if self.current_index <= 0:
            return False
            
        target_idx = self.current_index - 1
        self.current_index = 0
        self._init_state()
        
        while self.current_index < target_idx:
            # 内部進行ではAI解析をスキップ(高速化)
            self._process_event(self.events[self.current_index])
            self.current_index += 1
            
        # 最後の1手でのみAI解析を実行
        if self.current_index < len(self.events):
             event = self.events[self.current_index - 1] if self.current_index > 0 else None
             if event and event["type"] in ["tsumo", "dahai", "chi", "pon", "daiminkan", "ankan", "kakan"]:
                 actor = event.get("actor", 0)
                 self._update_analysis(actor)

        return True

    def _update_analysis(self, actor: int):
        """指定プレイヤー席でのAI解説を更新"""
        try:
            self.mortal.seat = actor
            mortal_probs = self.mortal._get_probabilities()
            self.last_analysis = self.commentator.analyze(actor, mortal_probs)
        except Exception as e:
            print(f"[ReplayManager] Analysis err: {e}")
            self.last_analysis = None

    def _process_event(self, event: Dict):
        """個別のmjaiイベントを適用"""
        t = event.get("type", "")
        if t == "start_game":
            self.names = event.get("names", self.names)
            
        elif t == "start_kyoku":
            self.state = GameState()
            self.state.players = [PlayerState(seat=i) for i in range(4)]
            self.state.round_number = event.get("kyoku", 1) - 1
            wk = event.get("bakaze", "E")
            wind_map = {"E": Wind.EAST, "S": Wind.SOUTH, "W": Wind.WEST, "N": Wind.NORTH}
            self.state.round_wind = wind_map.get(wk, Wind.EAST)
            self.state.honba = event.get("honba", 0)
            self.state.riichi_sticks = event.get("kyotaku", 0)
            self.state.dealer = event.get("oya", 0)
            
            dora_marker = event.get("dora_marker")
            if dora_marker and dora_marker != "?":
                self.state.dora_indicators.append(tile_from_str(dora_marker))
                
            tehais = event.get("tehais", [[], [], [], []])
            for i, p_hand in enumerate(tehais):
                if p_hand:
                    # '?' の場合は裏向きだが、今回は解析用のダミー牌か無視を追加
                    v_hand = [tile_from_str(pai) for pai in p_hand if pai != '?']
                    self.state.players[i].hand = v_hand
            self.state.phase = GamePhase.PLAYER_TURN

        elif t == "tsumo":
            actor = event["actor"]
            pai = event["pai"]
            if pai != '?':
                self.state.players[actor].add_tile(tile_from_str(pai))
            self.state.current_player = actor
            self.state.turn_count += 1

        elif t == "dahai":
            actor = event["actor"]
            pai = event["pai"]
            tile = tile_from_str(pai)
            try:
                self.state.players[actor].remove_tile(tile)
            except ValueError:
                pass # 見えない手牌'?'などの都合
            self.state.players[actor].discards.append(tile)
            self.state.last_discard = tile
            self.state.last_discard_player = actor
            self.state.current_player = actor

        elif t == "riichi":
            actor = event["actor"]
            self.state.players[actor].is_riichi = True

        elif t == "riichi_accepted":
            actor = event["actor"]
            # スコア変動や供託増加は任意で簡易再現
            pass

        elif t == "chi" or t == "pon" or t == "daiminkan":
            actor = event["actor"]
            target = event["target"]
            pai = tile_from_str(event["pai"])
            consumed = [tile_from_str(p) for p in event["consumed"]]
            
            for c in consumed:
                try:
                    self.state.players[actor].remove_tile(c)
                except ValueError:
                    pass
            
            m_type = MeldType.CHI if t == "chi" else MeldType.PON if t == "pon" else MeldType.DAIMINKAN
            self.state.players[actor].melds.append(Meld(
                meld_type=m_type,
                tiles=consumed + [pai],
                called_tile=pai,
                from_player=target
            ))
            
            # 捨て牌から対象を削除
            if self.state.players[target].discards:
                self.state.players[target].discards.pop()

        elif t == "ankan" or t == "kakan":
            actor = event["actor"]
            consumed = [tile_from_str(p) for p in event["consumed"]]
            for c in consumed:
                try:
                    self.state.players[actor].remove_tile(c)
                except ValueError:
                    pass
            m_type = MeldType.ANKAN if t == "ankan" else MeldType.KAKAN
            self.state.players[actor].melds.append(Meld(
                meld_type=m_type,
                tiles=consumed
            ))

        elif t == "dora":
            dora_marker = event.get("dora_marker")
            if dora_marker and dora_marker != "?":
                self.state.dora_indicators.append(tile_from_str(dora_marker))

        elif t == "hora" or t == "ryukyoku":
            self.state.phase = GamePhase.ROUND_END

    def to_client_dict(self):
        """クライアント向けにGameStateを辞書化(GameManager相当)"""
        # (簡略化した互換出力)
        players = []
        for p in self.state.players:
            players.append({
                "seat": p.seat,
                "score": p.score,
                "hand": [t.id for t in p.hand],
                "discards": [t.id for t in p.discards],
                "melds": [{"type": m.meld_type.value, "tiles": [t.id for t in m.tiles]} for m in p.melds],
                "is_riichi": p.is_riichi,
                "name": self.names[p.seat]
            })

        return {
            "round_name": self.state.round_name_ja,
            "honba": self.state.honba,
            "riichi_sticks": self.state.riichi_sticks,
            "tiles_remaining": self.state.tiles_remaining,
            "dora_indicators": [t.id for t in self.state.dora_indicators],
            "dealer": self.state.dealer,
            "current_player": self.state.current_player,
            "turn_count": self.state.turn_count,
            "phase": self.state.phase.value,
            "players": players
        }
