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

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

game = GameLoop()

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
                # ゲーム開始（最初の1人が入ったときのみ）
                if game.state == game.STATE.INIT:
                    snapshot = game.start()
                else:
                    snapshot = game._get_state_snapshot()
                await ws_manager.send_personal_message(snapshot, player_id)
                
            elif msg_type == "action_request":
                action = data.get("action")
                if action == "discard":
                    tile = data.get("tile")
                    # プレイヤー0（人間）が打牌したと仮定
                    snapshot = game.process_discard(0, tile)
                    await ws_manager.broadcast(snapshot)
                    
                    # 簡易的にCPU(1,2,3)も自動で打牌してターンを回す
                    while game.state != game.STATE.ROUND_END and game.turn_idx != 0:
                        await asyncio.sleep(0.5)
                        cpu_idx = game.turn_idx
                        # CPUの最初の手牌を適当に切る
                        if game.players[cpu_idx].hand:
                            cpu_tile = game.players[cpu_idx].hand[0]
                            snapshot = game.process_discard(cpu_idx, cpu_tile)
                            await ws_manager.broadcast(snapshot)
                            
    except WebSocketDisconnect:
        ws_manager.disconnect(player_id)
    except Exception as e:
        print(f"WS error: {e}")
        ws_manager.disconnect(player_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
