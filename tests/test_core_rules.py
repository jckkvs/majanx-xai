import pytest
from server.rules.rule_validator import FuritenState, DoraTracker

def test_furiten_same_turn():
    f = FuritenState()
    f.pass_ron()
    assert not f.can_ron({"3m"})
    f.record_discard("1s")
    assert f.can_ron({"3m"}) # 同巡解除

def test_kan_dora_timing():
    d = DoraTracker(indicators=["2s"])
    wall = ["5m", "7p", "9s"]
    assert d.resolve_kan("open_kan", wall) == "5m"
    assert d.indicators == ["2s", "5m"]
