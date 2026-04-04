"""
FastAPI WebSocket サーバー
Implements: F-005 | WebSocket対局サーバー

静的ファイル(HTML/CSS/JS)の配信 + WebSocket対局通信を提供。
ユーザーの実働骨格をベースに、既存エンジンとフル統合。
"""
from __future__ import annotations

import asyncio
import os
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uuid

from .game_manager import GameManager
from .replay_manager import ReplayManager
from .tenhou_to_mjai import TenhouToMjaiConverter
from .mortal.mortal_agent import MortalAgent

app = FastAPI(title="麻雀AI - Mahjong AI")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_active_connections = set()

def get_active_connections():
    return _active_connections.copy()

async def broadcast_event(event: Dict[str, Any]):
    """全接続クライアントにイベント送信"""
    for conn in get_active_connections():
        try:
            await conn.send_json(event)
        except Exception:
            pass

@app.websocket("/ws_ui")
async def ui_ws(ws: WebSocket):
    """UI用WebSocketエンドポイント"""
    await ws.accept()
    _active_connections.add(ws)
    
    # クライアント接続時に初回のみゲーム開始
    # 本番では別のトリガーでGameManagerをキックするが、Phase1では接続時に起動
    if not hasattr(app.state, "game_manager"):
        app.state.game_manager = GameManager(human_seat=-1) # -1でフルオート
        app.state.game_manager.set_client_handler(broadcast_event)
        
        # プレイヤーをMortalAgentに差し替え（1人だけMortal、他はランダムCPUにするなど可能）
        # 今回は全員MortalAgentにする
        for seat in range(4):
            app.state.game_manager.cpus[seat] = MortalAgent(seat, app.state.game_manager.engine)
            
        asyncio.create_task(app.state.game_manager.start_game())
    else:
        # 進行中の状態同期
        await ws.send_json({
            "type": "state_sync",
            "data": app.state.game_manager.engine.to_state_dict(for_player=None)
        })

    try:
        while True:
            data = await ws.receive_json()
            # UIからのインタラクション処理
            if app.state.game_manager.human_seat != -1:
                app.state.game_manager.receive_human_input(data)
    except WebSocketDisconnect:
        _active_connections.discard(ws)
    except Exception as e:
        print(f"[Server] WebSocket error: {e}")
        _active_connections.discard(ws)

# === Replay API ===

replay_sessions = {}

@app.post("/api/replay/upload")
async def upload_replay(file: UploadFile = File(...)):
    """牌譜ファイルをアップロードし、セッションIDを返す"""
    content = await file.read()
    session_id = str(uuid.uuid4())
    
    rm = ReplayManager()
    
    if file.filename.endswith(".log"):
        converter = TenhouToMjaiConverter()
        events = converter.convert_log(content.decode("utf-8", errors="ignore"))
    else:
        events = __import__("json").loads(content.decode("utf-8"))
        
    rm.load_log(events)
    replay_sessions[session_id] = rm
    return {"session_id": session_id, "turns": len(events)}

@app.websocket("/ws/replay/{session_id}")
async def replay_ws(ws: WebSocket, session_id: str):
    """リプレイ制御用WebSocketエンドポイント"""
    await ws.accept()
    if session_id not in replay_sessions:
        await ws.close()
        return

    rm: ReplayManager = replay_sessions[session_id]
    
    # 初期状態送信
    await ws.send_json({
        "type": "state_sync",
        "data": rm.to_client_dict(),
        "ai_analysis": rm.last_analysis
    })
    
    try:
        while True:
            data = await ws.receive_json()
            act = data.get("action")
            
            if act == "next":
                has_next = rm.step_forward()
                await ws.send_json({
                    "type": "state_sync",
                    "data": rm.to_client_dict(),
                    "ai_analysis": rm.last_analysis,
                    "has_next": has_next
                })
            elif act == "prev":
                has_prev = rm.step_backward()
                await ws.send_json({
                    "type": "state_sync",
                    "data": rm.to_client_dict(),
                    "ai_analysis": rm.last_analysis,
                    "has_next": True
                })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[Replay] WS Error: {e}")

@app.get("/api/health")
async def health():
    return {"status": "ok", "game": "mahjong-ai"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
