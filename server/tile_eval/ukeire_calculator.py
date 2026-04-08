"""
形状進化を考慮した受入枚数計算モジュール
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from .tile_analyzer import TileAnalyzer, TileConnection, TileRelation

@dataclass
class UkeireResult:
    """受入計算結果"""
    tile_id: str
    raw_ukeire: int      # 単純受入枚数
    effective_ukeire: float  # 形状進化・安定度を考慮した有効受入
    improvement_tiles: List[str]  # 向聴改善に寄与する牌
    shape_evolution: float  # 形状進化期待値

class UkeireCalculator:
    """形状進化を考慮した受入枚数計算"""
    
    # 牌の残り枚数（初期値）
    TILE_REMAINING = {i: 4 for i in range(34)}
    
    def __init__(self, visible_tiles: Dict[str, int]):
        """公開牌から残り枚数を計算"""
        self.remaining = self.TILE_REMAINING.copy()
        for tile_id, count in visible_tiles.items():
            idx = self._tile_to_idx(tile_id)
            self.remaining[idx] = max(0, self.remaining[idx] - count)
    
    def calculate(self, hand: List[str], discard_candidate: str, 
                  connections: Dict[str, TileConnection]) -> UkeireResult:
        """打牌候補ごとの有効受入を計算"""
        # 手牌から候補牌を除去した状態をシミュレーション
        sim_hand = hand.copy()
        if discard_candidate in sim_hand:
            sim_hand.remove(discard_candidate)
        
        # 各ツモ牌に対する評価
        total_effective = 0.0
        improvement_tiles = []
        shape_evolution_sum = 0.0
        
        for draw_idx in range(34):
            if self.remaining[draw_idx] == 0:
                continue
            
            draw_tile = self._idx_to_tile(draw_idx)
            test_hand = sim_hand + [draw_tile]
            
            # 受入判定：向聴数改善または形状進化
            is_improvement, evolution_value = self._evaluate_draw(
                test_hand, connections, discard_candidate
            )
            
            if is_improvement:
                remaining = self.remaining[draw_idx]
                total_effective += remaining * (1.0 + evolution_value * 0.5)
                improvement_tiles.append(draw_tile)
                shape_evolution_sum += evolution_value * remaining
        
        raw_ukeire = sum(self.remaining[self._tile_to_idx(t)] for t in improvement_tiles)
        effective = total_effective
        evolution_avg = shape_evolution_sum / max(1, raw_ukeire)
        
        return UkeireResult(
            tile_id=discard_candidate,
            raw_ukeire=raw_ukeire,
            effective_ukeire=effective,
            improvement_tiles=improvement_tiles,
            shape_evolution=evolution_avg
        )
    
    def _evaluate_draw(self, hand: List[str], base_connections: Dict[str, TileConnection],
                       discarded: str) -> Tuple[bool, float]:
        """ツモ牌が向聴改善または形状進化に寄与するか評価"""
        analyzer = TileAnalyzer()
        new_connections = analyzer.analyze_hand(hand)
        
        # 向聴数改善の簡易判定（接続数増加で近似）
        base_conn_count = sum(len(c.connected_tiles) for c in base_connections.values())
        new_conn_count = sum(len(c.connected_tiles) for c in new_connections.values())
        
        is_improvement = new_conn_count > base_conn_count
        
        # 形状進化価値の計算
        evolution = 0.0
        for tile_id, conn in new_connections.items():
            if TileRelation.RYANMEN in conn.relations and tile_id not in base_connections:
                evolution += 0.3  # 新規両面形成
            elif TileRelation.COMPOUND in conn.relations:
                evolution += 0.2  # 複合形進化
        
        return is_improvement, min(evolution, 1.0)
    
    def _tile_to_idx(self, tile_id: str) -> int:
        """牌ID→0-33インデックス変換"""
        suit = tile_id[-1]
        if suit == 'z':
            return 27 + int(tile_id[0]) - 1
        suit_idx = {'m': 0, 'p': 1, 's': 2}[suit]
        num = int(tile_id[1]) if 'r' in tile_id else int(tile_id[0])
        return suit_idx * 9 + (num - 1)
    
    def _idx_to_tile(self, idx: int) -> str:
        """インデックス→牌ID変換"""
        if idx >= 27:
            return f"{idx - 26}z"
        suit = ['m', 'p', 's'][idx // 9]
        num = (idx % 9) + 1
        return f"{num}{suit}"
