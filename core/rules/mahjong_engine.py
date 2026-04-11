# core/rules/mahjong_engine.py
from mahjong.shanten import Shanten
from mahjong.agari import Agari
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.meld import Meld
from typing import List, Dict, Optional
import re

class MahjongRuleEngine:
    """mahjong(PyPI)をラップしたルール判定エンジン"""
    
    def __init__(self):
        self.shanten_calc = Shanten()
        self.agari_check = Agari()
        self.hand_calc = HandCalculator()

    @staticmethod
    def tile_to_34_index(tile: str) -> int:
        """'1m'→0, '9m'→8, '1p'→9 ... '7z'→33 に変換"""
        m = re.match(r"([1-9])([mpsz])", tile)
        if not m: raise ValueError(f"Invalid tile format: {tile}")
        num, suit = m.groups()
        base = {'m': 0, 'p': 9, 's': 18, 'z': 27}[suit]
        return base + int(num) - 1

    def tiles_to_34_array(self, tiles: List[str]) -> List[int]:
        arr = [0] * 34
        for t in tiles:
            idx = self.tile_to_34_index(t)
            arr[idx] += 1
        return arr

    def get_shanten(self, hand_tiles: List[str]) -> int:
        """向聴数計算（-1: 聴牌）"""
        arr = self.tiles_to_34_array(hand_tiles)
        return self.shanten_calc.calculate_shanten(arr)

    def check_agari(self, hand_tiles: List[str], melds: Optional[List[Meld]] = None) -> bool:
        """アガリ判定"""
        arr = self.tiles_to_34_array(hand_tiles)
        return self.agari_check.is_agari(arr, melds or [])

    def calculate_win_info(self, hand_tiles: List[str], melds: Optional[List[Meld]] = None,
                           is_tsumo: bool = False, field_wind: int = 0, seat_wind: int = 0) -> Dict:
        """役・翻数・符計算（MVP簡易版）"""
        if not self.check_agari(hand_tiles, melds):
            return {"is_win": False, "reason": "Not a winning shape"}
        
        # TODO: 完全な役判定・点数計算は Priority 2 で詳細化
        return {"is_win": True, "shanten": -1, "score_placeholder": True}
