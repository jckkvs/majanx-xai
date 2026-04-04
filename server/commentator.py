"""
ユーザー提案ベースの最小・最速の実働解説エンジン
"""
import numpy as np
from typing import List, Dict
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

from .engine import GameEngine


class CommentatorAI:
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.shanten_calc = Shanten()

    def analyze(self, seat: int, mortal_probs: np.ndarray = None) -> Dict:
        """
        現在のGameEngine状態からトップ3打牌候補と解説を返す
        """
        st = self.engine.state
        player = st.players[seat]
        
        # 34配列の作成
        hand_34 = self.engine._hand_to_34(player.hand)
        
        # ツモ牌の切り出し(最後がツモ牌と仮定)
        # ※既に手牌に組み込まれているため、別途結合の必要なし
        full_34 = hand_34.copy()
        
        # 見えている牌の集計
        visible_34 = [0] * 34
        for p in self.engine.state.players:
            for d in p.discards:
                idx = self._tile_obj_to_34(d)
                visible_34[idx] += 1
            for m in p.melds:
                for t in m.tiles:
                    idx = self._tile_obj_to_34(t)
                    visible_34[idx] += 1

        round_info = {
            "turn": st.turn_count,
            "is_riichi": any(p.is_riichi for p in st.players if p.seat != seat)
        }

        if sum(full_34) == 0:
            return {"top3": [], "explanation": "判定不可", "current_shanten": -1}

        candidates = []
        current_shanten = self.shanten_calc.calculate_shanten(full_34)

        for i in range(34):
            if full_34[i] == 0: continue
            
            # 打牌シミュレーション
            sim_34 = full_34.copy()
            sim_34[i] -= 1
            
            sh_after = self.shanten_calc.calculate_shanten(sim_34)
            acceptance = self._count_acceptance(sim_34, sh_after)
            danger = self._estimate_danger(i, visible_34, round_info)

            # 攻守スコア計算
            attack = acceptance * (1.0 if sh_after <= 1 else 0.5) * (1.5 if sh_after < current_shanten else 1.0)
            defense = max(0.1, 1.0 - danger)
            balance = attack * defense  # 攻守最適化指標

            prob = float(mortal_probs[i]) if mortal_probs is not None else 0.0

            candidates.append({
                "tile_idx": i,
                "tile_name": self._idx_to_name(i),
                "shanten": sh_after,
                "acceptance": acceptance,
                "attack_score": round(attack, 1),
                "defense_score": round(defense, 2),
                "balance_score": round(balance, 1),
                "prob": round(prob, 3)
            })

        # ルールベース上位3位
        candidates.sort(key=lambda x: x["balance_score"], reverse=True)
        rule_top3 = candidates[:3]

        if not rule_top3:
            return {"top3": [], "explanation": "判定不可", "current_shanten": -1}

        # Mortal（確率）上位3位
        candidates.sort(key=lambda x: x["prob"], reverse=True)
        mortal_top3 = candidates[:3]

        # 双視点解説文生成
        explanation_data = self._generate_dual_commentary(mortal_top3, rule_top3, round_info)

        return {
            # 汎用互換用
            "top3": mortal_top3,
            "explanation": explanation_data["synthesis"],
            "current_shanten": current_shanten,
            
            # 双視点用データ
            "recommendation": mortal_top3[0]["tile_name"],
            "agreement": explanation_data["is_agree"],
            "mortal_view": explanation_data["mortal_view"],
            "rule_view": explanation_data["rule_view"],
            "synthesis": explanation_data["synthesis"],
            "mortal_top3": mortal_top3,
            "rule_top3": rule_top3,
        }

    def _count_acceptance(self, hand_34: List[int], target_shanten: int) -> int:
        """受入枚数計算（34牌総当たり）"""
        count = 0
        for i in range(34):
            if hand_34[i] >= 4: continue
            sim = hand_34.copy()
            sim[i] += 1
            if self.shanten_calc.calculate_shanten(sim) < target_shanten:
                count += (4 - hand_34[i])
        return count

    def _estimate_danger(self, tile_idx: int, visible_34: List[int], round_info: Dict) -> float:
        """簡易危険度推定"""
        if not round_info.get("is_riichi", False):
            return 0.15
        if visible_34[tile_idx] >= 3: return 0.05
        suit = tile_idx // 9
        num = tile_idx % 9 + 1
        danger = 0.4
        if suit == 3:
            if visible_34[tile_idx] == 0: danger = 0.8
        else:
            if num in [2, 5, 8]: danger = 0.7
            elif num in [3, 6, 9]: danger = 0.5
        return min(danger, 0.95)

    def _generate_dual_commentary(self, mortal_top3: List[Dict], rule_top3: List[Dict], round_info: Dict) -> Dict:
        """Mortal推論結果と独自ルールの推論結果を比較し、双視点解説を生成"""
        mort = mortal_top3[0]
        rule = rule_top3[0]
        is_agree = mort["tile_idx"] == rule["tile_idx"]

        # 1. 確率・期待値視点 (Mortal)
        prob = mort["prob"]
        m_stance = "牌効率最適" if prob > 0.6 else "攻守バランス"
        mortal_view = f"[AI学習視点] 確率{prob:.1%}で最有力。{m_stance}。"

        # 2. 牌効率・攻守視点 (Rule)
        t = rule
        rule_view = f"[牌効率・攻守視点] 受入{t['acceptance']}枚、放銃リスク{round(1-t['defense_score'],2)}。"
        if t['attack_score'] > t['defense_score'] * 1.5:
            rule_view += f"テンパイ確率向上が明確。"
        elif t['defense_score'] > t['attack_score'] * 1.5:
            rule_view += f"危険牌回避が優先。"
        else:
            rule_view += f"受入確保と危険度抑制の交差点。"

        # 3. 統合(Synthesis)
        phase = "序盤" if round_info.get("turn") < 10 else "中盤" if round_info.get("turn") < 25 else "終盤"
        
        if is_agree:
            synthesis = f"✅ 両視点一致（{phase}）\nAIの期待値最適と、牌効率・攻守バランスの論理的根拠が揃っているため、自信度高く「{mort['tile_name']}」切りを推奨。"
        else:
            reason = "AIは他家の捨牌パターン・ドラ分布・順位状況を考慮した期待値最適を出力。"
            if phase in ["中盤", "終盤"]:
                reason += "終盤では牌効率より「打点差/放銃ペナルティ」の重みが増すため、AI判断が優先される傾向あり。"
            else:
                reason += "序盤はAIが長期的な手変わり・副露誘導を評価している可能性あり。"
                
            synthesis = f"⚠️ 視点のズレ（{phase}）\nAI:「{mort['tile_name']}」 / ルール:「{rule['tile_name']}」\n{reason}"

        return {
            "is_agree": is_agree,
            "mortal_view": mortal_view,
            "rule_view": rule_view,
            "synthesis": synthesis
        }

    def _tile_obj_to_34(self, tile) -> int:
        return tile.suit.value * 9 + tile.number - 1 if tile.suit.value < 3 else 27 + tile.number - 1

    def _idx_to_name(self, idx: int) -> str:
        suits = ["m", "p", "s", "z"]
        if idx < 27:
            return f"{idx % 9 + 1}{suits[idx // 9]}"
        return f"{idx - 27 + 1}{suits[3]}"
