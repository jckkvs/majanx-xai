# server/ensemble_ai.py
from typing import Dict, List, Any
import time

from server.tactics.attack_fold_controller import AttackFoldController
from server.tactics.call_evaluator import CallEvaluator
from server.tactics.riichi_judge import RiichiJudge
from server.ai.offline_progression import OfflineEngine
from server.ai.cpu_pacing import CPUPacingEngine

class MockNNEngine:
    def predict(self, features: Any) -> Dict[str, float]:
        return {
            "win_rate": 0.25,
            "deal_in_rate": 0.10,
            "value": 4000.0,
            "shanten": 1,
            "win_rate_dama": 0.20,
            "risk": 0.05
        }

class FeatureBuilder:
    @classmethod
    def build_state_tensor(cls, **kwargs):
        return [0] * 100

class EnsembleAI:
    def __init__(self, model_path: str = ""):
        # Mock NN engine for the v7.0 specification
        self.nn_engine = MockNNEngine()
        self.offline_engine = OfflineEngine()
        
    def recommend(self, game_state: Dict, hand: List[str], my_seat: int) -> Dict:
        start_time = time.time()
        
        # 1. 基本特徴量抽出・NN推論 (既存)
        features = FeatureBuilder.build_state_tensor(**game_state)
        nn_output = self.nn_engine.predict(features)
        
        # 2. 他家打牌評価 (鳴き判定)
        if game_state.get("discard_player") is not None:
            call_dec = CallEvaluator.evaluate(
                current_hand=hand, 
                call_target=game_state.get("discard_tile", ""), 
                call_type="chi/pon/kan",
                current_shanten=int(nn_output["shanten"]), 
                current_value=nn_output["value"],
                current_risk=nn_output["risk"], 
                turn=game_state.get("turn", 1), 
                riichi_count=game_state.get("riichi_count", 0)
            )
            if call_dec.should_call:
                return {
                    "action": "call", 
                    "type": call_dec.call_type, 
                    "latency_ms": self._get_latency(start_time)
                }
                
        # 3. 攻守判断
        af_dec = AttackFoldController.decide(
            win_prob=nn_output["win_rate"],
            deal_in_prob=nn_output["deal_in_rate"],
            avg_hand_value=nn_output["value"],
            current_score_diff=game_state.get("score_diff", 0),
            rank=game_state.get("rank", 2),
            turn=game_state.get("turn", 1),
            is_riichi_opponent=len(game_state.get("riichi_players", [])) > 0
        )
        
        # 4. 打牌候補フィルタリング
        candidates = self._filter_candidates(hand, af_dec, nn_output, game_state)
        if not candidates:
            # Fallback if no valid candidates
            candidates = [{"tile": hand[0] if hand else "1m", "risk_score": 0.0}]
            
        # 5. リーチ判定 (聴牌時)
        riichi_dec = None
        if nn_output["shanten"] == 0:
            riichi_dec = RiichiJudge.judge(
                hand=hand, 
                win_prob_dama=nn_output.get("win_rate_dama", 0.2), 
                deal_in_prob=nn_output["deal_in_rate"],
                avg_hand_value=nn_output["value"], 
                riichi_opponents=len(game_state.get("riichi_players", [])),
                turn=game_state.get("turn", 1), 
                is_dealer=game_state.get("is_dealer", False)
            )

        # 6. CPU Pacing (Local Offline Context)
        pacing_cfg = self.offline_engine.cpu_diff
        pacing_engine = CPUPacingEngine(difficulty=pacing_cfg)
        cpu_action = pacing_engine.resolve(candidates, {
            "opponent_riichi": len(game_state.get("riichi_players", [])) > 0,
            "turn": game_state.get("turn", 1)
        })
            
        # 7. 最終出力
        return {
            "action": "discard",
            "tile": cpu_action.tile,
            "riichi": riichi_dec.should_riichi if riichi_dec else False,
            "reasoning": af_dec.reason,
            "latency_ms": self._get_latency(start_time),
            "cpu_delay_ms": cpu_action.delay_ms,
            "is_suboptimal": cpu_action.is_suboptimal,
            "cpu_difficulty": pacing_cfg
        }
        
    def _filter_candidates(self, hand: List[str], af_dec, nn_output, game_state) -> List[Dict]:
        return [{"tile": t, "risk_score": 0.1 * idx} for idx, t in enumerate(set(hand))]
        
    def _get_latency(self, start_time: float) -> float:
        return (time.time() - start_time) * 1000.0
