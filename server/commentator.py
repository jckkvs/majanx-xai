"""
ユーザー提案ベースの最小・最速の実働解説エンジン
"""
import numpy as np
from typing import List, Dict
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

from .engine import GameEngine
from .ai_reasoning import AIReasoningEngine

class CommentatorAI:
    def __init__(self, engine: 'GameEngine' = None):
        self.engine = engine
        self.shanten_calc = Shanten()
        self.reasoning = AIReasoningEngine()

    def _tile_to_34(self, tile) -> int:
        """Tileオブジェクト -> 0-33インデックス変換"""
        suit_to_idx = {"m": 0, "p": 1, "s": 2, "z": 3}
        suit_idx = suit_to_idx.get(tile.suit.value, 3)
        if suit_idx < 3:
            return suit_idx * 9 + tile.number - 1
        else:
            return 27 + tile.number - 1

    def _hand_to_34(self, hand: list) -> List[int]:
        """手牌リスト -> 34要素カウント配列に変換"""
        result = [0] * 34
        for tile in hand:
            idx = self._tile_to_34(tile)
            if 0 <= idx < 34:
                result[idx] += 1
        return result

    def analyze(self, seat: int, mortal_probs: np.ndarray = None) -> Dict:
        """
        現在のGameEngine状態からトップ3打牌候補と解説を返す
        """
        st = self.engine.state
        player = st.players[seat]
        
        # 34配列の作成（ローカルメソッドで変換）
        hand_34 = self._hand_to_34(player.hand)
        
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
            shanten_penalty = 0.001 if sh_after > current_shanten else 1.0
            attack = acceptance * (1.0 if sh_after <= 1 else 0.5) * shanten_penalty
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

        probs = [0.0] * 34
        q_values = [0.0] * 34
        top3_indices = []
        for x in candidates:
            probs[x["tile_idx"]] = x["prob"]
            # 簡易ルールベースの場合はattack_scoreなどをqの代わりに活用
            q_values[x["tile_idx"]] = x.get("balance_score", 0.0) / 10.0
            
        for t in mortal_top3:
            top3_indices.append(t["tile_idx"])

        board_state = round_info
        
        reasoning_data = self.reasoning.interpret(
            probs, q_values, board_state, top3_indices,
            is_mortal=(mortal_probs is not None),
            current_shanten=current_shanten
        )
        
        # 不要になった双視点解説文生成を削除し、AIReasoningEngineの出力を使用

        # フロントエンド用 choices 形式に変換（tile_name -> tile へマッピング）
        choices = [
            {"tile": c["tile_name"], "tile_name": c["tile_name"],
             "prob": c.get("prob", 0), "acceptance": c.get("acceptance", 0),
             "shanten": c.get("shanten", -1)}
            for c in mortal_top3
        ]

        return {
            # 汎用互換用
            "top3": mortal_top3,
            "explanation": reasoning_data["reasoning"],
            "current_shanten": current_shanten,
            
            # フロントエンド用（highlightRecommendedTiles が参照）
            "choices": choices,
            
            # 新しいAI推論データ (UIオーバーレイ用)
            "recommendation": self._idx_to_ja_name(mortal_top3[0]["tile_idx"]) if mortal_top3 else "",
            "reasoning": reasoning_data["reasoning"],
            "attack_score": reasoning_data.get("attack_score", 0),
            "defense_score": reasoning_data.get("defense_score", 0),
            "balance": reasoning_data.get("balance", ""),
            
            # 双視点用データ互換
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
        turn = round_info.get("turn") or 0
        phase = "序盤" if turn < 10 else "中盤" if turn < 25 else "終盤"
        
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
        return self._tile_to_34(tile)

    def _idx_to_name(self, idx: int) -> str:
        suits = ["m", "p", "s", "z"]
        if idx < 27:
            return f"{idx % 9 + 1}{suits[idx // 9]}"
        return f"{idx - 27 + 1}{suits[3]}"

    def _idx_to_ja_name(self, idx: int) -> str:
        nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]
        if idx < 9:
            return f"{nums[idx]}萬"
        elif idx < 18:
            return f"{nums[idx - 9]}筒"
        elif idx < 27:
            return f"{nums[idx - 18]}索"
        else:
            z_names = ["東", "南", "西", "北", "白", "發", "中"]
            return z_names[idx - 27]
