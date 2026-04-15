# server/endpoints/v2_game.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import uuid
import asyncio
from server.ws_handler import ws_manager
from server.game_loop import GameLoop

# AI adapters are optional
try:
    from server.triple_recommendation_engine import FivePatternRecommendationEngine
    recommendation_engine = FivePatternRecommendationEngine()
    AI_AVAILABLE = True
except Exception as e:
    print(f"AI adapters not available: {e}")
    recommendation_engine = None
    AI_AVAILABLE = False

router = APIRouter(tags=["V2ゲームWebSocket"])

game = GameLoop()

async def request_ai_suggestion(current_game):
    if not AI_AVAILABLE:
        return None
    if current_game.state != current_game.STATE.DISCARDING or current_game.turn_idx != 0:
        return None
        
    game_state_dict = current_game._get_state_snapshot()
    hand_tiles = current_game.players[0].hand
    
    result = await recommendation_engine.generate_recommendations(game_state_dict, hand_tiles)
    return result

@router.websocket("/ws_ui")
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
                    
                    from server.config import CPU_STRENGTH
                    from server.cpu_decision import select_cpu_action
                    while game.state != game.STATE.ROUND_END and game.turn_idx != 0:
                        await asyncio.sleep(0.5)
                        if getattr(game, "_session_id", None) != current_session_id:
                            break
                        cpu_idx = game.turn_idx
                        if game.players[cpu_idx].hand:
                            valid_moves = game.players[cpu_idx].hand
                            cpu_tile = select_cpu_action(None, valid_moves, strength=CPU_STRENGTH)
                            
                            snapshot = game.process_discard(cpu_idx, cpu_tile)
                            await ws_manager.broadcast(snapshot)
                            
                            if snapshot.get("phase") == "ryukyoku":
                                await asyncio.sleep(1.5)
                            
                    if getattr(game, "_session_id", None) != current_session_id:
                        continue
                            
                    if game.state == game.STATE.DISCARDING and game.turn_idx == 0:
                        snapshot = game._get_state_snapshot()
                        await ws_manager.broadcast(snapshot)
                        ai_res = await request_ai_suggestion(game)
                        if ai_res:
                            await ws_manager.broadcast(ai_res)

                elif action == "kan":
                    tile = data.get("tile")
                    snapshot = game.process_ankan(0, tile)
                    await ws_manager.broadcast(snapshot)
                    if game.state == game.STATE.DISCARDING and game.turn_idx == 0:
                        ai_res = await request_ai_suggestion(game)
                        if ai_res:
                            await ws_manager.broadcast(ai_res)
    except WebSocketDisconnect:
        ws_manager.disconnect(player_id)
    except Exception as e:
        print(f"WS error: {e}")
        ws_manager.disconnect(player_id)
