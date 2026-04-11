from typing import Dict, List, Any
import time
from server.ai.offline_progression import OfflineEngine
from server.ai.cpu_pacing import CPUPacingEngine
from server.ai.mahjong_brain import MahjongBrain, ShantenEngine
from server.ai.action_judge import ActionJudge
from server.utils.mahjong_logic import hand_to_34
from server.models import tile_from_str

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
        self.offline_engine = OfflineEngine()
        
    def recommend(self, game_state: Dict, hand: List[str], my_seat: int) -> Dict:
        start_time = time.time()
        
        # 文字列手牌を34形式に変換
        hand_tiles = [tile_from_str(t) for t in hand]
        hand_34 = hand_to_34(hand_tiles)
        
        def idx_to_tile(idx: int) -> str:
            suits = ['m', 'p', 's', 'z']
            s = suits[idx // 9]
            n = (idx % 9) + 1
            return f"{n}{s}"

        # 1. 向聴数計算
        shanten, ukeire = ShantenEngine.calc(hand_34)
        
        # 2. 打牌評価 (MahjongBrain)
        river_data = {
            "turn": game_state.get("turn", 1),
            "discards": game_state.get("discards", [[],[],[],[]])
        }
        riichi_flags = game_state.get("riichi_flags", [False]*4)
        opponents = [{"id": i, "riichi": riichi_flags[i]} for i in range(4) if i != my_seat]
        best_move = MahjongBrain.evaluate_discard(hand_34, river_data, opponents)

        # 3. 全打牌候補の評価 (Discard Support 用)
        discard_options = {}
        for tile_id in set(hand):
            temp_hand = [t for t in hand]
            temp_hand.remove(tile_id)
            temp_hand_tiles = [tile_from_str(t) for t in temp_hand]
            temp_hand_34 = hand_to_34(temp_hand_tiles)
            s, u = ShantenEngine.calc(temp_hand_34)
            discard_options[tile_id] = {
                "shanten": s,
                "ukeire_count": len(u),
                "waits": [idx_to_tile(idx) for idx in u[:8]]
            }
            
        # 4. リーチ判定 (ActionJudge)
        riichi_action = "none"
        if shanten == 0:
            riichi_action = ActionJudge.riichi_vs_dama(
                win_prob=0.3, 
                avg_score=4000, 
                deal_in_prob=0.1, 
                is_riichi_safe=True, 
                turn=game_state.get("turn", 1)
            )
                
        # 5. 出力
        return {
            "action": "discard",
            "tile": idx_to_tile(best_move["tile_idx"]),
            "riichi": riichi_action == "riichi",
            "shanten": shanten,
            "ukeire": len(ukeire),
            "discard_options": discard_options,
            "reasoning": f"Attack: {best_move['attack']:.2f}, Defense: {best_move['defense']:.2f}",
            "latency_ms": (time.time() - start_time) * 1000.0,
        }

    def _get_latency(self, start_time: float) -> float:
        return (time.time() - start_time) * 1000.0
