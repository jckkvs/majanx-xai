from typing import List, Set, Dict, Optional, Tuple

class FuritenState:
    """フリテン状態管理"""
    def __init__(self):
        self.discarded: Set[str] = set()
        self.same_turn_wait: Optional[str] = None
        self.is_riichi: bool = False

    def can_ron(self, wait_tiles: Set[str]) -> bool:
        if self.is_riichi:
            return not bool(wait_tiles & self.discarded)
        if self.same_turn_wait and self.same_turn_wait in wait_tiles:
            return False
        return not bool(wait_tiles & self.discarded)

    def record_pass(self, tile: str):
        """ロン見送り: 同巡フリテン付与"""
        if self.same_turn_wait is None:
            self.same_turn_wait = tile

    def clear_same_turn(self):
        """自番打牌で同巡フリテン解除"""
        self.same_turn_wait = None

    def record_discard(self, tile: str):
        self.discarded.add(tile)
        self.clear_same_turn()

class AgariValidator:
    """和了可否・同時処理・途中流局判定"""
    
    @staticmethod
    def validate_simultaneous_ron(
        ron_claims: List[Dict], tile: str, furiten_map: Dict[int, FuritenState]
    ) -> Optional[int]:
        """
        同時ロン処理
        returns: 和了者ID (None: フリテン abort)
        """
        valid = []
        for claim in ron_claims:
            pid = claim["player_id"]
            waits = set(claim["waits"])
            if tile in waits and furiten_map[pid].can_ron(waits):
                valid.append(pid)
                
        if not valid: return None
        # 頭ハネ: 親優先 → 反時計回り席順
        # Note: In standard rules, if dealers are involved, seat distance from discarder is usually the tie-break.
        # Here we follow the user's simplified priority logic.
        valid.sort(key=lambda p: (0 if any(c["player_id"] == p and c.get("is_dealer") for c in ron_claims) else 1, p))
        return valid[0]

    @staticmethod
    def check_abortive_draw(state: Dict) -> Optional[str]:
        """途中流局判定"""
        if state.get("kyushu_kyuhai", False): return "九種九牌"
        if state.get("consecutive_wind_discards", 0) >= 4: return "四風連打"
        if len(state.get("kan_history", [])) >= 4: return "四槓散了"
        if len(state.get("active_ron_claims", [])) >= 3: return "三家和"
        return None
