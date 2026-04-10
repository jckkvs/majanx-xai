"""
server/app.py
"""
import uuid
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from server.ws_handler import ws_manager
from server.game_loop import GameLoop

# AI adapters are optional - game works without them
try:
    from server.triple_recommendation_engine import FivePatternRecommendationEngine
    recommendation_engine = FivePatternRecommendationEngine()
    AI_AVAILABLE = True
except Exception as e:
    print(f"AI adapters not available: {e}")
    recommendation_engine = None
    AI_AVAILABLE = False

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

game = GameLoop()

async def request_ai_suggestion(current_game):
    if not AI_AVAILABLE:
        return None
    # 人間の打牌待ち時、5パターンの推奨を取得して統合する
    if current_game.state != current_game.STATE.DISCARDING or current_game.turn_idx != 0:
        return None
        
    game_state_dict = current_game._get_state_snapshot()
    hand_tiles = current_game.players[0].hand
    
    result = await recommendation_engine.generate_recommendations(game_state_dict, hand_tiles)
    return result

@app.get("/")
async def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws_ui")
async def websocket_ui_endpoint(ws: WebSocket):
    player_id = f"p_{uuid.uuid4().hex[:8]}"
    await ws_manager.connect(ws, player_id)
    
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "join":
                global game
                game = GameLoop()
                game._session_id = str(uuid.uuid4())
                current_session_id = game._session_id
                snapshot = game.start()
                
                # 自分(盤面)のターンならAI予測を別途送信
                await ws_manager.send_personal_message(snapshot, player_id)
                if game.state == game.STATE.DISCARDING and game.turn_idx == 0:
                    ai_res = await request_ai_suggestion(game)
                    if ai_res:
                        await ws_manager.send_personal_message(ai_res, player_id)
                
            elif msg_type == "action_request":
                action = data.get("action")
                if action == "discard":
                    tile = data.get("tile")
                    snapshot = game.process_discard(0, tile)
                    await ws_manager.broadcast(snapshot)
                    
                    # 簡易的にCPU(1,2,3)も自動で打牌してターンを回す
                    from server.config import CPU_STRENGTH
                    from server.cpu_decision import select_cpu_action
                    while game.state != game.STATE.ROUND_END and game.turn_idx != 0:
                        await asyncio.sleep(0.5)
                        if getattr(game, "_session_id", None) != current_session_id:
                            break
                        cpu_idx = game.turn_idx
                        if game.players[cpu_idx].hand:
                            valid_moves = game.players[cpu_idx].hand
                            
                            # AI確率分布を実際は得たいが、現行MVPでは対応していないため None を渡す
                            # (None の場合 select_cpu_action 内でランダムに選ばれる)
                            cpu_tile = select_cpu_action(None, valid_moves, strength=CPU_STRENGTH)
                            
                            snapshot = game.process_discard(cpu_idx, cpu_tile)
                            await ws_manager.broadcast(snapshot)
                            
                            if snapshot.get("phase") == "ryukyoku":
                                await asyncio.sleep(1.5)
                            
                    if getattr(game, "_session_id", None) != current_session_id:
                        continue
                            
                    # 人間の手番に戻ったならAI推論を生成してブロードキャスト
                    if game.state == game.STATE.DISCARDING and game.turn_idx == 0:
                        snapshot = game._get_state_snapshot()
                        await ws_manager.broadcast(snapshot)
                        ai_res = await request_ai_suggestion(game)
                        if ai_res:
                            await ws_manager.broadcast(ai_res)
    except WebSocketDisconnect:
        ws_manager.disconnect(player_id)
    except Exception as e:
        print(f"WS error: {e}")
        ws_manager.disconnect(player_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
