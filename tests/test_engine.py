import pytest
from server.engine import GameEngine
from server.models import Tile, TileSuit, ActionType, GamePhase, GameAction

def test_engine_init_and_start():
    engine = GameEngine()
    engine.start_game()
    assert engine.state.round_number == 0
    assert len(engine.state.players) == 4
    for p in engine.state.players:
        assert p.score == 25000
        assert len(p.hand) == 13
    assert engine.state.phase == GamePhase.PLAYER_TURN
    assert engine.state.tiles_remaining == 70

def test_engine_tsumo_and_dahai():
    engine = GameEngine(seed=42)
    engine.start_game()
    curr = engine.state.current_player
    initial_tiles = engine.state.tiles_remaining
    
    tile = engine.do_tsumo()
    assert tile is not None
    assert engine.state.tiles_remaining == initial_tiles - 1
    assert len(engine.state.players[curr].hand) == 14
    
    # Dahai
    discard = engine.state.players[curr].hand[-1]
    res = engine.do_dahai(curr, discard)
    assert res is True
    assert len(engine.state.players[curr].hand) == 13
    assert len(engine.state.players[curr].discards) == 1
    assert engine.state.phase == GamePhase.CALLING

def test_engine_call_options():
    engine = GameEngine(seed=42)
    engine.start_game()
    
    # Forcing a discard
    curr = engine.state.current_player
    tile = engine.do_tsumo()
    discard = engine.state.players[curr].hand[0]
    engine.do_dahai(curr, discard)
    
    # Check options for next player
    next_p = (curr + 1) % 4
    options = engine.get_call_options(next_p)
    assert isinstance(options, list)
    
    # Force a Pon scenario
    discard = Tile(suit=TileSuit.MAN, number=5)
    engine.state.last_discard = discard
    engine.state.last_discard_player = curr
    
    # Give next_p two 5m
    engine.state.players[next_p].hand = [
        Tile(suit=TileSuit.MAN, number=5),
        Tile(suit=TileSuit.MAN, number=5),
        Tile(suit=TileSuit.MAN, number=1)
    ]
    options = engine.get_call_options(next_p)
    assert any(o.action_type == ActionType.PON for o in options)

def test_engine_riichi():
    engine = GameEngine(seed=42)
    engine.start_game()
    curr = engine.state.current_player
    
    # Forcing Tenpai hand for riichi
    player = engine.state.players[curr]
    player.hand = [
        Tile(suit=TileSuit.MAN, number=1), Tile(suit=TileSuit.MAN, number=1), Tile(suit=TileSuit.MAN, number=1),
        Tile(suit=TileSuit.PIN, number=2), Tile(suit=TileSuit.PIN, number=2), Tile(suit=TileSuit.PIN, number=2),
        Tile(suit=TileSuit.SOU, number=3), Tile(suit=TileSuit.SOU, number=3), Tile(suit=TileSuit.SOU, number=3),
        Tile(suit=TileSuit.WIND, number=1), Tile(suit=TileSuit.WIND, number=1), Tile(suit=TileSuit.WIND, number=1),
        Tile(suit=TileSuit.WIND, number=2), Tile(suit=TileSuit.WIND, number=3)
    ]
    
    assert engine.do_riichi(curr, player.hand[-1]) is True
    assert player.is_riichi is True
    assert player.score == 24000
    assert engine.state.riichi_sticks == 1

def test_engine_ryukyoku():
    engine = GameEngine()
    engine.start_game()
    
    # Force ryukyoku
    engine.state.wall_pointer = len(engine.state.wall) 
    
    tile = engine.do_tsumo()
    assert tile is None
    assert engine.state.phase == GamePhase.ROUND_END

def test_engine_hora():
    engine = GameEngine()
    engine.start_game()
    
    player = engine.state.players[0]
    # Set a winning hand (Kokushi Musou pseudo, but just using basic for speed)
    player.hand = [
        Tile(suit=TileSuit.MAN, number=1), Tile(suit=TileSuit.MAN, number=2), Tile(suit=TileSuit.MAN, number=3),
        Tile(suit=TileSuit.PIN, number=4), Tile(suit=TileSuit.PIN, number=5), Tile(suit=TileSuit.PIN, number=6),
        Tile(suit=TileSuit.SOU, number=7), Tile(suit=TileSuit.SOU, number=8), Tile(suit=TileSuit.SOU, number=9),
        Tile(suit=TileSuit.WIND, number=1), Tile(suit=TileSuit.WIND, number=1), Tile(suit=TileSuit.WIND, number=1),
        Tile(suit=TileSuit.WIND, number=2), Tile(suit=TileSuit.WIND, number=2)
    ]
    
    res = engine.handle_hora(0, 0, is_tsumo=True)
    assert "yakus" in res
    assert res["points"] > 0
