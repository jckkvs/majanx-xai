# core/inference/adapters/rlcard_adapter.py
from typing import Dict, Any, List
import random
from ..base import AIEngineAdapter

class RLCardAdapter(AIEngineAdapter):
    """
    RLCard (PPO / DQN) 用のアダプター
    軽量な推論エンジンとして使用、またはフォールバックとして機能する
    """

    def load_model(self) -> None:
        # RLCard モデルのロード (現在は構造のみ)
        print(f"[RLCardAdapter] Model loading simulated from {self.model_dir}")
        pass

    def infer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        RLCard 形式の局面入力 → 推論
        """
        if self._model is None:
            # 本来は torch.load 等
            pass

        # 暫定的なロジック: 手牌からランダムに、または簡単なルールで選択
        # (実機統合時は rlcard.models.mahjong_ppo.Agent 等を呼び出す)
        hand = state.get("hand", [])
        move = random.choice(hand) if hand else "5p"
        
        # RLCard は通常 確率分布を返す
        confidence = 0.7 

        return {
            "move": move,
            "score": confidence,
            "metadata": {
                "engine": "rlcard",
                "strategy": "ppo_standard"
            }
        }
