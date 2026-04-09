"""
server/ai_adapters/base.py
MJAIプロトコルインターフェース基底クラス
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class MJAIAction:
    """MJAIプロトコル準拠のアクション表現"""
    def __init__(self, action_type: str, **kwargs):
        self.type = action_type  # "dahai", "chi", "pon", "kan", "reach", "hora", "none"
        self.params = kwargs

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, **self.params}

class AIRecommendation:
    """AIからの推奨手とメタデータ"""
    def __init__(
        self,
        ai_name: str,
        recommended_action: MJAIAction,
        confidence: Optional[float] = None,  # 0.0-1.0
        reasoning: Optional[str] = None,     # 定性説明
        raw_output: Optional[dict] = None    # 生出力
    ):
        self.ai_name = ai_name
        self.recommended_action = recommended_action
        self.confidence = confidence
        self.reasoning = reasoning
        self.raw_output = raw_output

class BaseAIAdapter(ABC):
    """MJAIプロトコル経由で麻雀AIと通信する抽象基底クラス"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """AIとの接続を確立"""
        pass
    
    @abstractmethod
    async def send_observation(self, mjai_events: List[dict]) -> None:
        """観測イベント（履歴・手牌状態の更新）を送信"""
        pass
    
    @abstractmethod
    async def request_action(self, legal_actions: List[MJAIAction]) -> Optional[AIRecommendation]:
        """合法手リストを与え、推奨アクションを取得"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """接続を閉じ、リソース解放"""
        pass
