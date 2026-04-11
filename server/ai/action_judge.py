from typing import List, Dict

class ActionJudge:
    @staticmethod
    def should_call(hand_shanten: int, post_shanten: int, call_type: str, loses_yaku: bool) -> bool:
        """鳴き可否判定"""
        if post_shanten >= hand_shanten: return False
        if loses_yaku and call_type in ("chi", "pon"): return False
        return True

    @staticmethod
    def riichi_vs_dama(win_prob: float, avg_score: float, deal_in_prob: float, 
                       is_riichi_safe: bool, turn: int) -> str:
        """リーチ/ダマ期待値比較"""
        prob_r = min(0.85, win_prob * 1.35)
        risk_r = deal_in_prob + (0.15 if is_riichi_safe else 0.35)
        ev_r = prob_r * (avg_score + 1000) - risk_r * 8000
        ev_d = win_prob * avg_score - deal_in_prob * 6000
        
        # 終盤補正: 10巡以降はダマ安全牌維持を優先
        if turn >= 10 and deal_in_prob > 0.25:
            ev_d += 500
            ev_r -= 300
            
        return "riichi" if ev_r > ev_d + 500 else "dama"
