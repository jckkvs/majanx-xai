# server/endpoints/game.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import random
from typing import List, Dict, Optional
from core.rules.mahjong_engine import MahjongRuleEngine
from server.endpoints.inference import suggest_move, InferenceRequest, get_registry
from core.monitoring.metrics import WS_CONNECTIONS

router = APIRouter(prefix="/ws", tags=["ゲームWebSocket"])

rule_engine = MahjongRuleEngine()

class Player:
    def __init__(self, ws: Optional[WebSocket], seat: int, is_human: bool = False):
        self.ws = ws
        self.seat = seat
        self.is_human = is_human
        self.hand: List[str] = []
        self.river: List[str] = []
        self.score = 25000

class GameState:
    def __init__(self):
        self.players: Dict[int, Player] = {}
        self.wall: List[str] = []
        self.turn_seat: int = 0
        self.dealer: int = 0
        self.kyoku: int = 1  # 1: 東1, 2: 東2...
        self.honba: int = 0
        self.dora_indicators: List[str] = []
        self.current_draw: Optional[str] = None
        self.is_active: bool = False
        self._lock = asyncio.Lock()
        self.logger = None # main.py でセットされる想定

    def init_wall(self) -> None:
        suits = ['m', 'p', 's']
        wall = [f"{n}{s}" for s in suits for n in range(1, 10)] * 4
        wall += [f"{n}z" for n in range(1, 8)] * 4
        random.shuffle(wall)
        self.wall = wall

    def deal_initial(self) -> None:
        for seat in range(4):
            p = self.players[seat]
            p.hand = self.wall[seat*13 : (seat+1)*13]
        self.dora_indicators = [self.wall.pop()]
        self.current_draw = self.wall.pop()
        self.is_active = True

    async def process_human_discard(self, seat: int, tile: str) -> Dict:
        """人間の打牌を厳密に検証・状態更新"""
        async with self._lock:
            if not self.is_active:
                return {"error": "Game not active"}
            if seat != self.turn_seat:
                return {"error": "Not your turn"}
            
            p = self.players[seat]
            # 手牌または自摸牌からのみ打牌可能
            if tile == self.current_draw:
                self.current_draw = None
            elif tile in p.hand:
                p.hand.remove(tile)
            else:
                return {"error": f"Tile {tile} not in hand"}
            
            # スナップショット作成 (打牌前)
            state_snapshot = {
                "hand": list(p.hand) + ([self.current_draw] if self.current_draw else []),
                "river": list(p.river),
                "players": {s: {"score": pl.score, "river": list(pl.river)} for s, pl in self.players.items()},
                "turn": self.turn_seat,
                "dealer": self.dealer,
                "kyoku": self.kyoku,
                "honba": self.honba,
                "dora": list(self.dora_indicators)
            }
            
            p.river.append(tile)
            
            # 向聴数計算（デバッグ/解説用）
            shanten = rule_engine.get_shanten(p.hand)
            
            # AI推論トリガー
            ai_suggestion = None
            try:
                reg = get_registry()
                ai_state = {
                    "hand": p.hand,
                    "river": p.river,
                    "turn": self.turn_seat,
                    "draw": self.current_draw
                }
                req_data = InferenceRequest(state=ai_state, engine="ensemble")
                ai_result = await asyncio.wait_for(
                    suggest_move(req_data, reg=reg),
                    timeout=3.0
                )
                ai_suggestion = {
                    "move": ai_result.recommended_move,
                    "confidence": ai_result.confidence,
                    "metadata": ai_result.explanation.summary.one_liner # 簡易化
                }
            except Exception as e:
                print(f"[AI Error] {e}")

            # ログ記録
            if self.logger:
                self.logger.log_move(seat, tile, state_snapshot, ai_suggestion)

            self.turn_seat = (seat + 1) % 4
            self.current_draw = self.wall.pop()

            return {
                "status": "ok",
                "next_turn": self.turn_seat,
                "your_shanten": shanten,
                "current_draw": self.current_draw,
                "ai_suggestion": ai_suggestion
            }

game_state = GameState()

@router.websocket("/game/{room_id}")
async def game_ws(websocket: WebSocket, room_id: str):
    await websocket.accept()
    WS_CONNECTIONS.inc()
    
    # Kifu開始
    if game_state.logger:
        game_state.logger.start_game(room_id)
    
    # MVP: 座席0を人間プレイヤーとして登録
    seat = 0
    game_state.players[seat] = Player(websocket, seat, is_human=True)
    for i in range(1, 4):
        game_state.players[i] = Player(None, i, is_human=False)  # AI仮配置
    
    if len(game_state.players) == 4:
        game_state.init_wall()
        game_state.deal_initial()
        await websocket.send_json({
            "type": "game_start",
            "hand": game_state.players[seat].hand,
            "draw": game_state.current_draw,
            "turn": game_state.turn_seat
        })

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "discard":
                result = await game_state.process_human_discard(seat, data["tile"])
                await websocket.send_json({"type": "discard_result", **result})
                    
    except WebSocketDisconnect:
        WS_CONNECTIONS.dec()
        if seat in game_state.players:
            del game_state.players[seat]
        if game_state.logger:
            game_state.logger.save()
