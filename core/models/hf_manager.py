# core/models/hf_manager.py
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict
from huggingface_hub import snapshot_download
from fastapi import HTTPException

class HFModelManager:
    def __init__(self, base_cache_dir: str = "./models_cache"):
        self.cache_dir = Path(base_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._download_locks: Dict[str, asyncio.Lock] = {}

    def get_engine_dir(self, engine_name: str) -> Path:
        return self.cache_dir / engine_name

    def is_model_ready(self, engine_name: str, expected_files: list[str]) -> bool:
        engine_dir = self.get_engine_dir(engine_name)
        if not engine_dir.exists(): return False
        return all((engine_dir / f).exists() for f in expected_files)

    async def download_model(
        self, 
        engine_name: str, 
        repo_id: str, 
        hf_token: str, 
        expected_files: list[str],
        progress_callback=None
    ) -> str:
        if self.is_model_ready(engine_name, expected_files):
            return str(self.get_engine_dir(engine_name))
        
        lock = self._download_locks.setdefault(engine_name, asyncio.Lock())
        async with lock:
            # 二重ダウンロード防止
            if self.is_model_ready(engine_name, expected_files):
                return str(self.get_engine_dir(engine_name))
            
            os.environ["HF_TOKEN"] = hf_token
            
            engine_dir = self.get_engine_dir(engine_name)
            engine_dir.mkdir(parents=True, exist_ok=True)
            
            # 非同期ダウンロード（huggingface_hubは同期APIのためスレッドプールで実行）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                snapshot_download, 
                repo_id, 
                None, 
                hf_token, 
                str(engine_dir), 
                None, 
                None, 
                None, 
                True
            )
            
            if not self.is_model_ready(engine_name, expected_files):
                raise HTTPException(400, f"ダウンロード完了但し必須ファイル不足: {expected_files}")
            
            return str(engine_dir)

    def get_model_status(self, engines: dict) -> list[dict]:
        status = []
        for name, cfg in engines.items():
            ready = self.is_model_ready(name, cfg["expected_files"])
            status.append({
                "name": name,
                "status": "ready" if ready else "not_installed",
                "repo_id": cfg["repo_id"],
                "path": str(self.get_engine_dir(name))
            })
        return status
