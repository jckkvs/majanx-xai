# core/explanation/technical.py
from typing import List
from mahjong.shanten import Shanten
from .models import TechnicalFactor

class TechnicalAnalyzer:
    def __init__(self):
        self.shanten_calc = Shanten()

    @staticmethod
    def tiles_to_34(tiles: List[str]) -> List[int]:
        """手牌リスト → 34種カウント配列変換"""
        arr = [0] * 34
        suit_map = {'m': 0, 'p': 9, 's': 18, 'z': 27}
        for t in tiles:
            if len(t) < 2: continue
            num, suit = int(t[0]), t[1]
            if suit in suit_map:
                arr[suit_map[suit] + num - 1] += 1
        return arr

    def analyze(self, hand_before: List[str], hand_after: List[str], discarded: str) -> List[TechnicalFactor]:
        factors = []
        
        # 1. 向聴数変化
        shanten_b = self.shanten_calc.calculate_shanten(self.tiles_to_34(hand_before))
        shanten_a = self.shanten_calc.calculate_shanten(self.tiles_to_34(hand_after))
        diff = shanten_b - shanten_a
        
        if diff > 0:
            factors.append(TechnicalFactor(
                code="shanten_down", label="向聴数前進", value=float(diff),
                detail=f"向聴数 {shanten_b}→{shanten_a} に改善"
            ))
        elif diff == 0:
            factors.append(TechnicalFactor(
                code="shanten_keep", label="向聴数維持", value=0.0,
                detail="手牌の形を崩さず進行"
            ))
        else:
            factors.append(TechnicalFactor(
                code="shanten_downgrade", label="向聴数後退", value=float(diff),
                detail="一時的な後退だが後続の受け入れを拡大"
            ))

        # 2. 手牌効率（簡易受け入れ枚数評価）
        # ※ MVPではAIスコア差を間接指標として使用。詳細算出は拡張ポイント。
        factors.append(TechnicalFactor(
            code="efficiency", label="手牌効率最適化", value=None,
            detail="待ちの広さ・複合形維持を優先"
        ))

        return factors
