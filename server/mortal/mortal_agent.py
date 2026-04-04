"""
Mortal Agent
Implements: F-103 | ロジットからの最善手決定ロジック
"""
import numpy as np
from typing import Optional

from server.models import GameState, GameAction, ActionType, Tile, TileSuit
from .feature_extractor import MortalFeatureExtractor
from .mortal_engine import MortalEngine


class MortalAgent:
    """
    ONNX出力（ロジットや確率分布）から実際のアクション (GameAction) を決定するエージェント。
    """
    
    def __init__(self, seat: int, engine, rng=None):
        self.seat = seat
        self.game_engine = engine
        self.extractor = MortalFeatureExtractor()
        self.mortal = MortalEngine()
        self.rng = rng

    def _get_probabilities(self) -> np.ndarray:
        st = self.game_engine.state
        features = self.extractor.extract_features(st, self.seat)
        return self.mortal.get_action_probabilities(features)

    def choose_discard(self) -> Tile:
        """打牌を選択 (出力 0-33 が各牌へのロジットと仮定)"""
        st = self.game_engine.state
        player = st.players[self.seat]
        
        probs = self._get_probabilities()
        
        # モデル出力を 0-33 の牌の確率として扱う
        discard_probs = probs[:34]
        
        # 実際に手牌にある牌だけにフィルタリングして確率を正規化
        valid_indices = []
        for t in player.hand:
            valid_indices.append(self.extractor._tile_to_index(t))
            
        best_tile = None
        best_prob = -1.0
        
        for t in player.hand:
            idx = self.extractor._tile_to_index(t)
            p = discard_probs[idx]
            if p > best_prob:
                best_prob = p
                best_tile = t
        
        if best_tile is None:
            # フォールバック
            return player.hand[-1]
            
        return best_tile

    def decide_tsumo_action(self, options: list[GameAction]) -> Optional[GameAction]:
        """各種ツモ時判定 (和了, リーチ, カン)"""
        # アクションチャネルの確率(34以降)から判断する論理。
        # 今回は優先順で、可能な場合(和了確定など)は採用。
        probs = self._get_probabilities()
        action_probs = probs[34:] # ツモ, リーチ, カン, ポン, チー, (スキップ)
        
        # インデックス定義マッピング仮定 (34: HORA, 35: RIICHI, 36: ANKAN)
        hora_prob = action_probs[0] if len(action_probs) > 0 else 0
        riichi_prob = action_probs[1] if len(action_probs) > 1 else 0
        
        for opt in options:
            if opt.action_type == ActionType.HORA:
                if hora_prob > 0.05 or True: # 和了は一律許容
                    return opt
            if opt.action_type == ActionType.RIICHI:
                if riichi_prob > 0.2:
                    return opt
        
        return None

    def decide_call(self, options: list[GameAction]) -> GameAction:
        """鳴きの判定"""
        probs = self._get_probabilities()
        action_probs = probs[34:] 
        
        hora_prob = action_probs[0] if len(action_probs) > 0 else 0
        pon_prob = action_probs[3] if len(action_probs) > 3 else 0
        chi_prob = action_probs[4] if len(action_probs) > 4 else 0
        
        for opt in options:
            if opt.action_type == ActionType.HORA:
                return opt
                
        best_call = None
        best_val = 0.5 # 鳴き閾値
        
        for opt in options:
            if opt.action_type == ActionType.PON and pon_prob > best_val:
                best_val = pon_prob
                best_call = opt
            if opt.action_type == ActionType.CHI and chi_prob > best_val:
                best_val = chi_prob
                best_call = opt
        
        if best_call:
            return best_call

        return GameAction(action_type=ActionType.SKIP, player=self.seat)

    @property
    def last_decision(self):
        # 現在のCPUPlayerのプロパティインターフェース用互換性
        return None
