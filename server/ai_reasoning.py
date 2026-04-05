from typing import List, Dict

class AIReasoningEngine:
    """Mortal/ルールAIの出力を戦略言語に翻訳"""
    
    STRATEGY_MAP = {
        "efficiency": "牌効率最適化",
        "value": "打点・順位最大化",
        "defense": "守備転換・危険回避",
        "balance": "攻守バランス調整",
        "evolution": "手変わり・多面待ち創出"
    }

    def interpret(self, probs: List[float], q_values: List[float], 
                  board_state: Dict, top3_indices: List[int], is_mortal: bool = False, current_shanten: int = -1) -> Dict:
        """
        確率分布・期待値・盤面から判断根拠を生成し、双視点データを含む辞書を返す。
        """
        if not top3_indices:
            return {"strategy": "", "reasoning": "判定不可", "attack_score": 0.0, "defense_score": 0.0, "balance": "不明"}
            
        best_idx = top3_indices[0]
        second_idx = top3_indices[1] if len(top3_indices) > 1 else best_idx
        
        # 数値差分計算
        prob_diff = probs[best_idx] - probs[second_idx]
        q_diff = q_values[best_idx] - q_values[second_idx]
        best_q = q_values[best_idx]
        best_prob = probs[best_idx]

        # 1. 主要戦略の特定
        strategy = self._detect_strategy(prob_diff, q_diff, board_state, is_mortal)
        
        # 2. 場況コンテキスト抽出
        context = self._extract_context(board_state)
        
        # 3. 根拠文構築
        primary = f"【AI判断】{strategy}を優先。"
        data = f"確率差{prob_diff:.1%}、期待値{best_q:+.1f}。"
        context_str = f"場況({'・'.join(context)})を考慮し、" if context else ""
        
        # 4. 次点比較による補強
        comparison = "次点との比較で明確な優位性があるため、この打牌を推奨。"
        if prob_diff < 0.05 and q_diff < 0.2:
            comparison = "僅差だが、場況適応力で上回ると判断。"

        reasoning_text = f"{primary}{context_str}{data}{comparison}"

        # 5. 攻守計算 (Mortalからの出力がない場合のフォールバック用)
        attack_score = best_prob * 10 + max(0, best_q)
        if board_state.get("turn", 0) < 10: attack_score *= 1.2
        defense_score = 1.0 - best_prob
        if board_state.get("is_riichi", False): defense_score *= 2.0
        
        balance_str = "攻め" if attack_score > defense_score * 1.3 else "守り" if defense_score > attack_score * 1.3 else "バランス"

        return {
            "strategy": strategy,
            "reasoning": reasoning_text,
            "attack_score": round(attack_score, 1),
            "defense_score": round(defense_score, 2),
            "balance": balance_str
        }

    def _detect_strategy(self, prob_diff: float, q_diff: float, state: Dict, is_mortal: bool) -> str:
        if not is_mortal:
            return "牌効率最適化（ルールベース）"
            
        if prob_diff > 0.15:
            return self.STRATEGY_MAP["efficiency"]
        if q_diff > 0.5:
            return self.STRATEGY_MAP["value"]
        if state.get("is_riichi") and q_diff < 0.1:
            return self.STRATEGY_MAP["defense"]
        if state.get("turn", 0) > 20 and q_diff > 0.2:
            return self.STRATEGY_MAP["evolution"]
        return self.STRATEGY_MAP["balance"]

    def _extract_context(self, state: Dict) -> List[str]:
        ctx = []
        if state.get("turn", 0) > 25: ctx.append("終盤")
        elif state.get("turn", 0) > 12: ctx.append("中盤")
        else: ctx.append("序盤")
        
        if state.get("is_riichi"): ctx.append("他家リーチ")
        if state.get("my_rank", 1) == 1: ctx.append("トップ維持")
        elif state.get("my_rank", 1) >= 3: ctx.append("逆転局面")
        if state.get("dora_count", 0) >= 2: ctx.append("高打点環境")
        return ctx
