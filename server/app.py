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
    from server.ai_adapters.mortal_adapter import MortalAdapter
    from server.ai_adapters.rulebase_adapter import RulebaseAdapter
    from server.ai_adapters.base import MJAIAction
    from server.recommendation_aggregator import RecommendationAggregator
    mortal = MortalAdapter()
    phoenix = RulebaseAdapter()
    aggregator = RecommendationAggregator()
    AI_AVAILABLE = True
except Exception as e:
    print(f"AI adapters not available: {e}")
    mortal = None
    phoenix = None
    aggregator = None
    AI_AVAILABLE = False

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

game = GameLoop()

async def request_ai_suggestion():
    if not AI_AVAILABLE:
        return None
    # 人間の打牌待ち時、AI2つの推奨を取得して統合する
    if game.state != game.STATE.DISCARDING or game.turn_idx != 0:
        return None
        
    legal_actions = []
    # 実際には適正な合法手リストが必要だがモック化
    for tile in game.players[0].hand:
        legal_actions.append(MJAIAction("dahai", pai=tile))
        
    rec_speed = await mortal.request_action(legal_actions)
    rec_phoenix = await phoenix.request_action(legal_actions)
    
    if rec_speed and rec_phoenix:
        return aggregator.aggregate([rec_speed, rec_phoenix], [a.params["pai"] for a in legal_actions])
    return None

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
                snapshot = game.start()
                
                # 自分(盤面)のターンならAI予測も付与して送信
                if game.state == game.STATE.DISCARDING and game.turn_idx == 0:
                    ai_res = await request_ai_suggestion()
                    if ai_res:
                        snapshot["perspective_parallel"] = ai_res["perspective_parallel"]
                
                await ws_manager.send_personal_message(snapshot, player_id)
                
            elif msg_type == "action_request":
                action = data.get("action")
                if action == "discard":
                    tile = data.get("tile")
                    snapshot = game.process_discard(0, tile)
                    await ws_manager.broadcast(snapshot)
                    
                    # 簡易的にCPU(1,2,3)も自動で打牌してターンを回す
                    while game.state != game.STATE.ROUND_END and game.turn_idx != 0:
                        await asyncio.sleep(0.5)
                        cpu_idx = game.turn_idx
                        if game.players[cpu_idx].hand:
                            cpu_tile = game.players[cpu_idx].hand[0]
                            snapshot = game.process_discard(cpu_idx, cpu_tile)
                            await ws_manager.broadcast(snapshot)
                            
                    # 人間の手番に戻ったならAI推論を生成してブロードキャスト
                    if game.state == game.STATE.DISCARDING and game.turn_idx == 0:
                        snapshot = game._get_state_snapshot()
                        ai_res = await request_ai_suggestion()
                        if ai_res:
                            snapshot["perspective_parallel"] = ai_res["perspective_parallel"]
                        await ws_manager.broadcast(snapshot)
                            
    except WebSocketDisconnect:
        ws_manager.disconnect(player_id)
    except Exception as e:
        print(f"WS error: {e}")
        ws_manager.disconnect(player_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
