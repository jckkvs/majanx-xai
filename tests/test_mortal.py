import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from server.models import GameState, PlayerState, Tile, TileSuit, GameAction, ActionType
from server.mortal.feature_extractor import MortalFeatureExtractor
from server.mortal.mortal_engine import MortalEngine
from server.mortal.mortal_agent import MortalAgent
from server.engine import GameEngine


def test_feature_extractor():
    state = GameState()
    for i in range(4):
        state.players.append(PlayerState(seat=i))
    
    # 自身の手牌を設定
    me = state.players[0]
    me.add_tile(Tile(suit=TileSuit.MAN, number=1))
    me.add_tile(Tile(suit=TileSuit.PIN, number=9))
    
    # 他家の捨て牌
    state.players[1].discards.append(Tile(suit=TileSuit.SOU, number=5))
    
    # ドラ設定
    state.dora_indicators.append(Tile(suit=TileSuit.WIND, number=1)) # 東
    
    extractor = MortalFeatureExtractor()
    features = extractor.extract_features(state, player_seat=0)
    
    assert features.shape == (10, 34)
    # self hand
    assert features[0, 0] == 1.0 # 1m
    assert features[0, 17] == 1.0 # 9p
    
    # 下家捨牌
    assert features[3, 22] == 1.0 # 5s  (1 + 1*2 = 3)
    
    # ドラ
    assert features[9, 27] == 1.0 # 東

def test_mortal_engine():
    engine = MortalEngine(model_path="dummy_path_that_does_not_exist.onnx")
    features = np.zeros((10, 34), dtype=np.float32)
    # 手牌に何かある状態にする
    features[0, 0] = 1.0
    
    probs = engine.get_action_probabilities(features)
    assert probs.shape == (47,)
    assert 0.0 < probs[0] < 1.0
    assert np.isclose(probs.sum(), 1.0)
    assert probs[0] > probs[1] # bias should work for hand tiles

@patch("os.path.exists", return_value=True)
@patch("server.mortal.mortal_engine.ort.InferenceSession")
def test_mortal_engine_onnx_branch(mock_ort, mock_exists):
    # Mocking ort.InferenceSession and its run method
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "input_name"
    mock_session.get_inputs.return_value = [mock_input]
    mock_session.run.return_value = [np.ones((1, 47), dtype=np.float32)]
    mock_ort.return_value = mock_session

    engine = MortalEngine(model_path="fake_model.onnx")
    features = np.zeros((10, 34), dtype=np.float32)
    probs = engine.get_action_probabilities(features)
    assert probs.shape == (47,)
    mock_session.run.assert_called_once()

def test_mortal_agent():
    game_engine = GameEngine()
    game_engine.start_game()
    agent = MortalAgent(seat=0, engine=game_engine)
    
    # Player 0 の手牌をリセットして指定
    player = game_engine.state.players[0]
    player.hand = []
    player.add_tile(Tile(suit=TileSuit.MAN, number=1))
    player.add_tile(Tile(suit=TileSuit.PIN, number=9))
    
    discard = agent.choose_discard()
    assert discard.suit in [TileSuit.MAN, TileSuit.PIN]
    assert discard.number in [1, 9]

    # Decide Tsumo Action (HORA should trigger if prob is reasonable)
    opt1 = GameAction(action_type=ActionType.HORA, player=0)
    opt2 = GameAction(action_type=ActionType.ANKAN, player=0, tile=Tile(suit=TileSuit.MAN, number=1))
    opt_riichi = GameAction(action_type=ActionType.RIICHI, player=0, tile=Tile(suit=TileSuit.MAN, number=1))
    
    res = agent.decide_tsumo_action([opt1, opt2])
    assert res == opt1 or res is None
    
    # Mock probabilities to favor riichi
    with patch.object(agent, '_get_probabilities') as mock_probs:
        probs = np.zeros(47)
        probs[35] = 1.0 # Force riichi prob high
        mock_probs.return_value = probs
        res_r = agent.decide_tsumo_action([opt_riichi])
        assert res_r == opt_riichi

    # Decide Call
    opt3 = GameAction(action_type=ActionType.PON, player=0)
    opt4 = GameAction(action_type=ActionType.CHI, player=0)
    res_call = agent.decide_call([opt3, opt4])
    assert res_call.action_type in [ActionType.PON, ActionType.CHI, ActionType.SKIP]

    # Decide Call with Hora
    res_call2 = agent.decide_call([opt3, opt1])
    assert res_call2.action_type == ActionType.HORA
    
    # Empty hand fallback discard
    player.hand = []
    try:
        agent.choose_discard()
    except IndexError:
        pass # fallback throws when hand is empty, or works if logic tries player.hand[-1]
