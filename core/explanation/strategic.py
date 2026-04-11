# core/explanation/strategic.py
from typing import Dict, List
from .models import StrategicFactor

class StrategicAnalyzer:
    def analyze(self, context: Dict) -> List[StrategicFactor]:
        factors = []
        is_dealer = context.get("is_dealer", False)
        round_name = context.get("round", "東1")
        score_diff = context.get("score_diff", 0)
        riichi_count = context.get("riichi_opponents", 0)
        turn_count = context.get("turn_count", 0)

        # 親番判断
        if is_dealer:
            factors.append(StrategicFactor(
                code="oya_advantage", label="親番・連荘意識",
                context=f"{round_name}局・親", priority=0.8
            ))

        # リーチ対応
        if riichi_count > 0:
            priority = 0.9 if riichi_count >= 2 else 0.7
            factors.append(StrategicFactor(
                code="riichi_defense", label="リーチ対応・安全牌優先",
                context=f"対面{riichi_count}人リーチ", priority=priority
            ))

        # 点差状況
        if score_diff < -15000:
            factors.append(StrategicFactor(
                code="desperation_attack", label="トップ離れ・攻め転換",
                context=f"点差 {score_diff}・逆転狙い", priority=0.85
            ))
        elif score_diff > 15000:
            factors.append(StrategicFactor(
                code="top_defense", label="トップ維持・ベタ降り傾向",
                context=f"点差 {score_diff}・逃げ切り優先", priority=0.9
            ))

        # 巡目判断
        if turn_count > 15:
            factors.append(StrategicFactor(
                code="late_game_risk", label="終盤・危険牌回避",
                context=f"{turn_count}巡目・後手注意", priority=0.75
            ))

        # デフォルト（状況特異性なし）
        if not factors:
            factors.append(StrategicFactor(
                code="standard_flow", label="標準手牌進行",
                context="特段の状況変化なし", priority=0.5
            ))

        return sorted(factors, key=lambda x: x.priority, reverse=True)
