"""
Mortalダイレクト推論へ完全統合された実働解説エンジン
"""
import numpy as np
from typing import List, Dict

from .engine import GameEngine

class CommentatorAI:
    def __init__(self, engine: 'GameEngine' = None):
        self.engine = engine
        
        # MortalInference の初期化
        try:
            from .mortal_inference import MortalInference
            self.mortal = MortalInference()
        except ImportError as e:
            print(f"[CommentatorAI] Failed to load MortalInference: {e}")
            self.mortal = None

    def analyze(self, seat: int, mjai_events: List[Dict] = None) -> Dict:
        """
        現在の状態からMortalの出力を呼び出し、トップ打牌候補と解説を返す
        手動ヒューリスティクス（TileEfficiency等）は一切介在しない。
        """
        if not self.mortal:
            return {"top3": [], "explanation": "Mortal推論エンジン未搭載", "choices": []}

        # 1. AI推論の実行
        # mjai_events が取得できる場合はそのまま流し込み、なければNone（フォールバック）を渡す
        prediction = self.mortal.predict(mjai_events)
        rec = prediction.get("recommendation", {})
        
        if not rec:
            return {"top3": [], "explanation": "判定不可", "choices": []}

        best_tile = rec.get("tile", "none")
        confidence = rec.get("confidence", "antagonism")
        probs = rec.get("probability", 0.0)
        q_val = rec.get("q_value", 0.0)
        alts = rec.get("alternatives", [])

        # 2. フロントエンド用 choices 形式へのマッピング
        # 元のUI描画互換を維持するため、choices配列を生成
        choices = []
        mortal_top3 = []
        
        # トップ推奨手
        choices.append({
            "tile": best_tile,
            "tile_name": best_tile,
            "prob": probs,
            "acceptance": int(q_val * 10), # 表示用ダミー数値としてQ値を活用
            "shanten": -1
        })
        mortal_top3.append({
            "tile_idx": 0, 
            "tile_name": best_tile,
            "shanten": -1,
            "acceptance": int(q_val * 10),
            "prob": probs
        })

        # 代替候補
        for idx, alt in enumerate(alts[:2]): # 上位3手まで表示
            choices.append({
                "tile": alt["tile"],
                "tile_name": alt["tile"],
                "prob": alt["probability"],
                "acceptance": 0,
                "shanten": -1
            })
            mortal_top3.append({
                "tile_idx": idx + 1,
                "tile_name": alt["tile"],
                "shanten": -1,
                "acceptance": 0,
                "prob": alt["probability"]
            })

        # 3. 判定根拠（AIからのメタ情報を使った言語化のみ）
        # 完全なMortalの確率的根拠に基づく。
        explanation = f"Mortal推奨: {best_tile} (確率: {probs:.1%})"
        if confidence == "high":
            explanation += "。確信度高く、他候補を大きく引き離しています。"
        else:
            explanation += "。僅差での推奨です。状況に応じた微調整が必要です。"
            if alts:
                explanation += f"（代替候補: {alts[0]['tile']}）"

        return {
            "top3": mortal_top3,
            "explanation": explanation,
            "current_shanten": -1, # シミュレーション排除のため不要
            "choices": choices,
            "recommendation": best_tile,
            "score": probs * 100.0,
            
            # 生データ
            "raw_mortal": prediction
        }
