# server/simulation/probability_calculator.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import random
import json
import time

@dataclass(frozen=True)
class ProbabilityResult:
    win_rate: float
    tenpai_rate: float
    deal_in_rate: float
    draw_rate: float

class ProbabilityCalculator:
    """モンテカルロ rollout と統計推定による勝率・放銃率計算"""
    
    MAX_ITERATIONS = 3000
    TIMEOUT_MS = 45
    
    @classmethod
    @lru_cache(maxsize=1024)
    def estimate(
        cls,
        hand_key: str,
        visible_json: str,
        turn: int,
        riichi_count: int,
        strategy_tag: str
    ) -> ProbabilityResult:
        """
        和了・聴牌・放銃・流局確率を推定
        
        Args:
            hand_key: 手牌のハッシュ/正規化文字列
            visible_json: 可視牌カウントJSON
            turn: 現在巡目
            riichi_count: 他家リーチ数
            strategy_tag: 現在の戦略タグ
        """
        visible = json.loads(visible_json)
        wall = cls._build_wall(visible)
        start_time = time.time()
        
        results = {"win": 0, "tenpai": 0, "deal_in": 0, "draw": 0}
        completed = 0
        
        # スレッドプーリングによる並列 rollout
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(cls._single_rollout, hand_key, wall, riichi_count, turn, strategy_tag) 
                       for _ in range(cls.MAX_ITERATIONS)]
            for f in futures:
                res = f.result()
                for k in results:
                    results[k] += res[k]
                completed += 1
                
                # 早期終了: 収束判定またはタイムアウト
                elapsed = (time.time() - start_time) * 1000
                if elapsed > cls.TIMEOUT_MS or completed >= 1000:
                    if completed >= 500:
                        break
                        
        total = max(completed, 1)
        return ProbabilityResult(
            win_rate=results["win"] / total,
            tenpai_rate=results["tenpai"] / total,
            deal_in_rate=results["deal_in"] / total,
            draw_rate=results["draw"] / total
        )
        
    @classmethod
    def _build_wall(cls, visible: Dict[str, int]) -> List[str]:
        """残牌構築"""
        wall = []
        all_tiles = {f"{s}{n}" for s in ['m','p','s'] for n in range(1,10)} | {f"{i}z" for i in range(1,8)}
        for t in all_tiles:
            count = 4 - visible.get(t, 0)
            wall.extend([t] * max(0, count))
        random.shuffle(wall)
        return wall
        
    @classmethod
    def _single_rollout(cls, hand_key: str, wall: List[str], riichi_count: int, turn: int, strategy: str) -> Dict[str, int]:
        """単一シミュレーション実行"""
        # 簡易実装: 手牌進行と他家リーチ時の放銃判定
        # 実運用時は mahjong_utils.calculate_shanten と連携し、牌山から引いた牌で向聴数遷移をシミュレーション
        sim_turn = turn
        current_shanten = cls._estimate_initial_shanten(hand_key)
        
        # 牌山から順次引く簡易シミュレーション
        deck = wall.copy()
        deal_in = False
        while sim_turn <= 17 and len(deck) > 0:
            draw = deck.pop(0) if deck else "unknown"
            # 打牌判定 (簡易: 最悪牌切り出し)
            sim_turn += 1
            current_shanten = max(0, current_shanten - 1) if random.random() > 0.3 else current_shanten
            
            # リーチ他家存在時の放銃判定 (簡易統計)
            if riichi_count > 0 and sim_turn >= 6 and random.random() < 0.08 * riichi_count:
                deal_in = True
                break
                
        if deal_in:
            return {"win": 0, "tenpai": 0, "deal_in": 1, "draw": 0}
        if current_shanten == 0:
            return {"win": 1 if random.random() > 0.2 else 0, "tenpai": 1, "deal_in": 0, "draw": 0}
        if sim_turn >= 17:
            return {"win": 0, "tenpai": 1 if current_shanten <= 1 else 0, "deal_in": 0, "draw": 1}
            
        return {"win": 0, "tenpai": 0, "deal_in": 0, "draw": 1}
        
    @classmethod
    def _estimate_initial_shanten(cls, hand_key: str) -> int:
        # 実運用時は calculate_shanten() を呼び出し
        return 3
