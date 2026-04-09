"""
server/ai_adapters/mortal_adapter.py
Mortal AI用 MJAIアダプター
"""
from __future__ import annotations

import json
import asyncio
from typing import List, Optional

import websockets

from .base import BaseAIAdapter, AIRecommendation, MJAIAction

class MortalAdapter(BaseAIAdapter):
    """MortalとのWebSocket通信を行うアタプター (MJAI互換)"""
    
    def __init__(self, endpoint: str = "ws://127.0.0.1:8080", model: str = "oracle"):
        self.endpoint = endpoint
        self.model = model
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        
    async def connect(self) -> bool:
        if self.ws is not None:
            return True
            
        try:
            self.ws = await websockets.connect(f"{self.endpoint}?model={self.model}")
            # start_gameイベントを送信して初期化（MJAI仕様に合わせて）
            await self.ws.send(json.dumps({"type": "start_game", "id": 0}))
            return True
        except Exception as e:
            print(f"Mortal接続エラー: {e}")
            return False
            
    async def send_observation(self, mjai_events: List[dict]) -> None:
        """過去のイベント履歴や観測を送信する (必要に応じて)"""
        # Mortalに途中から接続する場合などに実装しますが、通常は request_action にまとめるか
        # 1イベントずつ send します。今回は一括送信を想定。
        if not self.ws:
            return
        # 簡易実装：今のところ特に何もしない（Mortal側はステートレスリクエスト対応版を想定）
        pass
    
    async def request_action(self, legal_actions: List[MJAIAction]) -> Optional[AIRecommendation]:
        if not self.ws:
            return None
            
        # 本来はmjai_eventsやriichi_envフォーマットのobservationを送る必要がありますが、
        # UIから呼ばれる際のアダプタ層として、Mortalの入出力形式を再現します。
        request = {
            "type": "request_action",
            "possible_actions": [a.to_dict() for a in legal_actions],
            # "observation": "..." # 盤面情報は send_observation で送っている想定かここで包むか
        }
        
        try:
            await self.ws.send(json.dumps(request))
            response_str = await asyncio.wait_for(self.ws.recv(), timeout=3.0)
            result = json.loads(response_str)
            
            # 推奨アクションをMJAIActionに変換
            act_type = result.get("type", "none")
            kwargs = {}
            if "pai" in result:
                kwargs["pai"] = result["pai"]
            if "tsumogiri" in result:
                kwargs["tsumogiri"] = result["tsumogiri"]
            if "consumed" in result:
                kwargs["consumed"] = result["consumed"]
                
            action = MJAIAction(act_type, **kwargs)
            return AIRecommendation(
                ai_name="Mortal",
                recommended_action=action,
                confidence=result.get("meta", {}).get("q_value", None),
                reasoning="牌効率・期待値最大化の選択（Mortal）",
                raw_output=result
            )
        except asyncio.TimeoutError:
            print("Mortal応答タイムアウト")
            return None
        except Exception as e:
            print(f"Mortal requestエラー: {e}")
            return None
            
    async def disconnect(self) -> None:
        if self.ws:
            await self.ws.close()
            self.ws = None
