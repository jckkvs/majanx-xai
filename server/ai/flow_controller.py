# server/ai/flow_controller.py
from typing import Dict, Any

class FlowController:
    """実力差・連勝/連敗・局内点差に応じCPUの攻撃性/思考速度を動的調整"""
    def __init__(self, base_pacing):
        self.base = base_pacing
        self.win_streak = 0
        self.loss_streak = 0

    def adjust_context(self, ctx: Dict[str, Any], score_diff: int) -> Dict[str, Any]:
        if score_diff > 8000:
            ctx["hesitation_override"] = max(ctx.get("hesitation", 0), 0.20)
        elif score_diff < -8000:
            ctx["suboptimal_override"] = 0.12
        elif abs(score_diff) < 2000:
            ctx["hesitation_override"] = 0.05
        return ctx

    def record_result(self, player_won: bool):
        if player_won:
            self.win_streak += 1
            self.loss_streak = 0
        else:
            self.loss_streak += 1
            self.win_streak = 0
