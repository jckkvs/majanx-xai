# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

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
    # 必要に応じてモデルの事前確認など
    yield
    print("🔌 シャットダウン処理完了")

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

# 静的ファイル (Vue/React ビルド成果物)
# Docker環境やビルド済み環境では /app/static または /app/frontend/dist を参照
static_dir = Path("frontend/dist")
if not static_dir.exists():
    static_dir = Path("static")

if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")
else:
    print(f"⚠️ 警告: 静的ファイルディレクトリ {static_dir} が見つかりません。")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
