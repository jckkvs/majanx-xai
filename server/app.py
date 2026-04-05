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
from .models import GamePhase
from .replay_manager import ReplayManager
from .tenhou_to_mjai import TenhouToMjaiConverter
from .mortal.mortal_agent import MortalAgent
from .settings_manager import SettingsManager
from .voice_commentator import VoiceCommentator
from .precompute_engine import PrecomputeEngine
from .commentator import CommentatorAI

# グローバル初期化
settings_mgr = SettingsManager()
voice_mgr = VoiceCommentator(**settings_mgr.get_voice_config())
# Mortal Agent 初期化（設定ファイルから）
try:
    mortal_agent_global = MortalAgent(**settings_mgr.get_ai_config())
except Exception as e:
    print(f"MortalAgent initialization error: {e}")
    mortal_agent_global = None

rule_ai_global = CommentatorAI(engine=None)
precompute_global = PrecomputeEngine(mortal_agent=mortal_agent_global, rule_engine=rule_ai_global)

app = FastAPI(title="麻雀AI - Mahjong AI")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_active_connections = set()

def get_active_connections():
    return _active_connections.copy()

@app.on_event("startup")
async def startup():
    """アプリ起動時の初期化"""
    voice_mgr.start()
    print("[App] ✅ 起動完了")

@app.on_event("shutdown")
async def shutdown():
    """アプリ終了時のクリーンアップ"""
    voice_mgr.stop()

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

    gm = getattr(app.state, "game_manager", None)
    needs_new_game = (
        gm is None or
        gm.engine.state.phase == GamePhase.GAME_END
    )

    if needs_new_game:
        app.state.game_manager = GameManager(human_seat=0)
        app.state.game_manager.set_client_handler(broadcast_event)
        asyncio.create_task(app.state.game_manager.start_game())
    else:
        # 進行中の状態同期
        try:
            await ws.send_json({
                "type": "state_sync",
                "data": app.state.game_manager.engine.to_state_dict(for_player=None)
            })
        except Exception:
            pass

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")
            if action == "next_round":
                asyncio.create_task(app.state.game_manager.next_round())
            elif action == "new_game":
                app.state.game_manager = GameManager(human_seat=0)
                app.state.game_manager.set_client_handler(broadcast_event)
                asyncio.create_task(app.state.game_manager.start_game())
            elif app.state.game_manager.human_seat != -1:
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

# === Settings API ===

@app.get("/api/settings")
async def get_settings():
    return settings_mgr.get()

@app.post("/api/settings")
async def update_settings(new_settings: dict):
    settings_mgr.update(**new_settings)
    if any(k in new_settings for k in ["voice_enabled", "voice_engine", "voice_rate", "voice_volume"]):
        voice_mgr.update_settings(**settings_mgr.get_voice_config())
    return {"status": "ok"}

@app.post("/api/settings/reset")
async def reset_settings():
    global settings_mgr
    settings_mgr = SettingsManager()
    return settings_mgr.get()

# === Fast Match WebSocket (Phase 3) ===

class MockEngine:
    def __init__(self):
        self.wall = ["1m"] * 70
        self.hands = {
            0: ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "1z", "1z", "2z", "2z"],
            1: ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "1z", "1z", "2z", "2z"],
            2: ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "1z", "1z", "2z", "2z"],
            3: ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "1z", "1z", "2z", "2z"]
        }
        self.dora_indicators = ["1z"]
        self.scores = {0: 25000, 1: 25000, 2: 25000, 3: 25000}
        self.round_info = {"wind": "東", "round": 1}
        self.rivers = {0: [], 1: [], 2: [], 3: []}

    def do_dahai(self, seat: int, tile: str):
        if tile in self.hands[seat]:
            self.hands[seat].remove(tile)
        self.rivers[seat].append(tile)

    def _tile_to_idx(self, tile: str) -> int:
        return 0

engine = MockEngine()
precompute = {
    0: {
        "recommendation": "1z",
        "reasoning": {
            "reasoning": "字牌から切り出します",
            "attack_score": 20.0,
            "defense_score": 80.0,
            "balance": "defensive"
        }
    }
}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    
    # 初期状態
    await ws.send_json({
        "type": "init",
        "hand": engine.hands[0],
        "dora": engine.dora_indicators,
        "scores": engine.scores,
        "round": f"{engine.round_info['wind']}{engine.round_info['round']}局",
        "tile_count": len(engine.wall)
    })
    
    try:
        while True:
            msg = await ws.receive_json()
            
            if msg.get("type") == "action" and msg.get("action") == "dahai":
                tile = msg["tile"]
                seat = 0  # player
                engine.do_dahai(seat, tile)
                
                # 自分打牌
                await ws.send_json({
                    "type": "update",
                    "hand": engine.hands[0],
                    "new_discard": tile,
                    "discard_seat": seat,  # 0=自分
                    "tile_count": len(engine.wall)
                })
                
                # CPU打牌シミュレーション（簡易）
                for cpu_seat in [1, 2, 3]:
                    if engine.wall and len(engine.hands[cpu_seat]) > 0:
                        cpu_tile = engine.hands[cpu_seat].pop(0)
                        engine.rivers[cpu_seat].append(cpu_tile)
                        
                        # CPU打牌通知
                        await ws.send_json({
                            "type": "update",
                            "new_discard": cpu_tile,
                            "discard_seat": cpu_seat,  # 1=南, 2=西, 3=北
                            "scores": engine.scores,
                            "tile_count": len(engine.wall)
                        })
                        await asyncio.sleep(0.3)
                
                # AI推奨
                tsumo_idx = engine._tile_to_idx(tile.rstrip('r'))
                cached = precompute.get(tsumo_idx)
                if cached:
                    await ws.send_json({
                        "type": "ai_recommendation",
                        "recommendation": cached["recommendation"],
                        "reasoning": cached["reasoning"]["reasoning"],
                        "attack_score": cached["reasoning"]["attack_score"],
                        "defense_score": cached["reasoning"]["defense_score"],
                        "balance": cached["reasoning"]["balance"],
                        "is_precomputed": True
                    })
                    
    except Exception as e:
        print(f"[WS] error: {e}")

@app.get("/api/health")
async def health():
    return {"status": "ok", "game": "mahjong-ai"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
