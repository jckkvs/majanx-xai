import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from server.game_manager import GameManager
from server.models import GamePhase, Tile, TileSuit

@pytest.fixture
def gm():
    return GameManager(seed=42)

@pytest.mark.asyncio
async def test_game_manager_start(gm):
    mock_send = AsyncMock()
    gm.set_client_handler(mock_send)
    
    # Normally start_game loops forever, we need to mock something or just test pieces
    gm.engine.start_game()
    assert gm.engine.state.phase == GamePhase.PLAYER_TURN
    assert len(gm.cpus) == 0 # We didn't call start_game fully yet
    
    # We will test _send
    await gm._send({"type": "test"})
    mock_send.assert_called_once_with({"type": "test"})

@pytest.mark.asyncio
async def test_human_dahai(gm):
    # Setup state
    gm.engine.start_game()
    
    mock_send = AsyncMock()
    gm.set_client_handler(mock_send)
    
    tile = gm.engine.state.players[0].hand[0]
    
    # Send dahai via receive_human_input
    task = asyncio.create_task(gm._wait_for_human_input())
    await asyncio.sleep(0.01)
    gm.receive_human_input({
        "action": "dahai",
        "tile": str(tile),
        "tsumogiri": False
    })
    
    res = await task
    assert res["action"] == "dahai"
    
    await gm._process_human_action(res)
    assert gm.engine.state.last_discard == tile
    # send should have been called with "game_state"
    mock_send.assert_called()

@pytest.mark.asyncio
async def test_human_skip(gm):
    gm.engine.start_game()
    
    task = asyncio.create_task(gm._wait_for_human_input())
    await asyncio.sleep(0.01)
    gm.receive_human_input({
        "action": "skip"
    })
    
    res = await task
    assert res["action"] == "skip"
    
    await gm._process_human_action(res)
    # skip doesn't change state directly in _process_human_action

@pytest.mark.asyncio
async def test_cpu_turn(gm):
    gm.engine.start_game()
    
    # Setting up CPUs manually
    from server.mortal.mortal_agent import MortalAgent
    gm.cpus[1] = MortalAgent(1, gm.engine)
    
    mock_send = AsyncMock()
    gm.set_client_handler(mock_send)
    
    # Trigger a CPU turn
    await gm._handle_cpu_turn(1, [])
    
    # The CPU should discard a tile, and state advances
    assert gm.engine.state.last_discard_player == 1
    assert mock_send.call_count >= 1

@pytest.mark.asyncio
async def test_game_loop_ryukyoku(gm):
    mock_send = AsyncMock()
    gm.set_client_handler(mock_send)
    
    gm.engine.start_game()
    # empty wall
    gm.engine.state.wall_pointer = len(gm.engine.state.wall)
    
    # Call loop, it should break after tsumo returns None and ryukyoku is processed
    await gm._game_loop()
    
    # send should be called with ryukyoku from engine if we had handler, but gm loop sends logic too
    calls = mock_send.mock_calls
    types = []
    for c in calls:
        if c.args:
            types.append(c.args[0].get("type", "unknown"))
        elif c.kwargs and "msg" in c.kwargs:
            types.append(c.kwargs["msg"].get("type", "unknown"))
    assert "game_state" in types 
    assert gm.engine.state.phase == GamePhase.ROUND_END
    assert "round_end" in types
