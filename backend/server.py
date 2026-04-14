"""
FastAPI を使用した麻雀ゲームサーバー
WebSocket でリアルタイム通信
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import GameState, GameMessage, AIAnalysis
from backend.game_engine import MahjongEngine
from backend.ai_explainer import AIExplainer

app = FastAPI(title="麻雀解説 AI システム")

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ゲームエンジンのインスタンス
game_engine = MahjongEngine()
ai_explainer = AIExplainer()

# WebSocket 接続管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "麻雀解説 AI システム",
        "version": "0.1.0",
        "endpoints": {
            "websocket": "/ws",
            "game_init": "/game/init",
            "game_state": "/game/state"
        }
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket エンドポイント"""
    await manager.connect(websocket)

    # 初期ゲーム状態を送信
    try:
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "接続完了"}
        })
    except:
        manager.disconnect(websocket)
        return

    try:
        while True:
            # クライアントからのメッセージを待機
            data = await websocket.receive_text()
            message = json.loads(data)

            # メッセージタイプに応じて処理
            await handle_message(websocket, message)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Error: {e}")
        manager.disconnect(websocket)


async def handle_message(websocket: WebSocket, message: dict):
    """メッセージ処理"""
    msg_type = message.get("type")
    data = message.get("data", {})

    if msg_type == "init_game":
        # ゲーム初期化
        game_engine.init_game(
            round_name=data.get("round_name", "E1"),
            bakaze=data.get("bakaze", "east"),
            jikaze=data.get("jikaze", "east")
        )

        state = game_engine.get_state()
        if state:
            await websocket.send_json({
                "type": "game_state",
                "data": state.dict()
            })

            # AI 解析結果も送信
            analysis = ai_explainer.analyze(state)
            await websocket.send_json({
                "type": "ai_analysis",
                "data": analysis.dict()
            })

    elif msg_type == "draw_tile":
        # ツモ
        tile = game_engine.draw_tile()
        state = game_engine.get_state()

        if state:
            await websocket.send_json({
                "type": "game_state",
                "data": state.dict()
            })

            # AI 解析
            analysis = ai_explainer.analyze(state)
            await websocket.send_json({
                "type": "ai_analysis",
                "data": analysis.dict()
            })

    elif msg_type == "discard":
        # 打牌
        tile_index = data.get("tile_index", 0)
        success = game_engine.discard_tile(tile_index)

        if success:
            state = game_engine.get_state()
            if state:
                await websocket.send_json({
                    "type": "game_state",
                    "data": state.dict()
                })

    elif msg_type == "declare_riichi":
        # リーチ宣言
        success = game_engine.declare_riichi()

        if success:
            state = game_engine.get_state()
            if state:
                await websocket.send_json({
                    "type": "game_state",
                    "data": state.dict()
                })

                # AI 解析も更新
                analysis = ai_explainer.analyze(state)
                await websocket.send_json({
                    "type": "ai_analysis",
                    "data": analysis.dict()
                })
        else:
            # エラーメッセージ
            await websocket.send_json({
                "type": "error",
                "data": {"message": "リーチ宣言できません"}
            })

    elif msg_type == "get_analysis":
        # AI 解析リクエスト
        state = game_engine.get_state()
        if state:
            analysis = ai_explainer.analyze(state)
            await websocket.send_json({
                "type": "ai_analysis",
                "data": analysis.dict()
            })


@app.post("/game/init")
async def init_game(round_name: str = "E1", bakaze: str = "east",
                    jikaze: str = "east"):
    """HTTP でゲーム初期化"""
    from shared.models import Wind

    bakaze_enum = Wind(bakaze)
    jikaze_enum = Wind(jikaze)

    game_engine.init_game(round_name, bakaze_enum, jikaze_enum)
    state = game_engine.get_state()

    if state:
        analysis = ai_explainer.analyze(state)
        return {
            "game_state": state.dict(),
            "ai_analysis": analysis.dict()
        }

    return {"error": "初期化に失敗しました"}


@app.get("/game/state")
async def get_game_state():
    """現在のゲーム状態を取得"""
    state = game_engine.get_state()
    if state:
        analysis = ai_explainer.analyze(state)
        return {
            "game_state": state.dict(),
            "ai_analysis": analysis.dict()
        }
    return {"error": "ゲームが開始されていません"}


# フロントエンドの静的ファイルを提供
try:
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
except:
    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
