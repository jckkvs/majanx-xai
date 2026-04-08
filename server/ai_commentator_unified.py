"""
3方向性エンジンを統一インターフェースで提供するファサード
XAIによる推論、戦略エンジンによる戦術評価、Mortal逆推論のすべてを統合。
"""
from __future__ import annotations

import time
from typing import Any, Dict

from server.models import GameState
from server.xai_engine import XAIEngine
from server.strategy_engine import StrategyEngine
from server.mortal_interpreter import MortalInterpreter
from server.mortal.mortal_agent import MortalAgent

class UnifiedCommentator:
    def __init__(self, use_gpu: bool = True):
        # モデルロード等は必要に応じて設定
        self.mortal_agent = MortalAgent(use_gpu=use_gpu)
        self.engines = {
            'xai': XAIEngine(mortal_agent=self.mortal_agent),
            'strategy': StrategyEngine(),
            'interpret': MortalInterpreter()
        }
        self.mode = 'all' # 初期モード ('xai', 'strategy', 'interpret', 'all')

    def analyze(self, game_state: GameState, recommended_idx: int = -1, mortal_prob: float = 0.0) -> Dict[str, Any]:
        """統一エントリーポイント"""
        start_time = time.time()
        
        # recommended_idx が未指定の場合や不正な場合は、現在の推奨のダミー計算またはMortalから取得するが
        # ここではインデックスが渡される前提。渡されなければ最低限フォールバックを行う
        if recommended_idx < 0:
            recommended_idx = 0  # fallback

        if self.mortal_agent and self.mortal_agent.is_loaded:
            action_dict = self.mortal_agent._idx_to_action(recommended_idx, [])
            recommended_tile = action_dict.get("pai", f"idx_{recommended_idx}")
        else:
            recommended_tile = "5m" # fallback dummy

        results = {}

        if self.mode in ('xai', 'all'):
            try:
                results['xai'] = self.engines['xai'].analyze(game_state, recommended_idx)
            except Exception as e:
                print(f"XAI Error: {e}")
                results['xai'] = None

        if self.mode in ('strategy', 'all'):
            try:
                results['strategy'] = self.engines['strategy'].decide_strategy(game_state)
            except Exception as e:
                print(f"Strategy Error: {e}")
                results['strategy'] = None

        if self.mode in ('interpret', 'all'):
            try:
                results['interpret'] = self.engines['interpret'].interpret(game_state, recommended_tile, mortal_prob)
            except Exception as e:
                print(f"Interpret Error: {e}")
                results['interpret'] = None

        if self.mode == 'all':
            return self._merge_results(results, start_time)
        return {"mode": self.mode, "results": results, "execution_time": time.time() - start_time}

    def _merge_results(self, results: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """複数エンジン結果の統合ロジック"""
        explanation_parts = []
        recommendations = []
        confidences = []

        if results.get('xai'):
            xai_res = results['xai']
            explanation_parts.append(f"【XAI】{xai_res.explanation}")
            confidences.append(xai_res.confidence)
            recommendations.append(xai_res.tile_name)
            
        if results.get('strategy'):
            strat_res = results['strategy']
            explanation_parts.append(f"【戦略】{strat_res.rationale}")
            confidences.append(strat_res.score)
            
        if results.get('interpret'):
            interp_res = results['interpret']
            explanation_parts.append(f"【解釈】{interp_res.primary_interpretation}")
            confidences.append(interp_res.confidence)

        explanation = "\n".join(explanation_parts) if explanation_parts else "分析情報を取得できませんでした。"
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        metadata = {
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "engine_versions": "1.0.0",
            "confidence": avg_confidence
        }

        # もし複数の視点から異なる解説が生成されて矛盾があるかの簡易チェック
        # (確信度のばらつきが大きい等の場合)
        if len(confidences) >= 2 and (max(confidences) - min(confidences)) > 0.4:
            explanation += "\n※複数の視点から分析（評価に揺らぎ・場況依存あり）"

        return {
            "mode": "all",
            "explanation": explanation,
            "recommendations": recommendations,
            "metadata": metadata,
            "raw_data": results
        }
