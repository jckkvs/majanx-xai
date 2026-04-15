# server/endpoints/settings.py
from fastapi import APIRouter
from pydantic import BaseModel
import server.config as cfg

router = APIRouter(prefix="/api/settings", tags=["設定"])

class SettingsUpdate(BaseModel):
    cpu_strength: float | None = None

@router.get("")
async def get_settings():
    return {"cpu_strength": cfg.CPU_STRENGTH}

@router.post("")
async def update_settings(body: SettingsUpdate):
    if body.cpu_strength is not None:
        cfg.CPU_STRENGTH = max(0.0, min(1.0, body.cpu_strength))
    return {"cpu_strength": cfg.CPU_STRENGTH}
