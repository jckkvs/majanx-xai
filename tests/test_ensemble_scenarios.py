import pytest
from server.models import GameState, PlayerState, Tile, Wind, tile_from_str
from server.round_context import MatchConfig
from server.ensemble_ai import EnsembleAI
from server.strategy_engine import StrategyEngine

def setup_dummy_game(turn: int, is_riichi_others: bool, rank: int, dealer_seat: int) -> GameState:
    gs = GameState()
    gs.turn_count = turn
    gs.round_number = 3
    gs.dealer = dealer_seat
    gs.current_player = 0
    gs.bakaze = Wind.EAST
    
    # プレイヤーのモック
    p1 = PlayerState(seat=0)
    p1.score = [30000, 20000, 40000, 10000][rank - 1] # 順位に応じた点数
    p1.is_riichi = False
    p1.wind = Wind.EAST
    p1.discards = []
    p1.melds = []
    p1.recent_discards = []
    
    p2 = PlayerState(seat=1)
    p2.score = 25000
    p2.is_riichi = is_riichi_others
    p2.wind = Wind.SOUTH
    p2.discards = []
    p2.melds = []
    p2.recent_discards = []
    
    p3 = PlayerState(seat=2)
    p3.score = 25000
    p3.is_riichi = False
    p3.wind = Wind.WEST
    p3.discards = []
    p3.melds = []
    p3.recent_discards = []
    
    p4 = PlayerState(seat=3)
    p4.score = 25000
    p4.is_riichi = False
    p4.wind = Wind.NORTH
    p4.discards = []
    p4.melds = []
    p4.recent_discards = []

    gs.players = [p1, p2, p3, p4]
    return gs

def test_case_a_late_turn_riichi():
    """ケースA: 南4局(ラウンド3としてモック)、トップ目、他家リーチあり -> DEFEND"""
    gs = setup_dummy_game(turn=12, is_riichi_others=True, rank=1, dealer_seat=1)
    cfg = MatchConfig()
    
    # 安牌と危険牌
    hand = [tile_from_str("1m"), tile_from_str("2m"), tile_from_str("1z")] # 1zは安全とみなされる(risk_assessor内で)
    candidates = hand
    
    ensemble = EnsembleAI(strategy=StrategyEngine())
    result = ensemble.recommend(gs, cfg, hand, candidates)
    
    assert result.strategy_output.strategy_type == "DEFEND"

def test_case_b_early_turn_dealer():
    """ケースB: 東1局、親番(dealer_seat=0)、序盤 -> SPEED/ATTACK"""
    gs = setup_dummy_game(turn=4, is_riichi_others=False, rank=2, dealer_seat=0)
    cfg = MatchConfig()
    
    hand = [tile_from_str("1m"), tile_from_str("5p")]
    candidates = hand
    
    ensemble = EnsembleAI(strategy=StrategyEngine())
    result = ensemble.recommend(gs, cfg, hand, candidates)
    
    assert result.strategy_output.strategy_type == "SPEED"

def test_case_c_last_place_push():
    """ケースC: ラス確定目前(4位)、オーラス(kyoku=4) -> ATTACK"""
    gs = setup_dummy_game(turn=8, is_riichi_others=False, rank=4, dealer_seat=1)
    gs.round_number = 4
    cfg = MatchConfig()
    
    hand = [tile_from_str("1m"), tile_from_str("5p")]
    candidates = hand
    
    ensemble = EnsembleAI(strategy=StrategyEngine())
    result = ensemble.recommend(gs, cfg, hand, candidates)
    
    assert result.strategy_output.strategy_type == "ATTACK"
