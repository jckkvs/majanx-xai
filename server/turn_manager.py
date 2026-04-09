"""
server/turn_manager.py
Implements: ターン制御・鳴き優先順位・順番管理
"""
from __future__ import annotations

from typing import List, Optional
from dataclasses import dataclass

from server.models import Tile

@dataclass
class ActionOption:
    type: str # 'ron' | 'pon' | 'kan' | 'chi'
    player_idx: int
    priority: int

@dataclass
class MeldRequest:
    player_idx: int
    meld_type: str # 'ron' | 'pon' | 'kan' | 'chi'
    discarded_tile: str

class TurnManager:
    """ターン制御・鳴き優先順位・順番管理"""
    
    MELD_PRIORITY = {
        'ron': 3,      # 最優先
        'pon': 2,
        'kan': 2,      # ポンと同優先度
        'chi': 1,      # 最下位
    }
    
    def __init__(self, player_seats: List[int] = None):
        if player_seats is None:
            self.seats = [0, 1, 2, 3]
        else:
            self.seats = player_seats
        self.current_turn_idx = 0
        
    def get_next_player_idx(self, current_idx: int) -> int:
        """反時計回りの次プレイヤーを計算"""
        return (current_idx + 1) % 4
    
    def resolve_meld_conflict(self, requests: List[MeldRequest]) -> Optional[MeldRequest]:
        """
        複数プレイヤーからの鳴きリクエストを解決
        優先順位: ロン > ポン/カン > チー、同優先度は下家優先
        """
        if not requests:
            return None
        
        # 1. 優先度でフィルタリング
        max_priority = max(self.MELD_PRIORITY[req.meld_type] for req in requests)
        candidates = [r for r in requests if self.MELD_PRIORITY[r.meld_type] == max_priority]
        
        if len(candidates) == 1:
            return candidates[0]
        
        # 2. 同優先度の場合、打牌者からの距離で解決（下家優先）
        # 仕様に従ってリクエストクラスに discarder_idx がない場合は外部から与える必要がありますが、
        # 今回の仕様（TurnManager）では current_turn_idx が打牌者です。
        discarder_idx = self.current_turn_idx
        candidates.sort(key=lambda r: (r.player_idx - discarder_idx) % 4)
        
        return candidates[0]
    
    def get_action_order(self, discarder_idx: int, discarded_tile: Tile) -> List[ActionOption]:
        """
        打牌後のアクション順序の候補スタブ
        (実戦ロジックはGameLoopやEngineから呼び出される想定)
        """
        return []
