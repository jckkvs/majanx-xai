# server/endpoints/stats.py
from fastapi import APIRouter
from core.kifu.analyzer import KifuAnalyzer

router = APIRouter(prefix="/api/v1/stats", tags=["統計ダッシュボード"])
analyzer = KifuAnalyzer()

@router.get("/summary")
async def get_stats():
    return analyzer.get_stats()
