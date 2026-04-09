"""
server/ai_adapters/rulebase_adapter.py
定性推論ルールエンジン用アダプター
"""
from __future__ import annotations

import logging
from typing import List, Optional

from .base import BaseAIAdapter, AIRecommendation, MJAIAction
# 我々のStrategyJudgeを利用する想定ですが、今回は仮のインポートモックを使用するか直接利用
try:
    from server.engines.strategy_judge import StrategyJudge
    from server.rules.direction2_engine import StrategyEngine
except ImportError:
    StrategyJudge = None
    StrategyEngine = None

logger = logging.getLogger(__name__)

class RulebaseAdapter(BaseAIAdapter):
    """
    定性フレームワークに基づく軽量AIアダプター。
    同一プロセスで同期的に評価を行い、推奨手とその理由を返します。
    """
    def __init__(self, engine=None):
        # 外部からDIできるように設計
        self.engine = engine
        
    async def connect(self) -> bool:
        # DB接続や外部プロバイダがないインプロセスのため即座にTrue
        return True
        
    async def send_observation(self, mjai_events: List[dict]) -> None:
        pass
        
    async def request_action(self, legal_actions: List[MJAIAction]) -> Optional[AIRecommendation]:
        if not legal_actions:
            return None
            
        # UI/アグリゲータ単体テスト向けのモック動作（エンジンがない場合）
        if self.engine is None:
            # ダミーで最も基本的なアクション（1番目の合法手）を選択
            fallback_action = legal_actions[0]
            for a in legal_actions:
                if a.type == "dahai":
                    fallback_action = a
                    break
                    
            return AIRecommendation(
                ai_name="Rulebase (定性)",
                recommended_action=fallback_action,
                confidence=None,
                reasoning="中盤は受入枚数を広げて聴牌を早める（ダミー定性理由）",
                raw_output={"paradigm": "PAR_SPEED", "mock": True}
            )
            
        # 本番のエンジンがある場合は、評価コンテキストを構築して渡す
        try:
            # TODO: 厳密に局面コンテキストを構築する処理（Phase2で実装）
            perspective = self.engine.evaluate_current_situation(
                context={},
                hand=[]
            )
            
            # 定性フレームワークに基づく推奨牌を選択
            recommended_tile = getattr(perspective, "recommended_tile", "1m")
            action = MJAIAction("dahai", pai=recommended_tile)
            
            return AIRecommendation(
                ai_name="Rulebase (定性)",
                recommended_action=action,
                confidence=None,
                reasoning=getattr(perspective, "core_principle", "状況に応じた定性的打牌"),
                raw_output={"paradigm": getattr(perspective, "paradigm_id", "UNKNOWN")}
            )
        except Exception as e:
            logger.error(f"Rulebase engine error: {e}")
            return None

    async def disconnect(self) -> None:
        pass
