"""
tests/test_ai_adapters.py
複数AI対応のアダプタ層およびアグリゲータのテスト
"""
import pytest
from server.ai_adapters.base import MJAIAction, AIRecommendation
from server.recommendation_aggregator import RecommendationAggregator
from server.ai_adapters.rulebase_adapter import RulebaseAdapter

def test_recommendation_aggregator_consensus():
    """アグリゲータがコンセンサスを正しく検出できるかテスト"""
    agg = RecommendationAggregator()
    
    # AI 1: 3s
    rec1 = AIRecommendation(
        ai_name="Mortal",
        recommended_action=MJAIAction("dahai", pai="3s"),
        reasoning="Mortal reason"
    )
    # AI 2: 3s
    rec2 = AIRecommendation(
        ai_name="Rulebase",
        recommended_action=MJAIAction("dahai", pai="3s"),
        reasoning="Rulebase reason"
    )
    # AI 3: 1p
    rec3 = AIRecommendation(
        ai_name="Phoenix",
        recommended_action=MJAIAction("dahai", pai="1p"),
        reasoning="Phoenix reason"
    )
    
    res = agg.aggregate([rec1, rec2, rec3], legal_actions=["3s", "1p", "2p"])
    
    assert res["consensus"]["tile"] == "3s"
    assert res["consensus"]["agreement_ratio"] == 2/3
    assert len(res["consensus"]["reasoning_sources"]) == 2
    assert len(res["alternatives"]) == 1
    assert res["alternatives"][0]["tile"] == "1p"
    assert "Rulebase reason" in res["qualitative_frame"]
    assert not res["conflicts"]  # 対立（同数）は起きていない

def test_recommendation_aggregator_conflict():
    """アグリゲータが意見対立（同数票）を正しく検出できるかテスト"""
    agg = RecommendationAggregator()
    
    rec1 = AIRecommendation(
        ai_name="Mortal",
        recommended_action=MJAIAction("dahai", pai="3s")
    )
    rec2 = AIRecommendation(
        ai_name="Rulebase",
        recommended_action=MJAIAction("dahai", pai="1p")
    )
    
    res = agg.aggregate([rec1, rec2], legal_actions=["3s", "1p"])
    
    # 3sか1pがコンセンサスとして選ばれるが、対立リストにも両方が入るはず
    assert len(res["conflicts"]) == 2
    assert set(res["conflicts"]) == set(["3s", "1p"])

@pytest.mark.asyncio
async def test_rulebase_adapter_mock():
    """ルールベースアダプターの基礎挙動テスト"""
    # エンジンなしのモック実行
    adapter = RulebaseAdapter(engine=None)
    await adapter.connect()
    
    legal_actions = [
        MJAIAction("dahai", pai="1m"),
        MJAIAction("dahai", pai="2p")
    ]
    
    rec = await adapter.request_action(legal_actions)
    assert rec is not None
    assert rec.ai_name == "Rulebase (定性)"
    assert rec.recommended_action.type == "dahai"
    assert rec.recommended_action.params["pai"] == "1m"
    assert "受入枚数を広げて" in rec.reasoning
    
    await adapter.disconnect()
