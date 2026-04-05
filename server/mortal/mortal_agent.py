# server/mortal/mortal_agent.py
import torch
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import sys
import os

# Mortalリポジトリのインポート用パス設定
MORTAL_PATH = Path(__file__).parent.parent.parent / "Mortal"
if MORTAL_PATH.exists():
    sys.path.insert(0, str(MORTAL_PATH))

try:
    from mortal import MortalModel
    from mortal.feature import FeatureExtractor
    from mortal.action_mask import ActionMasker as MortalActionMasker
    MORTAL_AVAILABLE = True
except ImportError:
    MortalModel = None
    FeatureExtractor = None
    MortalActionMasker = None
    MORTAL_AVAILABLE = False

class MortalAgent:
    """
    Mortal AI の完全統合エージェント
    mjaiイベントを受け取り、合法手マスク適用後の確率分布を返す
    """
    
    # Mortalのアクション空間定義（46次元）
    ACTION_SPACE = {
        'dahai': list(range(34)),      # 0-33: 打牌
        'tsumogiri': 34,                # 34: ツモ切り
        'chi': 35,                      # 35: チー
        'pon': 36,                      # 36: ポン
        'kan_daimin': 37,               # 37: 大明槓
        'kan_ankan': 38,                # 38: 暗槓
        'kan_kakan': 39,                # 39: 加槓
        'hora': 40,                     # 40: 和了
        'ryukyoku': 41,                 # 41: 流局
        'none': 42,                     # 42: パス
        'reserve': list(range(43, 46))  # 43-45: 予約
    }
    
    def __init__(
        self, 
        weight_path: str = "server/mortal/weights/mortal.pth",
        device: Optional[str] = None,
        use_gpu: bool = True
    ):
        self.device = self._select_device(use_gpu, device)
        self.model = None
        self.feature_extractor = None
        self.action_masker = MortalActionMasker() if MORTAL_AVAILABLE else None
        self.is_loaded = False
        
        if Path(weight_path).exists():
            self._load_model(weight_path)
        else:
            print(f"[MortalAgent] 重みファイルが見つかりません: {weight_path}")
            print("[MortalAgent] ルールベースフォールバックモードで起動します")
    
    def _select_device(self, use_gpu: bool, device: Optional[str]) -> torch.device:
        if device:
            return torch.device(device)
        if use_gpu and torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    
    def _load_model(self, weight_path: str):
        """Mortalモデルと特徴量抽出器をロード"""
        try:
            # Mortalモデルのロード（公式実装準拠）
            self.model = MortalModel.load_from_checkpoint(
                weight_path, 
                map_location=self.device
            )
            self.model.eval()
            self.model.to(self.device)
            
            # 特徴量抽出器の初期化
            self.feature_extractor = FeatureExtractor()
            
            self.is_loaded = True
            print(f"[MortalAgent] ✅ モデルロード完了: {self.device}")
            
        except Exception as e:
            print(f"[MortalAgent] ❌ モデルロード失敗: {e}")
            self.is_loaded = False
    
    def predict(
        self, 
        mjai_events: List[Dict], 
        legal_actions: Optional[List[str]] = None,
        return_q_values: bool = False
    ) -> Dict:
        """
        mjaiイベント列から打牌確率を予測
        """
        if not self.is_loaded:
            return self._fallback_predict(mjai_events, legal_actions)
        
        try:
            # 1. mjaiイベント -> 特徴量テンソル
            features = self.feature_extractor.encode(mjai_events)
            features = features.to(self.device)
            
            # 2. 推論実行
            with torch.no_grad():
                logits, q_values, value = self.model(features)
                
            # 3. 確率分布に変換
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]  # shape: (46,)
            
            # 4. 合法手マスクの適用
            if legal_actions:
                mask = self._create_mask_from_actions(legal_actions)
            else:
                # mjaiイベントから自動で合法手マスク生成
                mask = self.action_masker.create_mask(mjai_events)
            
            probs[~mask] = -1e9  # 違法手をマスク
            probs = np.exp(probs) / np.sum(np.exp(probs))  # 再正規化
            
            # 5. 打牌確率のみ抽出（0-33）
            tile_probs = probs[:34].copy()
            
            # 6. 推奨アクションの決定
            best_idx = int(np.argmax(probs))
            best_action = self._idx_to_action(best_idx, mjai_events)
            
            result = {
                "action": best_action,
                "probs": tile_probs.tolist(),
                "is_mortal": True
            }
            
            if return_q_values:
                result["q_values"] = q_values.cpu().numpy()[0].tolist()
                result["value"] = float(value.item())
                
            return result
            
        except Exception as e:
            print(f"[MortalAgent] 推論エラー: {e}")
            return self._fallback_predict(mjai_events, legal_actions)
    
    def _create_mask_from_actions(self, legal_actions: List[str]) -> np.ndarray:
        """アクション名リストから46次元マスクを生成"""
        mask = np.zeros(46, dtype=bool)
        
        for action in legal_actions:
            if action.startswith("dahai:"):
                tile = action.split(":")[1]
                idx = self._tile_to_idx(tile)
                if 0 <= idx < 34:
                    mask[idx] = True
            elif action == "tsumogiri":
                mask[self.ACTION_SPACE['tsumogiri']] = True
            elif action == "chi":
                mask[self.ACTION_SPACE['chi']] = True
            elif action == "pon":
                mask[self.ACTION_SPACE['pon']] = True
            elif action == "kan":
                mask[self.ACTION_SPACE['kan_daimin']] = True
                mask[self.ACTION_SPACE['kan_ankan']] = True
                mask[self.ACTION_SPACE['kan_kakan']] = True
            elif action in ["hora", "ron", "tsumo"]:
                mask[self.ACTION_SPACE['hora']] = True
            elif action == "none":
                mask[self.ACTION_SPACE['none']] = True
                
        return mask
    
    def _tile_to_idx(self, tile: str) -> int:
        """牌文字列 -> 0-33インデックス変換"""
        suits = ['m', 'p', 's', 'z']
        tile = tile.rstrip('r')  # 赤ドラ表記を除去
        
        for suit_idx, suit in enumerate(suits):
            if tile.endswith(suit):
                num = int(tile[:-1])
                if suit_idx < 3:  # 数牌
                    return suit_idx * 9 + (num - 1)
                else:  # 字牌
                    return 27 + (num - 1)
        return -1
    
    def _idx_to_action(self, idx: int, events: List[Dict]) -> Dict:
        """インデックス -> mjaiアクション変換"""
        if 0 <= idx < 34:
            suits = ['m', 'p', 's', 'z']
            if idx < 27:
                suit = suits[idx // 9]
                num = (idx % 9) + 1
                tile = f"{num}{suit}"
            else:
                num = (idx - 27) + 1
                tile = f"{num}z"
            return {"type": "dahai", "pai": tile}
        elif idx == 34:
            return {"type": "dahai", "tsumogiri": True}
        elif idx == 35:
            return {"type": "chi"}
        elif idx == 36:
            return {"type": "pon"}
        elif idx in [37, 38, 39]:
            return {"type": "kan"}
        elif idx == 40:
            return {"type": "hora"}
        else:
            return {"type": "none"}
    
    def _fallback_predict(self, mjai_events: List[Dict], legal_actions: Optional[List[str]]) -> Dict:
        """Mortal未ロード時のフォールバック（均等確率）"""
        probs = np.zeros(34)
        if legal_actions:
            for action in legal_actions:
                if action.startswith("dahai:"):
                    idx = self._tile_to_idx(action.split(":")[1])
                    if 0 <= idx < 34:
                        probs[idx] = 1.0
        else:
            probs[:] = 1.0
        
        if probs.sum() > 0:
            probs = probs / probs.sum()
            
        return {
            "action": {"type": "dahai", "pai": "5m"},  # ダミー
            "probs": probs.tolist(),
            "is_mortal": False
        }
    
    def get_feature_dim(self) -> int:
        """特徴量の次元数を返す"""
        return 196 if self.feature_extractor else 0
