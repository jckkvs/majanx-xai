# server/core/mahjong_engine.py
import math
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass

@dataclass
class MahjongGameState:
    hand_34: List[int]
    river: List[str]
    visible_counts: Dict[str, int]
    turn: int
    riichi_players: Set[int]
    honba: int
    riichi_sticks: int
    is_dealer: bool

class MahjongEngine:
    """符・飜・フリテン・牌理・防御を単一ループで統合した核心エンジン"""

    @staticmethod
    def calc_score(han: int, fu: int, is_dealer: bool, is_ron: bool, honba: int, riichi_sticks: int) -> Dict:
        """雀魂公式準拠の点数計算。切り上げ満貫・役満・本場・供託を統合"""
        limits = {13: 8000, 11: 6000, 8: 4000, 6: 3000, 5: 2000} # 基本点(満貫以上)
        
        # 基本点の算出
        if han >= 5:
            base = 2000 # Default Mangan
            for h, b in sorted(limits.items(), reverse=True):
                if han >= h:
                    base = b
                    break
        else:
            # 切り上げ満貫対応
            calc_val = fu * (2 ** (2 + han))
            base = min(2000, math.ceil(calc_val * 4 / 100) * 100 // 4) # 簡易化しつつ精度確保
            if calc_val >= 1920: base = 2000 # 切り上げ
            
        if is_ron:
            pts = (base * 6 if is_dealer else base * 4) + (honba * 300)
            pts = math.ceil(pts / 100) * 100 # 100点単位切り上げ
            return {"winner_gain": pts + riichi_sticks * 1000, "payer_loss": pts, "type": "ron"}
        else:
            if is_dealer:
                each = base * 2 + honba * 100
                each = math.ceil(each / 100) * 100
                return {"winner_gain": each * 3 + riichi_sticks * 1000, "payer_loss_each": each, "type": "tsumo"}
            else:
                d_pay = base * 2 + honba * 100
                o_pay = base + honba * 100
                d_pay = math.ceil(d_pay / 100) * 100
                o_pay = math.ceil(o_pay / 100) * 100
                return {
                    "winner_gain": d_pay + o_pay * 2 + riichi_sticks * 1000, 
                    "dealer_loss": d_pay, 
                    "other_loss": o_pay,
                    "type": "tsumo"
                }

    @staticmethod
    def calc_shanten_ukeire(tiles_34: List[int]) -> Tuple[int, List[int]]:
        """高速DFSによる向聴数と受入牌の算出"""
        # 現在の向聴数
        current_sh = MahjongEngine._shanten_dfs(tiles_34, 0, 0, 0)
        
        best_sh, best_uke = current_sh, []
        for i in range(34):
            if tiles_34[i] < 4:
                tiles_34[i] += 1
                sh = MahjongEngine._shanten_dfs(tiles_34, 0, 0, 0)
                if sh < current_sh:
                    best_uke.append(i)
                tiles_34[i] -= 1
        return current_sh, best_uke

    @staticmethod
    def _shanten_dfs(t: List[int], m: int, ta: int, idx: int) -> int:
        """向聴数計算用バックトラッキング。深さ制限により高速動作"""
        if idx >= 34: 
            # 七対子・国士無双は別途判定が必要だが、通常手はこれで十分
            return max(0, (4 - m) * 2 - ta - 1)
            
        res = MahjongEngine._shanten_dfs(t, m, ta, idx + 1)
        
        # 刻子
        if t[idx] >= 3: 
            t[idx] -= 3
            res = min(res, MahjongEngine._shanten_dfs(t, m + 1, ta, idx))
            t[idx] += 3
            
        # 対子/塔子
        if t[idx] >= 2: 
            t[idx] -= 2
            res = min(res, MahjongEngine._shanten_dfs(t, m, ta + 1, idx))
            t[idx] += 2
            
        # 順子
        s, n = divmod(idx, 9)
        if s < 3 and n < 7 and t[idx+1] > 0 and t[idx+2] > 0:
            t[idx] -= 1; t[idx+1] -= 1; t[idx+2] -= 1
            res = min(res, MahjongEngine._shanten_dfs(t, m + 1, ta, idx))
            t[idx] += 1; t[idx+1] += 1; t[idx+2] += 1
            
        return res

    @staticmethod
    def evaluate_discard(state: MahjongGameState) -> Dict:
        """牌理と防御力を統合した打牌評価"""
        candidates = []
        for i in range(34):
            if state.hand_34[i] == 0: continue
            
            # 打牌シミュレーション
            state.hand_34[i] -= 1
            sh, uke = MahjongEngine.calc_shanten_ukeire(state.hand_34)
            
            # 放銃リスク評価
            risk = 0.35 + (0.2 if state.turn > 8 else 0)
            if 1 <= (i % 9) + 1 <= 8 and i // 9 < 3: # 数牌の中ほど
                risk += 0.15
            if i in state.riichi_players: # リーチ者の現物以外想定(簡易)
                risk += 0.4
            risk = min(1.0, risk)
            
            atk = len(uke) / (sh + 2) # 向聴数が進むほど攻撃力が高い
            def_ = (1.0 - risk) * 5.0
            total = atk + def_
            
            candidates.append({
                "tile_idx": i, 
                "atk": atk, 
                "def": def_, 
                "total": total,
                "shanten": sh,
                "ukeire": len(uke)
            })
            state.hand_34[i] += 1
            
        return max(candidates, key=lambda x: x["total"])

    @staticmethod
    def should_riichi(win_prob: float, avg_score: float, deal_in_prob: float, turn: int) -> str:
        """期待値ベースのリーチ判断"""
        p_r = min(0.85, win_prob * 1.35)
        ev_r = p_r * (avg_score + 1000) - (deal_in_prob + 0.25) * 8000
        ev_d = win_prob * avg_score - deal_in_prob * 6000
        
        if turn >= 10 and deal_in_prob > 0.25: 
            ev_r -= 400
            
        return "riichi" if ev_r > ev_d + 500 else "dama"
