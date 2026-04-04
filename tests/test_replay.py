import pytest
from server.replay_manager import ReplayManager
from server.tenhou_to_mjai import TenhouToMjaiConverter
from server.models import GamePhase

def test_mjai_replay_init():
    rm = ReplayManager()
    events = [
        {"type": "start_game", "names": ["A", "B", "C", "D"]},
        {"type": "start_kyoku", "bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "dora_marker": "1m", "tehais": [["1m"]*13, ["2m"]*13, ["3m"]*13, ["4m"]*13]}
    ]
    rm.load_log(events)
    
    assert rm.step_forward() is True
    assert rm.names == ["A", "B", "C", "D"]
    assert rm.state.phase == GamePhase.WAITING # Because it's only start_game so far
    
    assert rm.step_forward() is True
    
    assert rm.state.phase == GamePhase.PLAYER_TURN
    assert rm.state.dealer == 0
    assert len(rm.state.players[0].hand) == 13

def test_replay_step_backward():
    rm = ReplayManager()
    events = [
        {"type": "start_game"},
        {"type": "tsumo", "actor": 0, "pai": "5s"},
        {"type": "dahai", "actor": 0, "pai": "5s", "tsumogiri": True}
    ]
    rm.load_log(events)
    
    # Process start_game
    rm.step_forward()
    # Process tsumo
    rm.step_forward()
    assert len(rm.state.players[0].hand) == 1
    
    # Process dahai
    rm.step_forward()
    assert len(rm.state.players[0].hand) == 0
    assert len(rm.state.players[0].discards) == 1
    
    # Step backward -> back to tsumo (idx=2)
    assert rm.step_backward() is True
    assert len(rm.state.players[0].hand) == 1
    assert len(rm.state.players[0].discards) == 0

def test_tenhou_converter():
    conv = TenhouToMjaiConverter()
    log_str = "T12 D12"
    evts = conv.convert_log(log_str)
    assert len(evts) == 2
    assert evts[0]["type"] == "tsumo"
    assert evts[1]["type"] == "dahai"
