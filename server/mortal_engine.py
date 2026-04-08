"""
server/mortal_engine.py
Mortal 推論実行エンジン
"""
from __future__ import annotations
import torch
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AIRecommendation:
    tile: str
    action_type: str
    probability: float
    q_value: float
    rank: int

class MortalEngine:
    # Mortal 標準アクション空間 (46次元)
    ACTION_MAP = [
        *[f"{i}{s}" for s in ("m", "p", "s") for i in range(1, 10)],
        *[f"{i}z" for i in range(1, 8)],
        "tsumogiri", "chi", "pon", "ankan", "kakan", "daiminkan", "hora", "riichi", "none"
    ]

    def __init__(self, model_path: str = "server/models/mortal_jit.pt"):
        self.device = self._resolve_device()
        self.model = self._load_model(model_path)
        self.model.eval()
        logger.info(f"MortalEngine initialized on {self.device}")

    def _resolve_device(self) -> torch.device:
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def _load_model(self, path: str) -> torch.nn.Module:
        p = Path(path)
        if not p.exists():
            print(f"Mortal weight not found: {p.absolute()}")
            return self._build_mock_model()
        # TorchScript形式を想定
        try:
            model = torch.jit.load(p, map_location=self.device)
            return model
        except Exception as e:
            print(f"Model load failed: {e}")
            return self._build_mock_model()

    def _build_mock_model(self) -> torch.nn.Module:
        """Fallback for testing without real weights"""
        class MockModel(torch.nn.Module):
            def forward(self, x):
                logits = torch.randn(1, 46)
                q_vals = torch.randn(1, 46)
                return logits, q_vals, None
        return MockModel().to(self.device)

    def predict(self, features: np.ndarray, top_k: int = 3) -> List[AIRecommendation]:
        """
        特徴量からTop-K推奨手を返す
        features: shape (1, 196)
        """
        if features.shape != (1, 196):
            raise ValueError(f"Expected shape (1, 196), got {features.shape}")

        tensor_feat = torch.tensor(features, dtype=torch.float32).to(self.device)

        with torch.no_grad():
            outputs = self.model(tensor_feat)
            if isinstance(outputs, tuple) and len(outputs) >= 2:
                logits, q_values = outputs[0], outputs[1]
            else:
                logits = outputs
                q_values = torch.zeros_like(logits)
                
            probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()
            q_vals = q_values.squeeze(0).cpu().numpy()

        if probs.ndim > 1:
            probs = probs.flatten()
            q_vals = q_vals.flatten()

        top_indices = np.argsort(probs)[::-1][:top_k]
        results = []

        for rank, idx in enumerate(top_indices, start=1):
            action_str = self.ACTION_MAP[idx] if idx < len(self.ACTION_MAP) else f"unknown_{idx}"
            tile_id, action_type = self._parse_action(action_str)
            q_val = float(q_vals[idx]) if idx < len(q_vals) else 0.0
            results.append(AIRecommendation(
                tile=tile_id,
                action_type=action_type,
                probability=float(probs[idx]),
                q_value=q_val,
                rank=rank
            ))
        return results

    def _parse_action(self, action_str: str) -> tuple[str, str]:
        if action_str in ("tsumogiri", "chi", "pon", "ankan", "kakan", "daiminkan", "hora", "riichi", "none"):
            return action_str, action_str
        return action_str, "dahai"
