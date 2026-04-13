# tests/test_rules.py
import pytest
from core.rules.mahjong_engine import MahjongRuleEngine

@pytest.fixture
def engine():
    return MahjongRuleEngine()

def test_tile_to_34_mapping(engine):
    assert engine.tile_to_34_index("1m") == 0
    assert engine.tile_to_34_index("9m") == 8
    assert engine.tile_to_34_index("1p") == 9
    assert engine.tile_to_34_index("9s") == 26
    assert engine.tile_to_34_index("1z") == 27
    assert engine.tile_to_34_index("7z") == 33

def test_shanten_calculation(engine):
    # Chuuren Poutou (9-sided wait)
    hand = ["1m", "1m", "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "9m", "9m"]
    # 1枚持ってきたら和了なので、聴牌状態 = 0 shanten (in some contexts -1, but mahjong library returns 0 for tenhou if 13 tiles, or -1 if 14 tiles)
    # 13枚の場合、calculate_shanten は あと何枚で和了か を返す
    # 13枚聴牌 = 0, 14枚和了 = -1
    res = engine.get_shanten(hand)
    assert res == 0

def test_agari_detection(engine):
    hand = ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "1z", "1z", "1z", "2z", "2z"]
    assert engine.check_agari(hand) is True

def test_invalid_tile(engine):
    with pytest.raises(ValueError):
        engine.tile_to_34_index("0m")
    with pytest.raises(ValueError):
        engine.tile_to_34_index("1x")
