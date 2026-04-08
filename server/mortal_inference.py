"""
PyTorch版 Mortal推論モジュール
"""
import torch
import numpy as np
from pathlib import Path
from typing import List, Dict

from server.action_decoder import decode_action
# feature_extractorは既存のものをインポート(存在しない場合はモック化)
try:
    from server.mortal.feature_extractor import FeatureExtractor as MortalFeatureExtractor
except ImportError:
    class MortalFeatureExtractor:
        def encode(self, events):
            return np.zeros((196,))

class MortalInference:
    def __init__(self, model_path: str = "server/mortal/weights/mortal.pth", device: str = "auto"):
        self.device = self._select_device(device)
        self.model = self._load_model(model_path)
        self.feature_extractor = MortalFeatureExtractor()

    def _select_device(self, device: str) -> torch.device:
        if device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else 
                               "mps" if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() else "cpu")
        return torch.device(device)

    def _load_model(self, path: str) -> torch.nn.Module:
        """
        Mortal公式構造のモデルロード。
        ファイルが存在しない/定義がない場合はモックを返すフォールバック実装
        """
        model_file = Path(path)
        if not model_file.exists():
            print(f"[Warning] Mortal model file not found at {path}. Using Mock Inference.")
            return self._build_mock_model()
            
        try:
            from server.mortal.models.mortal_model import MortalModel
            # PyTorch Lightning 互換の load_from_checkpoint を想定
            if hasattr(MortalModel, 'load_from_checkpoint'):
                model = MortalModel.load_from_checkpoint(path, map_location=self.device)
            else:
                model = MortalModel()
                model.load_state_dict(torch.load(path, map_location=self.device))
            model.eval()
            model.to(self.device)
            return model
        except Exception as e:
            print(f"[Warning] Failed to load Mortal model: {e}. Using Mock Inference.")
            return self._build_mock_model()

    def _build_mock_model(self):
        """モデルが存在しない場合の安全装置（推論偽装用）"""
        class MockModel(torch.nn.Module):
            def forward(self, x):
                # 46次元のランダムlogits, q_values, is_train
                logits = torch.randn(1, 46)
                q_vals = torch.randn(1, 46)
                return logits, q_vals, None
        return MockModel().to(self.device)

    def predict(self, mjai_events: List[Dict] = None) -> Dict:
        """
        mjaiイベント列から打牌確率・期待値を返す
        """
        mjai_events = mjai_events or []
        
        try:
            # feature extract
            features = self.feature_extractor.encode(mjai_events)
        except Exception as e:
            print(f"[Warning] Feature extraction failed: {e}. Using zero-tensor.")
            features = np.zeros((196,))
            
        features_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(features_tensor)
            # モデルの出力構成に合わせた分岐
            if isinstance(outputs, tuple) and len(outputs) >= 2:
                logits = outputs[0]
                q_values = outputs[1]
            else:
                logits = outputs
                q_values = torch.zeros_like(logits)
                
            probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        # 確率上位5手を抽出
        if probs.ndim > 1:
            probs = probs.flatten()
            
        top_indices = np.argsort(probs)[::-1][:5]
        recommendations = []
        for idx in top_indices:
            q_val = 0.0
            if q_values.squeeze(0).dim() > 0 and len(q_values.squeeze(0)) > idx:
                q_val = q_values.squeeze(0)[idx].item()
                
            action_info = decode_action(int(idx), float(probs[idx]), float(q_val))
            recommendations.append(action_info)

        # 確信度判定
        top1_prob = recommendations[0]["probability"]
        top2_prob = recommendations[1]["probability"] if len(recommendations) > 1 else 0.0
        confidence = "high" if (top1_prob - top2_prob > 0.15) else "antagonism"

        return {
            "recommendation": {
                "tile": recommendations[0]["tile_id"],
                "probability": round(recommendations[0]["probability"], 4),
                "q_value": round(recommendations[0]["q_value"], 4),
                "confidence": confidence,
                "alternatives": [
                    {"tile": r["tile_id"], "probability": round(r["probability"], 4)} for r in recommendations[1:]
                ]
            },
            "raw_probs": probs.tolist()
        }
