# core/inference/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class AIEngineAdapter(ABC):
    """全AIエンジンの統一インターフェース"""
    
    def __init__(self, model_dir: str, config: Dict[str, Any]):
        self.model_dir = model_dir
        self.config = config
        self._model = None
    
    @abstractmethod
    def load_model(self) -> None:
        """重みロード・初期化"""
        pass
    
    @abstractmethod
    def infer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        局面入力 → 推論
        戻り値形式: {"move": "5p", "score": 0.85, "metadata": {"shanten": 1, "safety": 0.72}}
        """
        pass
    
    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Adapter", "").lower()
