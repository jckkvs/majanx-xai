# server/endpoints/review.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List
import json
from pathlib import Path

router = APIRouter(prefix="/api/v1/review", tags=["実戦振り返り"])

# 依存性注入（main.pyで初期化）
analyzer = None
registry = None
explainer = None

def get_analyzer():
    global analyzer, registry, explainer
    if not analyzer:
        from core.review.analyzer import ReviewAnalyzer
        from core.explanation.generator import ExplanationGenerator
        from core.inference.registry import EngineRegistry
        from core.models.hf_manager import HFModelManager
        
        # 既存のレジストリや説明生成器がある場合はそちらを利用（main.pyでセット）
        if not registry:
            registry = EngineRegistry(HFModelManager())
        if not explainer:
            explainer = ExplanationGenerator()
            
        analyzer = ReviewAnalyzer(registry, explainer)
    return analyzer

@router.post("/analyze/{game_id}")
async def trigger_analysis(game_id: str, force: bool = False, reg = Depends(get_analyzer)):
    try:
        result = await reg.analyze_kifu(game_id, force=force)
        return {"status": "completed", "game_id": game_id, "summary": result["summary"]}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")

@router.get("/{game_id}")
async def get_review(game_id: str, reg = Depends(get_analyzer)):
    cache = reg.get_cache_path(game_id)
    if not cache.exists():
        # キャッシュがなければその場で分析を試行
        try:
            return await reg.analyze_kifu(game_id)
        except Exception:
            raise HTTPException(404, "未分析です。先に /analyze を実行してください。")
    return json.loads(cache.read_text(encoding="utf-8"))

@router.get("/list")
async def list_kifu():
    kifu_dir = Path("./kifu_data")
    if not kifu_dir.exists(): return []
    # 最新順にソート
    files = sorted(kifu_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    return [{"id": f.stem, "date": f.stem.split("_")[1] if "_" in f.stem else "unknown", "size_kb": round(f.stat().st_size/1024, 1)} for f in files[:50]]
