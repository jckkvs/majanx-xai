"""
tests/test_game_loop.py
詳細設計仕様に基づく1局完全スルーテストと鳴き優先順位テスト
"""
import pytest
from server.game_loop import GameStateMachine, EventType, GameEvent, MatchPhase
from server.tile_wall import TileWall
from server.turn_manager import TurnManager, MeldRequest

pytestmark = pytest.mark.asyncio

def test_full_round_simulation():
    """1局の完全シミュレーション：配牌→打牌→和了/流局→次局"""
    TEST_CONFIG = {}
    game = GameStateMachine(config=TEST_CONFIG)
    wall = TileWall(seed=42)
    wall.build_and_shuffle()
    
    # 2. 配牌・初期状態
    game.process_event(GameEvent(type=EventType.GAME_START))
    assert game.state == MatchPhase.DEALING
    game.process_event(GameEvent(type=EventType.DEAL_COMPLETE))
    assert game.state == MatchPhase.DRAWING
    
    # 3. 模擬プレイヤーによる自動打牌（18巡まで）
    for turn in range(1, 19):
        # 自摸
        tile = wall.draw_tile()
        game.process_event(GameEvent(type=EventType.TILE_DRAWN, tile=tile))
        assert game.state == MatchPhase.DISCARDING
        
        # 打牌
        game.process_event(GameEvent(type=EventType.TILE_DISCARDED, tile=tile))
        assert game.state == MatchPhase.ACTION_CHECK
        
        # 誰も鳴かない
        game.process_event(GameEvent(type=EventType.NO_ACTION))
        assert game.state == MatchPhase.DRAWING
        
        # 流局または和了で終了
        if wall.is_exhausted() or game.is_won():
            break
    
    # 4. 局終了処理
    game.process_event(GameEvent(type=EventType.TILE_DRAWN, tile=wall.draw_tile()))
    game.process_event(GameEvent(type=EventType.WIN_DECLARE))
    assert game.state == MatchPhase.WIN_CHECK
    game.process_event(GameEvent(type=EventType.ROUND_END))
    assert game.state == MatchPhase.ROUND_END
    
    # 5. 結果の整合性検証
    assert game.context.score_updated

def test_meld_priority_resolution():
    """鳴き優先順位の解決ロジックを検証"""
    # 0:親, 1:下家, 2:対面, 3:上家
    manager = TurnManager(player_seats=[0, 1, 2, 3])
    
    # ケース1: ロンとポンが競合 → ロン優先
    requests = [
        MeldRequest(player_idx=1, meld_type='pon', discarded_tile='5m'),
        MeldRequest(player_idx=2, meld_type='ron', discarded_tile='5m'),
    ]
    result = manager.resolve_meld_conflict(requests)
    assert result.meld_type == 'ron'
    assert result.player_idx == 2
    
    # ケース2: ポンとチーが競合 → ポン優先
    requests = [
        MeldRequest(player_idx=1, meld_type='chi', discarded_tile='5m'),
        MeldRequest(player_idx=2, meld_type='pon', discarded_tile='5m'),
    ]
    result = manager.resolve_meld_conflict(requests)
    assert result.meld_type == 'pon'
    
    # ケース3: 同優先度（ポン同士）→ 下家優先
    manager.current_turn_idx = 0  # 放銃者は0番とする
    requests = [
        MeldRequest(player_idx=3, meld_type='pon', discarded_tile='5m'),  # 上家 (距離3)
        MeldRequest(player_idx=1, meld_type='pon', discarded_tile='5m'),  # 下家 (距離1)
    ]
    result = manager.resolve_meld_conflict(requests)
    assert result.player_idx == 1  # 下家が優先
