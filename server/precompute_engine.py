import asyncio
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

class PrecomputeEngine:
    """
    次ツモに備えて全34パターンの最善手を事前計算
    -> 実際のツモ時は0秒で回答可能
    """
    
    def __init__(self, mortal_agent=None, rule_engine=None):
        self.shanten_calc = Shanten()
        self.mortal = mortal_agent
        self.rule = rule_engine
        self.cache: Dict[int, Dict] = {}  # tile_idx -> 解説結果
        self.is_computing = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    async def precompute(self, hand_34: List[int], visible_34: List[int], 
                         round_info: Dict, timeout: float = 1.5):
        """
        現在の状態から、次にあり得る34種のツモに対する回答を事前計算
        制限時間内に終わらなければルールベースでフォールバック
        """
        if self.is_computing:
            return  # 重複計算防止
            
        self.is_computing = True
        self.cache.clear()
        
        start = time.time()
        
        # 非ブロッキングで並列計算
        loop = asyncio.get_event_loop()
        
        for tile_idx in range(34):
            if time.time() - start > timeout:
                print(f"[Precompute] \u23F0 タイムアウト: {tile_idx}/34 完了")
                break
                
            # 山にその牌が残っているか簡易チェック
            if visible_34[tile_idx] >= 4:
                continue
                
            # 非同期で計算タスクを投入
            task = loop.run_in_executor(
                self.executor,
                self._compute_single,
                hand_34.copy(), tile_idx, visible_34.copy(), round_info.copy()
            )
            # 結果はキャッシュに格納（完了順）
            asyncio.create_task(self._store_result(tile_idx, task))
        
        self.is_computing = False
        print(f"[Precompute] \u2705 事前計算完了: {len(self.cache)}/34 patterns")
    
    def _compute_single(self, hand_34, tsumo_idx, visible_34, round_info):
        """単一パターンに対する解説計算（CPUバウンド）"""
        # 手牌にツモ牌を追加
        hand_34[tsumo_idx] += 1
        
        # Mortalがあれば優先、なければルールベース
        if self.mortal and getattr(self.mortal, 'is_loaded', False) and hasattr(self.mortal, 'predict_fast'):
            # Mortal推論（軽量モード）
            result = self.mortal.predict_fast(hand_34, visible_34, round_info)
        else:
            # ルールベース高速計算
            result = self._rule_based_fast(hand_34, tsumo_idx, visible_34, round_info)
        
        return result
    
    async def _store_result(self, tile_idx: int, task):
        """計算結果をキャッシュに格納"""
        try:
            result = await task
            self.cache[tile_idx] = result
        except Exception as e:
            print(f"[Precompute] \u274C tile {tile_idx} error: {e}")
    
    def get_response(self, tsumo_idx: int) -> Optional[Dict]:
        """事前計算結果を取得（即座に返す）"""
        return self.cache.get(tsumo_idx)
    
    def _rule_based_fast(self, hand_34, tsumo_idx, visible_34, round_info):
        """
        超高速ルールベース計算（Mortalフォールバック用）
        受入枚数＋危険度のみで1ms以内に回答
        """
        current_sh = self.shanten_calc.calculate_shanten(hand_34)
        best = None
        best_score = -999
        
        for i in range(34):
            if hand_34[i] == 0: continue
            
            sim = hand_34.copy()
            sim[i] -= 1
            sh = self.shanten_calc.calculate_shanten(sim)
            
            # 受入枚数（簡易）
            acc = sum(1 for j in range(34) if sim[j] < 4 
                     and self.shanten_calc.calculate_shanten(
                         [sim[k] + (1 if k==j else 0) for k in range(34)]
                     ) < sh)
            
            # 危険度（簡易）
            risk = 0.1 if not round_info.get('is_riichi') else (
                0.05 if visible_34[i] >= 3 else 0.5
            )
            
            # 評価スコア
            score = acc * (2.0 if sh < current_sh else 1.0) - risk * 3.0
            
            if score > best_score:
                best_score = score
                best = {
                    "recommendation": TilesConverter.to_string([i])[0],
                    "explanation": f"受入{acc}枚・危険度{risk:.2f}",
                    "is_precomputed": True,
                    "method": "rule_fast"
                }
        
        return best or {"recommendation": "5m", "explanation": "デフォルト", "is_precomputed": True}
