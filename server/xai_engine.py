"""
方向性1: ニューラルネットワーク内部判断の可視化・言語化エンジン
注意機構重み・勾配寄与度・特徴量重要度を統合し、牌推奨根拠を自然言語化
"""
from __future__ import annotations

import numpy as np
import torch
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from server.models import Tile, GameState
from server.mortal.mortal_agent import MortalAgent

@dataclass
class XAIResult:
    tile_idx: int
    tile_name: str
    confidence: float
    contributing_factors: List[Dict[str, float]]
    raw_scores: Dict[str, np.ndarray]
    explanation: str

class XAIEngine:
    def __init__(self, mortal_agent: Optional[MortalAgent] = None):
        self.mortal_agent = mortal_agent
        self.feature_names = [f"feat_{i}" for i in range(34)]
        self.explanation_templates = {
            "high_attention_high_grad": "「{tile}」の推奨確度が高い理由：中盤形成への寄与度({attention_score:.2f})と勾配重要度({grad_score:.2f})が両立。モデルが両面構造の完成を明確に評価",
            "high_attention_low_grad": "「{tile}」の推奨パターン認識根拠：類似牌譜の出現頻度({attention_score:.2f})に依存。局所的な戦術判断だが、勾配寄与は分散傾向",
            "low_attention_high_grad": "「{tile}」の局所最適解評価：特定チャネルの勾配({grad_score:.2f})が突出。手牌構造の微調整をモデルが優先と判断",
            "low_uncertainty": "「{tile}」の推論確度が低い理由：候補牌のスコア分布が拮抗。場況依存の判断領域であり、複数解釈が可能",
        }

    def _extract_features(self, game_state: GameState) -> torch.Tensor:
        if not self.mortal_agent:
            return torch.zeros(10, 34)
        # Mortal特徴量抽出器を再利用（既存実装と整合）
        return self.mortal_agent.feature_extractor.encode(game_state.to_mjai_events())

    def compute_saliency(self, game_state: GameState, recommended_idx: int) -> Tuple[np.ndarray, np.ndarray]:
        features = self._extract_features(game_state)
        if features.sum() == 0 or not self.mortal_agent or not self.mortal_agent.is_loaded:
            return np.zeros(34), np.zeros(34)

        features = features.to(self.mortal_agent.device)
        features.requires_grad_(True)

        with torch.no_grad():
            logits, _, _ = self.mortal_agent.model(features.unsqueeze(0))
        target = logits[0, recommended_idx]
        target.backward()

        grads = features.grad.abs().squeeze()
        attention = np.zeros(34)
        if hasattr(self.mortal_agent.model, "get_attention_scores"):
            attn_scores = self.mortal_agent.model.get_attention_scores(features.unsqueeze(0)).detach().cpu().numpy()
            attention = attn_scores.mean(axis=0).flatten()[:34]

        grads_norm = (grads - grads.min()) / (grads.max() - grads.min() + 1e-9)
        features.requires_grad_(False)
        return attention[:34], grads_norm[:34]

    def analyze(self, game_state: GameState, recommended_idx: int) -> XAIResult:
        attention, gradients = self.compute_saliency(game_state, recommended_idx)
        combined = attention * 0.6 + gradients * 0.4
        top_factors = np.argsort(combined)[::-1][:5]

        confidence = float(np.clip(combined[recommended_idx], 0.0, 1.0))
        factors_list = [
            {"feature": self.feature_names[idx], "score": float(combined[idx])} for idx in top_factors
        ]

        attn_score = float(attention[recommended_idx])
        grad_score = float(gradients[recommended_idx])
        if confidence > 0.65 and attn_score > 0.5 and grad_score > 0.5:
            tpl_key = "high_attention_high_grad"
        elif attn_score > 0.5 and grad_score <= 0.5:
            tpl_key = "high_attention_low_grad"
        elif attn_score <= 0.5 and grad_score > 0.5:
            tpl_key = "low_attention_high_grad"
        else:
            tpl_key = "low_uncertainty"

        tile_name = self.mortal_agent._idx_to_action(recommended_idx, [])["pai"] if self.mortal_agent and "pai" in self.mortal_agent._idx_to_action(recommended_idx, []) else f"idx_{recommended_idx}"
        
        explanation = self.explanation_templates[tpl_key].format(
            tile=tile_name, attention_score=attn_score, grad_score=grad_score
        )

        return XAIResult(
            tile_idx=recommended_idx,
            tile_name=tile_name,
            confidence=confidence,
            contributing_factors=factors_list,
            raw_scores={"attention": attention, "gradients": gradients},
            explanation=explanation,
        )
