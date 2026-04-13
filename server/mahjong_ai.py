"""
Latest OSS Mahjong AI Engine
Based on pjura/mahjong_ai from HuggingFace
https://huggingface.co/pjura/mahjong_ai
"""

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModelForSequenceClassification
import numpy as np
from typing import Dict, List, Tuple, Optional
import json

class MahjongBoardEncoder:
    """手牌と捨て牌をエンコード"""
    
    def __init__(self, hand_size: int = 68, discard_size: int = 136):
        self.hand_size = hand_size
        self.discard_size = discard_size
        
    def encode(self, hand_tiles: List[str], discard_pool: List[str]) -> torch.Tensor:
        """
        手牌と捨て牌を特徴量ベクトルに変換
        
        Args:
            hand_tiles: 手牌（例: ["1m", "2m", "3m", ...]）
            discard_pool: 捨て牌プール
            
        Returns:
            torch.Tensor: 特徴量ベクトル
        """
        # 手牌エンコード（68次元）
        hand_features = self._encode_tiles(hand_tiles, self.hand_size)
        
        # 捨て牌エンコード（136次元）
        discard_features = self._encode_tiles(discard_pool, self.discard_size)
        
        # 結合
        features = np.concatenate([hand_features, discard_features])
        return torch.tensor(features, dtype=torch.float32)
    
    def _encode_tiles(self, tiles: List[str], size: int) -> np.ndarray:
        """牌をone-hotエンコード"""
        encoding = np.zeros(size)
        tile_to_idx = self._get_tile_mapping()
        
        for i, tile in enumerate(tiles[:size]):
            if tile in tile_to_idx:
                idx = tile_to_idx[tile]
                if idx < size:
                    encoding[idx] = 1.0
                    
        return encoding
    
    def _get_tile_mapping(self) -> Dict[str, int]:
        """牌→インデックスのマッピング"""
        mapping = {}
        idx = 0
        
        # 萬子 (1-9)
        for i in range(1, 10):
            mapping[f"{i}m"] = idx
            idx += 1
            
        # 筒子 (1-9)
        for i in range(1, 10):
            mapping[f"{i}p"] = idx
            idx += 1
            
        # 索子 (1-9)
        for i in range(1, 10):
            mapping[f"{i}s"] = idx
            idx += 1
            
        # 字牌 (東西南北白發中)
        for wind in ["E", "S", "W", "N"]:
            mapping[wind] = idx
            idx += 1
            
        for dragon in ["Wh", "Gr", "Rd"]:
            mapping[dragon] = idx
            idx += 1
            
        # 0m, 0p, 0s (赤ドラ)用のフォールバックも追加しておく
        mapping["0m"] = mapping["5m"]
        mapping["0p"] = mapping["5p"]
        mapping["0s"] = mapping["5s"]

        return mapping


class LatestOSSMahjongAI:
    """最新OSS麻雀AI（pjura/mahjong_aiベース）"""
    
    def __init__(self, model_path: str = "pjura/mahjong_ai"):
        self.encoder = MahjongBoardEncoder()
        self.model = None
        self.config = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # モデル読み込み
        self._load_model(model_path)
        
    def _load_model(self, model_path: str):
        """モデルと設定を読み込み"""
        try:
            # 設定読み込み
            self.config = AutoConfig.from_pretrained(model_path)
            
            # モデル読み込み
            self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            self.model.to(self.device)
            self.model.eval()
            
            print(f"[AI] Loaded model from {model_path}")
            
        except Exception as e:
            print(f"[AI] Warning: Could not load from HuggingFace: {e}")
            print("[AI] Using random initialization for development")
            self._create_dummy_model()
    
    def _create_dummy_model(self):
        """開発用のダミーモデルを作成"""
        class DummyModel(nn.Module):
            def __init__(self, input_size=204, num_labels=34):
                super().__init__()
                self.fc1 = nn.Linear(input_size, 512)
                self.fc2 = nn.Linear(512, 256)
                self.fc3 = nn.Linear(256, num_labels)
                self.relu = nn.ReLU()
                self.softmax = nn.Softmax(dim=-1)
                
            def forward(self, x):
                x = self.relu(self.fc1(x))
                x = self.relu(self.fc2(x))
                x = self.softmax(self.fc3(x))
                return x
                
        self.model = DummyModel().to(self.device)
        self.model.eval()
    
    async def predict(self, game_state: Dict, hand_tiles: List[str]) -> Dict:
        """
        打牌予測
        
        Args:
            game_state: ゲーム状態
            hand_tiles: 手牌
            
        Returns:
            予測結果（推奨牌、確率、代替案）
        """
        # 捨て牌プールの取得
        discard_pool = self._extract_discard_pool(game_state)
        
        # 特徴量エンコード
        features = self.encoder.encode(hand_tiles, discard_pool)
        features = features.unsqueeze(0).to(self.device)  # バッチ次元追加
        
        # 推論
        with torch.no_grad():
            output = self.model(features)
            # DummyModelは softmax を適用したテンソルを返す仕組みだが、
            # HuggingFaceモデルを使用できた場合は output.logits で確率を計算するケースがあるため、フォールバックを入れる
            probabilities = output[0] if isinstance(output, tuple) else (output.logits[0] if hasattr(output, 'logits') else output[0])
            if not isinstance(output, tuple) and not hasattr(output, 'logits') and isinstance(self.model, nn.Module):
                probabilities = output[0]

        # マスキング処理 (手牌にない牌は候補から除外)
        probabilities = probabilities.clone()
        tile_decoder = self.encoder._get_tile_mapping()
        valid_indices = set()
        for t in hand_tiles:
            if t in tile_decoder:
                valid_indices.add(tile_decoder[t])
                
        for i in range(len(probabilities)):
            if i not in valid_indices:
                probabilities[i] = -1.0 # 除外

        # 確率の高い順にソート
        top_k = min(5, len(probabilities))
        top_values, top_indices = torch.topk(probabilities, top_k)
        
        # 結果を変換
        tile_decoder = self.encoder._get_tile_mapping()
        idx_to_tile = {v: k for k, v in tile_decoder.items()}
        
        recommended = {
            "recommended_tile": idx_to_tile.get(top_indices[0].item(), "unknown"),
            "probability": top_values[0].item(),
            "alternatives": [
                {
                    "tile": idx_to_tile.get(idx.item(), "unknown"),
                    "prob": prob.item()
                }
                for idx, prob in zip(top_indices[1:], top_values[1:])
            ]
        }
        
        return recommended
    
    def _extract_discard_pool(self, game_state: Dict) -> List[str]:
        """ゲーム状態から捨て牌プールを抽出"""
        discard_pool = []
        
        # 各家の捨て牌を収集
        if "players" in game_state:
            for player in game_state["players"]:
                if "discards" in player:
                    # 捨て牌のフォーマットから牌IDを抽出する可能性があるため、適切なプロパティアクセスを行う
                    for discard in player.get("discards", []):
                        if isinstance(discard, str):
                            discard_pool.append(discard)
                        elif isinstance(discard, dict) and "tile" in discard:
                            discard_pool.append(discard["tile"])
                        elif hasattr(discard, "id"):
                            discard_pool.append(discard.id)
                    
        return discard_pool
    
    def get_model_info(self) -> Dict:
        """モデル情報を取得"""
        return {
            "model_type": "pjura/mahjong_ai",
            "architecture": "TabularClassification",
            "device": str(self.device),
            "input_size": 204,  # 68 (hand) + 136 (discard)
            "output_size": 34   # 全牌の種類
        }
