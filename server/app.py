"""
FastAPI WebSocket サーバー
Implements: F-005 | WebSocket対局サーバー

静的ファイル(HTML/CSS/JS)の配信 + WebSocket対局通信を提供。
"""
from __future__ import annotations

import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .game_manager import GameManager

app = FastAPI(title="麻雀AI - Mahjong AI")

# 静的ファイルのパス
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


# ============================================================
# 静的ファイル配信
# ============================================================

@app.get("/")
async def index():
    """メインページ"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# 静的ファイルマウント（CSS, JS, 画像）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============================================================
# WebSocket対局
# ============================================================

# アクティブなゲームセッション
active_games: dict[str, GameManager] = {}


@app.websocket("/ws/game")
async def websocket_game(websocket: WebSocket):
    """対局用WebSocketエンドポイント"""
    await websocket.accept()

    # ゲームマネージャー作成
    manager = GameManager(human_seat=0)

    async def send_to_client(msg: dict):
        """クライアントにJSON送信"""
        try:
            await websocket.send_json(msg)
        except Exception:
            pass

    manager.set_client_handler(send_to_client)

    # ゲームループを非同期タスクとして開始
    game_task = asyncio.create_task(manager.start_game())

    try:
        while True:
            # クライアントからのメッセージ受信
            data = await websocket.receive_json()
            action = data.get("action", "")

            if action == "next_round":
                # 次局開始
                asyncio.create_task(manager.next_round())
            else:
                # 人間の入力として処理
                manager.receive_human_input(data)

    except WebSocketDisconnect:
        game_task.cancel()
    except Exception as e:
        print(f"WebSocket error: {e}")
        game_task.cancel()


# ============================================================
# ヘルスチェック
# ============================================================

@app.get("/api/health")
async def health():
    return {"status": "ok", "game": "mahjong-ai"}


# ============================================================
# サーバー起動
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
