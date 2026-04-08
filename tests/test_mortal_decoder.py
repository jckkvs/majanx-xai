import pytest
from server.action_decoder import decode_action
from server.mortal_inference import MortalInference

def test_decode_action_tiles():
    """牌の出力（0-33）のデコードテスト"""
    # 0 = 1m
    res = decode_action(0, 0.8, 1.2)
    assert res["tile_id"] == "1m"
    assert res["action_type"] == "dahai"
    assert res["probability"] == 0.8
    assert res["q_value"] == 1.2

    # 8 = 9m
    res = decode_action(8, 0.1, 0.0)
    assert res["tile_id"] == "9m"

    # 9 = 1p
    res = decode_action(9, 0.1, 0.0)
    assert res["tile_id"] == "1p"

    # 27 = 1z (東)
    res = decode_action(27, 0.1, 0.0)
    assert res["tile_id"] == "1z"

    # 33 = 7z (中)
    res = decode_action(33, 0.1, 0.0)
    assert res["tile_id"] == "7z"

def test_decode_action_special():
    """鳴きやアガリ（34-45）のデコードテスト"""
    # 34 = ツモ切り
    res = decode_action(34, 0.5, 0.5)
    assert res["tile_id"] == "tsumogiri"
    assert res["action_type"] == "tsumogiri"

    # 35 = chi
    res = decode_action(35, 0.5, 0.5)
    assert res["tile_id"] == "chi"
    assert res["action_type"] == "chi"

    # 40 = hora
    res = decode_action(40, 0.5, 0.5)
    assert res["tile_id"] == "hora"
    assert res["action_type"] == "hora"

def test_mortal_mock_inference():
    """Mortalのモック推論テスト"""
    engine = MortalInference(model_path="dummy/path/not_exist.pth")
    # ダミーイベント送出
    res = engine.predict([])
    
    assert "recommendation" in res
    assert "tile" in res["recommendation"]
    assert "probability" in res["recommendation"]
    assert "alternatives" in res["recommendation"]
    
    # モックによる確率計算で上位5手が絞り込まれているはず
    assert len(res["recommendation"]["alternatives"]) <= 4
