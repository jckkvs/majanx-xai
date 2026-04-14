# server/endpoints/inference.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict
import time
from core.explanation.models import CompleteExplanation
from core.explanation.generator import ExplanationGenerator

router = APIRouter(prefix="/api/v1/inference", tags=["AI推論"])

explainer = ExplanationGenerator()  # 初回初期化

# --- モデル定義 ---
class InferenceRequest(BaseModel):
    state: dict = Field(..., description="局面状態 JSON")
    engine: Literal["kanachan", "phoenix", "rlcard", "ensemble"] = "ensemble"
    hf_token: Optional[str] = Field(None, description="初回ダウンロード用HFトークン")

class EngineDetail(BaseModel):
    engine: str
    move: str
    confidence: float

class InferenceResponse(BaseModel):
    recommended_move: str
    explanation: CompleteExplanation  # ← 新規追加（旧 metadata を置換）
    engine_used: str
    latency_ms: float
    ensemble_details: Optional[List[EngineDetail]] = None

class DownloadRequest(BaseModel):
    engine: Literal["kanachan", "phoenix", "rlcard"]
    hf_token: str = Field(..., min_length=1)

# --- 依存性注入（ゲーム起動時に初期化） ---
# 注意: 実際の実装では DI コンテナやグローバルな初期化が必要
registry = None 

def get_registry():
    global registry
    if registry is None:
        # Fallback for testing/standalone
        from core.models.hf_manager import HFModelManager
        from core.inference.registry import EngineRegistry
        hfm = HFModelManager()
        registry = EngineRegistry(hfm)
    return registry

# --- エンドポイント ---
@router.post("/suggest", response_model=InferenceResponse)
async def suggest_move(req: InferenceRequest, reg = Depends(get_registry)):
    start = time.time()
    
    # 実際は各エンジンのアダプターを呼び出す
    # ここでは仕様に基づき構造のみ実装
    
    # --- AI推論（現在はMock実行） ---
    if req.engine == "ensemble":
        results = {}
        for eng in ["kanachan", "phoenix", "rlcard"]:
            results[eng] = {"move": "5p", "score": 0.8} 
        best_eng = "kanachan"
        final_move = results[best_eng]["move"]
        ensemble_details = [EngineDetail(engine=k, move=v["move"], confidence=v["score"]) for k, v in results.items()]
    else:
        final_move = "5p"
        ensemble_details = None

    # 説明生成用ダミー状態（実運用時は game_state から正確な前後の手牌・文脈を渡す）
    explanation_state = {
        "hand_before": req.state.get("hand", []),
        "hand_after": [t for t in req.state.get("hand", []) if t != final_move],
        "context": req.state.get("context", {"round": "東1", "score_diff": 0, "is_dealer": True, "turn_count": 5})
    }
    ai_meta = {
        "confidence": 0.8 if req.engine == "ensemble" else 0.9,
        "alternatives": []  # エンジン側が返す場合はここに入れる
    }
    
    # ★ 説明生成実行
    full_explanation = explainer.generate(final_move, explanation_state, ai_meta)
    
    latency = (time.time() - start) * 1000
    
    return InferenceResponse(
        recommended_move=final_move,
        explanation=full_explanation,  # ← 統合
        engine_used=req.engine,
        latency_ms=latency,
        ensemble_details=ensemble_details
    )

@router.post("/models/download")
async def download_model(req: DownloadRequest, reg = Depends(get_registry)):
    try:
        # ここではアダプターのロードを想定したプレースホルダー
        # path = await reg.download_and_register(req.engine, req.hf_token, SomeAdapter)
        return {"status": "completed", "path": f"./models_cache/{req.engine}"}
    except Exception as e:
        raise HTTPException(400, str(e))

@router.get("/models/status")
async def model_status(reg = Depends(get_registry)):
    return reg.hf_manager.get_model_status(reg.engine_configs)
