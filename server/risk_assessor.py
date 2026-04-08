"""
他家の手牌推定と危険度マップ生成モジュール
"""
from typing import Dict, List, Any

class RiskAssessor:
    """他家の手牌推定と危険度マップ生成"""
    
    # 萬子、筒子、索子、字牌の全34種
    ALL_TILES = [f"{n}{s}" for s in "mps" for n in range(1, 10)] + [f"{n}z" for n in range(1, 8)]

    def assess_risk(self, gs: Any) -> Dict[str, float]:
        """全プレイヤー、全牌の危険度を計算して返す"""
        risk_map = {}
        
        for tile_id in self.ALL_TILES:
            max_danger = 0.0
            
            for opponent in gs.players:
                if opponent.seat == gs.current_player:
                    continue  # 自分は除外
                    
                # 1. 現物・スジなどの基本防御力計算
                basic_safety = self._calc_basic_safety(tile_id, opponent)
                
                # 2. 捨て牌時系列からの読み（ベイズ更新）
                seq_likelihood = self._analyze_discard_sequence(tile_id, opponent)
                
                # 3. テンパイ確率による重み付け
                tenpai_prob = self._estimate_tenpai_prob(opponent, gs.turn_count)
                
                # 最終危険度 = (1 - 基本防御力) * 時系列尤度 * テンパイ確率
                danger = (1.0 - basic_safety) * seq_likelihood * tenpai_prob
                max_danger = max(max_danger, danger)
            
            risk_map[tile_id] = max_danger
            
        return risk_map

    def _calc_basic_safety(self, tile_id: str, opponent: Any) -> float:
        """現物やスジに基づく基本安全度 (0.0=絶対危険, 1.0=完全安全)"""
        # 現物判定
        discard_ids = [t.id.replace('r', '') for t in opponent.discards]
        base_id = tile_id.replace('r', '')
        if base_id in discard_ids:
            return 1.0  # 現物
            
        # 簡易な字牌安全度
        if 'z' in base_id:
            # 場に見えている数で安全度を変えるなど
            return 0.5
            
        # スジ判定（簡易版）
        num = int(base_id[0])
        suit = base_id[1]
        is_suji = False
        if num <= 3 and f"{num+3}{suit}" in discard_ids:
            is_suji = True
        elif num >= 7 and f"{num-3}{suit}" in discard_ids:
            is_suji = True
        elif 4 <= num <= 6 and f"{num-3}{suit}" in discard_ids and f"{num+3}{suit}" in discard_ids:
            is_suji = True
            
        if is_suji:
            return 0.7  # スジは比較的安全
            
        return 0.1  # 無筋

    def _analyze_discard_sequence(self, tile_id: str, opponent: Any) -> float:
        """時系列による尤度（危険性の高まり具合を調整）"""
        # 単純化: 1.0を返す
        return 1.0

    def _estimate_tenpai_prob(self, player: Any, turn: int) -> float:
        """
        ベイズ的アプローチによるテンパイ確率推定
        """
        priors = {
            'early': 0.1,  # 1-4巡
            'mid': 0.35,   # 5-8巡
            'late': 0.70,  # 9-12巡
            'end': 0.90    # 13巡〜
        }
        
        phase = 'early' if turn < 5 else 'mid' if turn < 9 else 'late' if turn < 13 else 'end'
        prob = priors[phase]
        
        if player.is_riichi:
            prob = 0.98 # リーチ宣言済みならほぼ確定
        elif len(player.melds) > 0:
            prob += 0.15 # 鳴きがあるなら速度が出ている可能性大
            
        return max(0.05, min(0.99, prob))
