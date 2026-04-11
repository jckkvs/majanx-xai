# game.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import random
from typing import List, Dict, Optional
from core.rules.mahjong_engine import MahjongRuleEngine
from server.endpoints.inference import router as inference_router, suggest_move, InferenceRequest

app = FastAPI()
app.include_router(inference_router)

# プロジェクト構造に合わせて静的ファイルをマウント (Optional)
# app.mount("/static", StaticFiles(directory="static"), name="static")

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
        self.current_draw: Optional[str] = None
        self.is_active: bool = False
        self._lock = asyncio.Lock()

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
            
            p.river.append(tile)
            self.turn_seat = (seat + 1) % 4
            self.current_draw = self.wall.pop()
            
            # 向聴数計算（デバッグ/解説用）
            shanten = rule_engine.get_shanten(p.hand)
            
            # AI推論トリガー
            ai_suggestion = None
            try:
                from server.endpoints.inference import get_registry
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
                    "metadata": ai_result.metadata
                }
            except Exception as e:
                print(f"[AI Error] {e}")

            return {
                "status": "ok",
                "next_turn": self.turn_seat,
                "your_shanten": shanten,
                "current_draw": self.current_draw,
                "ai_suggestion": ai_suggestion
            }

game_state = GameState()

@app.websocket("/ws/game/{room_id}")
async def game_ws(websocket: WebSocket, room_id: str):
    await websocket.accept()
    
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
                
                if result.get("status") == "ok":
                    # Priority 2 でここにAI推論トリガーを挿入
                    pass
                    
    except WebSocketDisconnect:
        if seat in game_state.players:
            del game_state.players[seat]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("game:app", host="0.0.0.0", port=8000, reload=True)
