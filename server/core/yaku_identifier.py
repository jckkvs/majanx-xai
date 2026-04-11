from typing import List, Dict, Optional, Tuple
from .score_calculator import ScoreCalculator

class YakuIdentifier:
    """手牌から役・飜・符を特定するエンジン"""
    
    YAKU_HAN = {
        "Riichi": 1, "Tanyao": 1, "Pinfu": 1, "Iippeku": 1, 
        "Yakuhai": 1, "Honitsu": 3, "Chinitsu": 6
    }

    @classmethod
    def identify(cls, hand_34: List[int], melds: List[Dict], is_menzen: bool,
                 is_ron: bool, is_riichi: bool, dora_count: int,
                 bakaze: int, jikaze: int) -> Tuple[int, int, List[str]]:
        """
        returns: (han, fu, yaku_names)
        """
        han = dora_count
        yaku_names = []
        if is_riichi:
            han += 1
            yaku_names.append("Riichi")
            
        # 簡易判定: 断幺九
        if cls._is_tanyao(hand_34, melds):
            han += 1
            yaku_names.append("Tanyao")
            
        # 役牌 (白發中, 場風, 自風)
        yakuhai_count = cls._count_yakuhai(hand_34, melds, bakaze, jikaze)
        if yakuhai_count > 0:
            han += yakuhai_count
            for _ in range(yakuhai_count): yaku_names.append("Yakuhai")
            
        # 符計算
        fu = 30
        if not is_menzen and not is_ron: # Tsumo non-menzen
            fu = 20
        elif is_menzen and not is_ron: # Pinfu Tsumo check would go here
            fu = 20
        
        # 翻数不足チェック (1役以上必要)
        if han <= dora_count and not yaku_names:
            return 0, 0, []
            
        return han, fu, yaku_names

    @staticmethod
    def _is_tanyao(hand_34: List[int], melds: List[Dict]) -> bool:
        # 字牌(27-33) check
        for i in range(27, 34):
            if hand_34[i] > 0: return False
        # 端牌 (1, 9) check
        for suit in range(3):
            if hand_34[suit*9] > 0 or hand_34[suit*9 + 8] > 0: return False
        return True

    @staticmethod
    def _count_yakuhai(hand_34: List[int], melds: List[Dict], bakaze: int, jikaze: int) -> int:
        count = 0
        # 三元牌 (31, 32, 33) -> 白發中
        for i in [31, 32, 33]:
            if hand_34[i] >= 3: count += 1
        # 場風・自風
        if hand_34[27 + bakaze] >= 3: count += 1
        if hand_34[27 + jikaze] >= 3: count += 1 # ダブ東などは2役になるはずだが簡易化
        return count
