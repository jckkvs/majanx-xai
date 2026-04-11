from typing import List, Dict, Set, Tuple
from itertools import combinations

class ShantenEngine:
    """向聴数・受入枚数 完全計算"""
    
    @classmethod
    def calc(cls, tiles_34: List[int]) -> Tuple[int, List[int]]:
        """
        tiles_34: 34種の牌枚数 [0..4]
        returns: (向聴数, 受け入れ牌インデックスリスト)
        """
        best_shanten = 8
        best_ukeire_indices = []
        
        for i in range(34):
            if tiles_34[i] < 4:
                tiles_34[i] += 1
                sh = cls._shanten_recursive(tiles_34, 0, 0, 0)
                if sh < best_shanten:
                    best_shanten = sh
                    best_ukeire_indices = [i]
                elif sh == best_shanten:
                    best_ukeire_indices.append(i)
                tiles_34[i] -= 1
                
        return best_shanten + 1, best_ukeire_indices

    @classmethod
    def _shanten_recursive(cls, tiles: List[int], mentsu: int, taatsu: int, idx: int) -> int:
        """標準的な分割探索アルゴリズム"""
        if idx >= 34:
            # Janto check would normally be separate, 
            # but user provided this specific recursive Logic.
            remaining = sum(tiles)
            needed = 4 - mentsu
            return max(0, needed * 2 - taatsu - 1) if remaining > 0 else 8 - mentsu * 2 - taatsu
            
        count = tiles[idx]
        if count == 0:
            return cls._shanten_recursive(tiles, mentsu, taatsu, idx + 1)
            
        best = cls._shanten_recursive(tiles, mentsu, taatsu, idx + 1)
        
        # 刻子抽出
        if count >= 3:
            tiles[idx] -= 3
            best = min(best, cls._shanten_recursive(tiles, mentsu + 1, taatsu, idx))
            tiles[idx] += 3
            
        # 対子抽出
        if count >= 2:
            tiles[idx] -= 2
            best = min(best, cls._shanten_recursive(tiles, mentsu, taatsu + 1, idx))
            tiles[idx] += 2
            
        # 順子抽出 (数牌のみ)
        suit = idx // 9
        num = idx % 9
        if suit < 3 and num < 7:
            if tiles[idx+1] > 0 and tiles[idx+2] > 0:
                tiles[idx] -= 1; tiles[idx+1] -= 1; tiles[idx+2] -= 1
                best = min(best, cls._shanten_recursive(tiles, mentsu + 1, taatsu, idx))
                tiles[idx] += 1; tiles[idx+1] += 1; tiles[idx+2] += 1
                
        return best

class DefenseAnalyzer:
    """放銃リスク評価"""
    @staticmethod
    def assess(tile_idx: int, visible: Dict[str, int], riichi_players: Set[int], turn: int) -> float:
        """0.0(安全)〜1.0(危険)"""
        if visible.get(str(tile_idx), 0) >= 4: return 0.0
        if not riichi_players: return 0.15
        
        risk = 0.35
        if turn > 8: risk += 0.2
        if 1 <= (tile_idx % 9) + 1 <= 8 and (tile_idx // 9) < 3:
            risk += 0.15 # 中張牌
        return min(1.0, risk)

class MahjongBrain:
    @classmethod
    def evaluate_discard(cls, hand_34: List[int], river_data: Dict, opponents: List[Dict]) -> Dict:
        candidates = []
        for i in range(34):
            if hand_34[i] == 0: continue
            hand_34[i] -= 1
            sh, ukeire = ShantenEngine.calc(hand_34)
            risk = DefenseAnalyzer.assess(i, river_data, {o["id"] for o in opponents if o.get("riichi")}, river_data.get("turn", 1))
            
            attack_val = sum(1 for _ in ukeire) * (1.0 / (sh + 1))
            defense_val = (1.0 - risk) * 5.0
            
            candidates.append({"tile_idx": i, "attack": attack_val, "defense": defense_val, "total": attack_val + defense_val})
            hand_34[i] += 1
            
        return max(candidates, key=lambda x: x["total"])
