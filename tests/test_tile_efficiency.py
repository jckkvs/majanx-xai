import pytest
from server.tile_eval.efficiency_engine import TileEfficiencyEngine, EngineContext
from server.tile_eval.shape_evaluator import EvalContext

def test_4p_6p_8p_connection():
    """4-6-8p連関牌の評価テスト"""
    hand = ['4p', '6p', '8p', '1m', '9m', '1s', '9s', '1z', '2z', '3z', '4z', '6z', '7z']
    engine = TileEfficiencyEngine()
    # 状況：東1局5巡目、ドラなし
    shape_ctx = EvalContext(turn=5, bakaze='east', jikaze='south', dora_indicators=[])
    context = EngineContext(
        turn=5, bakaze_val=1, jikaze_val=2, 
        is_dealer=False, riichi_count=0,
        visible_tiles={}, safe_tiles_remaining=5,
        shape_context=shape_ctx
    )
    
    results = engine.evaluate_discards(hand, context)
    scores = {r.tile_id: r.final_score for r in results}
    
    connected_p = ['4p', '6p', '8p']
    isolated_terminals = ['1m', '9m', '1s', '9s']
    
    for c in connected_p:
        for i in isolated_terminals:
            assert scores[c] > scores[i], f"連関牌 {c}({scores[c]}) は孤立端牌 {i}({scores[i]}) より残すべき(最終スコアが高い)"

def test_honor_pair_value():
    """字牌対子の価値評価テスト"""
    hand = ['1z', '1z', '1m', '2m', '3m', '4p', '5p', '6p', '7s', '8s', '9s', '6z', '7z']
    engine = TileEfficiencyEngine()
    shape_ctx = EvalContext(turn=5, bakaze='east', jikaze='south', dora_indicators=[])
    context = EngineContext(
        turn=5, bakaze_val=1, jikaze_val=2, 
        is_dealer=False, riichi_count=0,
        visible_tiles={}, safe_tiles_remaining=5,
        shape_context=shape_ctx
    )
    
    results = engine.evaluate_discards(hand, context)
    scores = {r.tile_id: r.final_score for r in results}
    
    # 1zは場風牌の対子であり価値が高い。孤立役牌(6z)より優先して残すべき
    assert scores['1z'] > scores['6z'], f"対子字牌1z({scores['1z']}) は孤立字牌6z({scores['6z']}) より残すべき"
