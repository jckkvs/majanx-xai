from typing import Dict, Any, Optional
from .base import AIEngineAdapter
from .adapters.kanachan_adapter import KanachanAdapter
from .adapters.rlcard_adapter import RLCardAdapter

class EngineRegistry:
    def __init__(self, hf_manager):
        self.hf_manager = hf_manager
        self.engines: Dict[str, AIEngineAdapter] = {}
        self.loaded_engines: Dict[str, bool] = {}
        
        # エンジン設定定義
        self.engine_configs = {
            "kanachan": {"repo_id": "user/kanachan-mahjong", "expected_files": ["model.onnx", "config.yaml"]},
            "phoenix": {"repo_id": "user/phoenix-suphx", "expected_files": ["checkpoint.pt"]},
            "rlcard": {"repo_id": "user/rlcard-mahjong", "expected_files": ["ppo_agent.zip"]}
        }

    def register(self, engine_name: str, adapter_class: type[AIEngineAdapter], model_dir: str) -> None:
        self.engines[engine_name] = adapter_class(model_dir, self.engine_configs[engine_name])

    def ensure_loaded(self, engine_name: str) -> None:
        if engine_name not in self.engines:
            raise ValueError(f"Unknown engine: {engine_name}")
        if not self.loaded_engines.get(engine_name):
            self.engines[engine_name].load_model()
            self.loaded_engines[engine_name] = True

    async def download_and_register(self, engine_name: str, hf_token: str, adapter_class: type[AIEngineAdapter]) -> str:
        cfg = self.engine_configs[engine_name]
        model_dir = await self.hf_manager.download_model(
            engine_name, cfg["repo_id"], hf_token, cfg["expected_files"]
        )
        self.register(engine_name, adapter_class, model_dir)
        return model_dir

    def get_adapter(self, engine_name: str) -> AIEngineAdapter:
        self.ensure_loaded(engine_name)
        return self.engines[engine_name]
