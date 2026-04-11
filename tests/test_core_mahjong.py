import pytest
from server.core.score_calculator import ScoreCalculator
from server.core.agari_validator import FuritenState, AgariValidator
from server.ai.mahjong_brain import ShantenEngine, MahjongBrain
from server.ai.action_judge import ActionJudge

def test_score_calculation():
    # 3 han 40 fu Ron non-dealer: 5200
    res = ScoreCalculator.calc(han=3, fu=40, is_dealer=False, is_ron=True, honba=0, riichi_sticks=0, player_ranks={})
    assert res["winner_gain"] == 5200
    assert res["loser_loss"] == 5200

def test_furiten_same_turn():
    f = FuritenState()
    f.record_pass("5m")
    assert not f.can_ron({"5m"})
    f.record_discard("1s")
    assert f.can_ron({"5m"}) # Same-turn furiten should be cleared after own discard

def test_shanten_ukeire():
    # Example: Pure Chiitoitsu shanten
    # 11 22 33 44 55 66 7 (9 tiles, 6 pairs, 1 single)
    # This hand has 6 pairs, so it is Tenpai for Chiitoitsu.
    # But the recursive engine provided might be for standard 4-mentsu 1-janto only.
    # Let's test a standard shape: 123m 456m 789m 11p 23s
    hand = [0]*34
    for idx in [0,1,2, 3,4,5, 6,7,8, 9,9, 19,20]: hand[idx] = 1
    hand[9] = 2 # 11p pair
    sh, uke = ShantenEngine.calc(hand)
    assert sh == 0 # Tenpai (waiting for 18s or 21s, i.e., 1s or 4s)

def test_action_judge():
    # Correcting call evaluation
    assert ActionJudge.should_call(2, 1, "pon", loses_yaku=False) is True
    assert ActionJudge.should_call(1, 1, "chi", loses_yaku=False) is False

def test_riichi_dama():
    # Very high score, high win prob -> Undeniable Riichi
    assert ActionJudge.riichi_vs_dama(0.5, 12000, 0.05, True, 5) == "riichi"
    # Low score, high risk -> Dama
    assert ActionJudge.riichi_vs_dama(0.15, 2000, 0.4, False, 12) == "dama"
