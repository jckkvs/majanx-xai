import math
from typing import Dict, Tuple

class ScoreCalculator:
    """符・飜・本場・供託・オカウマを厳密に計算するエンジン"""
    
    OMA = {1: 12000, 2: 4000, 3: -4000, 4: -12000}  # 千点単位 (3-1ウマ)
    OKA = 30000                                       # 3万オカ
    HONBA_PER = 300
    RIICHI_STICK = 1000

    @classmethod
    def calc(cls, han: int, fu: int, is_dealer: bool, is_ron: bool,
             honba: int, riichi_sticks: int, player_ranks: Dict[int, int]) -> Dict:
        """和了時の点数分配を計算"""
        bp = cls._base_points(han, fu)
        if is_ron:
            ron_pts = (bp * 6 if is_dealer else bp * 4) + (honba * cls.HONBA_PER)
            ron_pts = math.ceil(ron_pts / 100) * 100
            return {
                "winner_gain": ron_pts + (riichi_sticks * cls.RIICHI_STICK),
                "loser_loss": ron_pts,
                "type": "ron"
            }
        else: # ツモ
            if is_dealer:
                each = (bp * 2) + (honba * 100)
                # each is already rounded at base_points level if limit, 
                # but tsumo payments are rounded up to nearest 100.
                each = math.ceil(each / 100) * 100
                return {
                    "winner_gain": (each * 3) + (riichi_sticks * cls.RIICHI_STICK),
                    "non_dealer_loss": each,
                    "type": "tsumo_dealer"
                }
            else:
                dealer_pay = (bp * 2) + (honba * 100)
                other_pay = bp + (honba * 100)
                dealer_pay = math.ceil(dealer_pay / 100) * 100
                other_pay = math.ceil(other_pay / 100) * 100
                return {
                    "winner_gain": dealer_pay + (other_pay * 2) + (riichi_sticks * cls.RIICHI_STICK),
                    "dealer_loss": dealer_pay,
                    "other_loss": other_pay,
                    "type": "tsumo_non_dealer"
                }

    @staticmethod
    def _base_points(han: int, fu: int) -> int:
        """基本点計算 (切り上げ満貫・役満上限対応)"""
        # Yakuman check
        if han >= 13: return 8000
        if han >= 11: return 6000
        if han >= 8: return 4000
        if han >= 6: return 3000
        if han >= 5: return 2000
        
        pts = fu * (2 ** (2 + han))
        # Kiriage mangan check (approx 2000 base points)
        if pts >= 1920: return 2000
        return pts

    @classmethod
    def apply_point_calculation(cls, bp: int, is_dealer: bool, is_ron: bool) -> int:
        """Calculate final payout from base points"""
        if is_ron:
            return math.ceil((bp * (6 if is_dealer else 4)) / 100) * 100
        return bp # For tsumo, individual payments are handled in calc()

    @classmethod
    def apply_uma_oka(cls, final_scores: Dict[int, int]) -> Dict[int, int]:
        """終局時のオカ・ウマ適用"""
        ranks = sorted(final_scores.keys(), key=lambda p: final_scores[p], reverse=True)
        adjustments = {r: cls.OMA.get(i + 1, 0) for i, r in enumerate(ranks)}
        adjustments[ranks[0]] += cls.OKA
        return {p: final_scores[p] + adjustments[p] for p in final_scores}
