# core/inference/adapters/onnx_adapter.py
import onnxruntime as ort
import numpy as np
from pathlib import Path
from typing import Dict, Any
from ..base import AIEngineAdapter

class ONNXEngineAdapter(AIEngineAdapter):
    """ONNXモデル用統一アダプター（kanachan/Phoenix等のONNX変換版に対応）"""
    
    def load_model(self) -> None:
        model_path = Path(self.model_dir) / "model.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {model_path}")
        
        # CPU/GPU自動切り替え
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def infer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 手牌を34種カウントベクトルに変換
        hand = state.get("hand", [])
        tiles_34 = [0.0] * 34
        suit_map = {'m': 0, 'p': 9, 's': 18, 'z': 27}
        for t in hand:
            if len(t) < 2: continue
            num, suit = int(t[0]), t[1]
            if suit in suit_map:
                tiles_34[suit_map[suit] + num - 1] += 1.0

        # 2. モデル入力形状に合わせバッチ次元追加
        input_data = np.array([tiles_34], dtype=np.float32)
        
        # 3. 推論実行
        outputs = self.session.run([self.output_name], {self.input_name: input_data})
        scores = outputs[0][0]  # (34,) 形状を仮定
        
        # 4. 結果マッピング（最高スコアの牌を返す）
        best_idx = int(np.argmax(scores))
        confidence = float(np.max(scores))
        
        # インデックス → 牌文字列変換
        suits = ['m', 'p', 's', 'z']
        suit_idx = best_idx // 9
        tile_num = (best_idx % 9) + 1
        recommended = f"{tile_num}{suits[suit_idx]}" if suit_idx < 3 else f"{tile_num}z"
        
        return {
            "move": recommended,
            "score": confidence,
            "metadata": {
                "raw_scores": scores.tolist(),
                "shanten_placeholder": 0,  # 必要に応じて別モジュールで計算
                "safety_placeholder": 0.0
            }
        }
