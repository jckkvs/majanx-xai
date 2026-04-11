# core/inference/adapters/kanachan_adapter.py
import os
from typing import Dict, Any, List
import numpy as np
import onnxruntime as ort
from ..base import AIEngineAdapter

class KanachanAdapter(AIEngineAdapter):
    """
    kanachan (ONNX) 用のアダプター
    HuggingFace からダウンロードされた ONNX モデルをロードして推論を実行する
    """

    def load_model(self) -> None:
        model_path = os.path.join(self.model_dir, "model.onnx")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # 実行プロバイダーの選択 (DirectML > CPU)
        providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
        self._model = ort.InferenceSession(model_path, providers=providers)
        print(f"[KanachanAdapter] Model loaded from {model_path}")

    def infer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        局面状態を特徴量ベクトルに変換し、ONNX推論を実行
        """
        if self._model is None:
            self.load_model()

        # 特徴量抽出 (実際の実装では kanachan 固有のベクトル化ロジックが必要)
        # ここでは構造を示すためのプレースホルダー
        features = self._extract_features(state)
        
        input_name = self._model.get_inputs()[0].name
        output_name = self._model.get_outputs()[0].name
        
        # 推論実行
        raw_output = self._model.run([output_name], {input_name: features})[0]
        
        # 出力デコード (Softmax 等)
        move_probs = self._softmax(raw_output[0])
        best_move_idx = np.argmax(move_probs)
        
        # インデックスから牌文字列への変換 (1m-9m, 1p-9p, 1s-9s, 1z-7z, etc.)
        move = self._idx_to_tile(best_move_idx)
        score = float(move_probs[best_move_idx])

        return {
            "move": move,
            "score": score,
            "metadata": {
                "engine": "kanachan",
                "shanten": state.get("shanten"),
                "confidence": score
            }
        }

    def _extract_features(self, state: Dict[str, Any]) -> np.ndarray:
        # kanachan の入力形式に合わせたダミーデータ (実際は 1xN の float32 配列)
        return np.random.randn(1, 1024).astype(np.float32)

    def _idx_to_tile(self, idx: int) -> str:
        # インデックスマッピングのプレースホルダー
        tiles = ["1m", "5p", "1z"] # 実際は 34+種のマッピング
        return tiles[idx % len(tiles)]

    def _softmax(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()
