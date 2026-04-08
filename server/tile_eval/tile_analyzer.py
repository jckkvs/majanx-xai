"""
牌の連結関係・形状パターンを解析するモジュール
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

class TileRelation(Enum):
    ISOLATED = auto()      # 孤立牌（連結なし）
    PAIR_CANDIDATE = auto() # 対子候補（同種2枚）
    RYANMEN = auto()       # 両面（23, 34, ..., 78）
    KANCHAN = auto()       # 嵌張（13, 24, ..., 79）
    EDGE = auto()          # 辺張（12, 89）
    OVERLAP = auto()       # 過剰形（2345, 3456等）
    COMPOUND = auto()      # 複合形（234+56, 34+567等）

@dataclass(frozen=True)
class TileConnection:
    """牌の連結情報"""
    tile_id: str
    suit: str  # 'm', 'p', 's', 'z'
    number: Optional[int]  # 字牌はNone
    is_red: bool
    relations: List[TileRelation] = field(default_factory=list)
    connected_tiles: List[str] = field(default_factory=list)
    pair_count: int = 0  # 同種枚数
    shape_stability: float = 1.0  # 形状安定度（0.0-1.0）

class TileAnalyzer:
    """牌の連結関係を解析するクラス"""
    
    # 数牌の連結定義（両面・嵌張・辺張の判定用）
    RYANMEN_PATTERNS = {
        (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8)
    }
    KANCHAN_PATTERNS = {
        (1, 3), (2, 4), (3, 5), (4, 6), (5, 7), (6, 8), (7, 9)
    }
    EDGE_PATTERNS = {
        (1, 2), (8, 9)
    }
    
    def __init__(self):
        self.tile_counts: Dict[str, int] = {}
        
    def analyze_hand(self, hand: List[str]) -> Dict[str, TileConnection]:
        """手牌全体を解析し、各牌の連結情報を返す"""
        # 牌のカウント
        self.tile_counts = {}
        for tile in hand:
            self.tile_counts[tile] = self.tile_counts.get(tile, 0) + 1
        
        results = {}
        for tile in set(hand):
            results[tile] = self._analyze_single_tile(tile, hand)
        
        return results
    
    def _analyze_single_tile(self, tile: str, hand: List[str]) -> TileConnection:
        """単一牌の連結関係を解析"""
        suit = tile[-1]
        is_red = 'r' in tile
        
        if suit == 'z':  # 字牌
            number = int(tile[0])
            return TileConnection(
                tile_id=tile, suit='z', number=number, is_red=is_red,
                relations=[TileRelation.PAIR_CANDIDATE] if self.tile_counts[tile] >= 2 else [TileRelation.ISOLATED],
                connected_tiles=[],
                pair_count=self.tile_counts[tile],
                shape_stability=0.9 if self.tile_counts[tile] >= 2 else 0.3
            )
        
        # 数牌
        number = int(tile[0]) if not is_red else int(tile[1])
        relations = []
        connected = []
        
        # 同種牌の枚数チェック
        count = self.tile_counts[tile]
        if count >= 2:
            relations.append(TileRelation.PAIR_CANDIDATE)
        
        # 同一スート内の他牌との連結チェック
        same_suit = [t for t in hand if t[-1] == suit and t != tile]
        other_numbers = []
        for t in same_suit:
            if 'r' in t:
                other_numbers.append(int(t[1]))
            else:
                other_numbers.append(int(t[0]))
        
        for other_num in set(other_numbers):
            pair = tuple(sorted([number, other_num]))
            if pair in self.RYANMEN_PATTERNS:
                relations.append(TileRelation.RYANMEN)
                connected.append(f"{other_num}{suit}")
            elif pair in self.KANCHAN_PATTERNS:
                relations.append(TileRelation.KANCHAN)
                connected.append(f"{other_num}{suit}")
            elif pair in self.EDGE_PATTERNS:
                relations.append(TileRelation.EDGE)
                connected.append(f"{other_num}{suit}")
        
        # 過剰形・複合形チェック
        if len(set(other_numbers)) >= 3:
            nums = sorted(set([number] + other_numbers))
            if self._is_overlap_shape(nums):
                relations.append(TileRelation.OVERLAP)
            if self._is_compound_shape(nums):
                relations.append(TileRelation.COMPOUND)
        
        # 形状安定度の計算
        stability = self._calc_shape_stability(relations, count)
        
        # 孤立牌の判定
        if not relations:
            relations.append(TileRelation.ISOLATED)
            stability = 0.2 if number in [1, 9] else 0.4
        
        return TileConnection(
            tile_id=tile, suit=suit, number=number, is_red=is_red,
            relations=relations, connected_tiles=connected,
            pair_count=count, shape_stability=stability
        )
    
    def _is_overlap_shape(self, numbers: List[int]) -> bool:
        """過剰形（4枚連続など）の判定"""
        if len(numbers) < 4:
            return False
        sorted_nums = sorted(numbers)
        for i in range(len(sorted_nums) - 3):
            if sorted_nums[i+3] - sorted_nums[i] == 3:
                return True
        return False
    
    def _is_compound_shape(self, numbers: List[int]) -> bool:
        """複合形（2つの形状が重なる）の判定"""
        if len(numbers) < 4:
            return False
        # 例: 2,3,4,5 → 234 + 345 の複合
        sorted_nums = sorted(numbers)
        for i in range(len(sorted_nums) - 3):
            if sorted_nums[i+2] - sorted_nums[i] == 2 and sorted_nums[i+3] - sorted_nums[i+1] == 2:
                return True
        return False
    
    def _calc_shape_stability(self, relations: List[TileRelation], count: int) -> float:
        """形状安定度の計算（0.0-1.0）"""
        if TileRelation.RYANMEN in relations:
            return 0.95
        elif TileRelation.COMPOUND in relations:
            return 0.90
        elif TileRelation.OVERLAP in relations:
            return 0.85
        elif TileRelation.KANCHAN in relations:
            return 0.70
        elif TileRelation.EDGE in relations:
            return 0.55
        elif TileRelation.PAIR_CANDIDATE in relations:
            return 0.65 if count == 2 else 0.95
        elif TileRelation.ISOLATED in relations:
            return 0.20
        return 0.50
