# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import threading
import http.server
import socketserver
import os
import sys

# WindowsでのUnicode/絵文字表示対策
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from server.middleware.security import setup_security
from server.endpoints.inference import router as inference_router
from server.endpoints.stats import router as stats_router
from server.endpoints.review import router as review_router
from server.endpoints.game import router as game_router, game_state
from core.kifu.logger import KifuLogger
from core.inference.registry import EngineRegistry
from core.models.hf_manager import HFModelManager
from core.monitoring.metrics import MetricsMiddleware

# ロガー初期化
kifu_logger = KifuLogger("./kifu_data")
game_state.logger = kifu_logger # game_router のグローバルステートに注入

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 MajanX-XAI 起動中...")
    yield
    print("🔌 シャットダウン完了")

app = FastAPI(title="MajanX-XAI", lifespan=lifespan)

# ミドルウェア適用
setup_security(app)
app.add_middleware(MetricsMiddleware)

# ルーターマウント
app.include_router(inference_router)
app.include_router(stats_router)
app.include_router(review_router)
app.include_router(game_router)

# 依存性注入
import server.endpoints.review as review_module
from core.explanation.generator import ExplanationGenerator
review_module.registry = EngineRegistry(HFModelManager())
review_module.explainer = ExplanationGenerator()

def run_http_server(port, directory):
    """指定されたディレクトリをサーブする簡易 HTTP サーバー"""
    if not os.path.exists(directory):
        return

    original_dir = os.getcwd()
    try:
        os.chdir(directory)
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"✅ Serving {directory} at http://localhost:{port}")
            httpd.serve_forever()
    except Exception as e:
        print(f"❌ Error serving {directory}: {e}")
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    print("🚀 MajanX-XAI Multi-Server Starting...")
    print("--------------------------------------------------")
    print("📡 API Server:      http://localhost:8001")
    print("📄 API Docs:        http://localhost:8001/docs")

    threads = []

    # Frontend V2 (ポート 8081) - static_v2 を使用
    if Path("static_v2").exists():
        t_v2 = threading.Thread(target=run_http_server, args=(8081, "static_v2"), daemon=True)
        t_v2.start()
        threads.append(t_v2)
        print("🎮 Frontend V2:    http://localhost:8081")
    else:
        print("⚠️ static_v2 directory not found.")

    # Frontend Old (ポート 8080)
    if Path("frontend").exists():
        t_old = threading.Thread(target=run_http_server, args=(8080, "frontend"), daemon=True)
        t_old.start()
        threads.append(t_old)
        print("🎮 Frontend Old:   http://localhost:8080")
    else:
        print("⚠️ frontend directory not found.")

    print("--------------------------------------------------")

    try:
        # API サーバーを起動
        uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down all servers...")
