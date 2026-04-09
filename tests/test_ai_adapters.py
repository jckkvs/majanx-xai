"""
tests/test_ai_adapters.py
複数AI対応のアダプタ層およびアグリゲータのテスト（双視点・定量プロトコル対応版）
"""
import pytest
from server.ai_adapters.base import MJAIAction, AIRecommendation
from server.recommendation_aggregator import RecommendationAggregator
from server.ai_adapters.rulebase_adapter import RulebaseAdapter

def test_recommendation_aggregator_perspectives():
    """アグリゲータが双視点（perspective_parallel）を正しく構築できるかテスト"""
    agg = RecommendationAggregator()
    
    quant_data_valid = {
        "dataset": "鳳凰位公開牌譜2023",
        "period": "2023Q1-Q4",
        "sample_size": "n=1000",
        "confidence_interval_95": "0.6-0.7",
        "methodology": "解析ロジック",
        "extra_info": "ok"
    }

    rec1 = AIRecommendation(
        ai_name="Mortal",
        recommended_action=MJAIAction("dahai", pai="3s"),
        reasoning="Mortal reason",
        raw_output={"quantitative_data": quant_data_valid}
    )
    rec2 = AIRecommendation(
        ai_name="Phoenix",
        recommended_action=MJAIAction("dahai", pai="1p"),
        reasoning="Rulebase reason"
    )
    
    res = agg.aggregate([rec1, rec2], legal_actions=["3s", "1p", "2p"])
    
    assert "perspective_parallel" in res
    perspectives = res["perspective_parallel"]
    assert len(perspectives) == 2
    
    # 視点1の確認
    p1 = perspectives[0]
    assert p1["source_ai"] == "Mortal"
    assert p1["recommended_action"]["pai"] == "3s"
    assert "定量データ" or "dataset" in p1["quantitative_reference"]["data"]
    
    # 視点2の確認
    p2 = perspectives[1]
    assert p2["source_ai"] == "Phoenix"
    assert p2["recommended_action"]["pai"] == "1p"
    assert p2["quantitative_reference"] is None  # 定量がない場合はNone

def test_recommendation_aggregator_quantitative_validation():
    """定量データの5必須条件が1つでも欠けている場合、出力が破棄されるかのテスト"""
    agg = RecommendationAggregator()
    
    quant_data_invalid = {
        "dataset": "鳳凰位データ",
        # period が欠落している
        "sample_size": "n=100",
        "confidence_interval_95": "0.1-0.2",
        "methodology": "適当"
    }
    
    rec1 = AIRecommendation(
        ai_name="FakeAI",
        recommended_action=MJAIAction("dahai", pai="5m"),
        raw_output={"quantitative_data": quant_data_invalid}
    )
    
    res = agg.aggregate([rec1], legal_actions=["5m"])
    p1 = res["perspective_parallel"][0]
    
    # 必須条件の欠如により None として弾かれているはず
    assert p1["quantitative_reference"] is None

@pytest.mark.asyncio
async def test_rulebase_adapter_mock():
    """ルールベースアダプターの基礎挙動テスト"""
    adapter = RulebaseAdapter(engine=None)
    await adapter.connect()
    
    legal_actions = [
        MJAIAction("dahai", pai="1m")
    ]
    
    rec = await adapter.request_action(legal_actions)
    assert rec.ai_name == "Phoenix"
    assert rec.recommended_action.params["pai"] == "1m"
    
    await adapter.disconnect()
