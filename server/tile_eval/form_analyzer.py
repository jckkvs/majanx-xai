"""
形勢判断モジュール
点数差・順位・残り局数から攻守度（0.0=完全守勢, 1.0=完全攻勢）を算出
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class FormScore:
    """形勢スコア"""
    aggression: float    # 攻勢度 (0.0=守勢, 1.0=攻勢)
    reasoning: str

    @property
    def is_aggressive(self) -> bool:
        return self.aggression >= 0.6

    @property
    def is_defensive(self) -> bool:
        return self.aggression < 0.4


@dataclass
class FormContext:
    """形勢判断コンテキスト"""
    score_diff: float        # 自分 - トップ (負ならビハインド、正ならリード)
    rank: int                # 現在順位 (1-4)
    remaining_rounds: int    # 残り局数 (0=オーラス)
    is_dealer: bool          # 親かどうか
    honba: int = 0           # 本場数
    riichi_sticks: int = 0   # 供託リーチ棒数


class FormAnalyzer:
    """形勢判断エンジン"""

    # 点差の基準値（満貫=8000, 跳満=12000, 倍満=16000）
    MANGAN = 8000
    HANEMAN = 12000
    BAIMAN = 16000

    def analyze(self, ctx: FormContext) -> FormScore:
        """
        局面の形勢を分析し、攻守度を返す。
        
        設計思想:
        - ビハインドが深いほど攻勢（逆転を狙う必要がある）
        - リードしているほど守勢（現状を維持すべき）
        - 残り局数が少ないほど点差の影響が大きい
        - 親は連荘の価値があるため攻勢寄り
        """
        aggression = 0.5  # ベース（ニュートラル）
        reasons = []

        # --- 1. 点差による補正 ---
        if ctx.score_diff >= 0:
            # リード中
            if ctx.score_diff >= self.BAIMAN:
                aggression -= 0.25
                reasons.append(f"大幅リード({ctx.score_diff}点)で守勢")
            elif ctx.score_diff >= self.MANGAN:
                aggression -= 0.15
                reasons.append(f"安定リード({ctx.score_diff}点)")
            elif ctx.score_diff >= 2000:
                aggression -= 0.05
                reasons.append(f"微リード({ctx.score_diff}点)")
        else:
            # ビハインド
            deficit = abs(ctx.score_diff)
            if deficit >= self.BAIMAN:
                aggression += 0.25
                reasons.append(f"大幅ビハインド({deficit}点差)で攻勢必須")
            elif deficit >= self.MANGAN:
                aggression += 0.15
                reasons.append(f"ビハインド({deficit}点差)で攻勢")
            elif deficit >= 2000:
                aggression += 0.08
                reasons.append(f"微ビハインド({deficit}点差)")

        # --- 2. 順位による補正 ---
        rank_adj = {1: -0.10, 2: 0.0, 3: 0.08, 4: 0.18}
        aggression += rank_adj.get(ctx.rank, 0.0)
        if ctx.rank >= 3:
            reasons.append(f"現在{ctx.rank}位で順位上昇が必要")

        # --- 3. 残り局数による補正 ---
        if ctx.remaining_rounds <= 1:
            # オーラスまたは残り1局：点差の影響を増幅
            if ctx.score_diff < 0:
                aggression += 0.15
                reasons.append("オーラス接近・逆転が必要")
            elif ctx.score_diff > 0:
                aggression -= 0.10
                reasons.append("オーラス接近・逃げ切り態勢")
        elif ctx.remaining_rounds <= 3:
            if ctx.score_diff < -self.MANGAN:
                aggression += 0.08
                reasons.append("残り局数少・ビハインド大")

        # --- 4. 親補正（連荘の価値） ---
        if ctx.is_dealer:
            aggression += 0.07
            reasons.append("親番・連荘の価値あり")

        # --- 5. 供託リーチ棒の価値 ---
        if ctx.riichi_sticks >= 2:
            aggression += 0.05
            reasons.append(f"供託{ctx.riichi_sticks}本・和了価値上昇")

        # クリッピング
        aggression = max(0.0, min(1.0, aggression))

        return FormScore(
            aggression=round(aggression, 3),
            reasoning="。".join(reasons) if reasons else "標準的な形勢判断"
        )
