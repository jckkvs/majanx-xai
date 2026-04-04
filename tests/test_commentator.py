import pytest
from server.engine import GameEngine
from server.commentator import CommentatorAI
from server.models import Tile, TileSuit

def test_commentator_analyze():
    engine = GameEngine()
    engine.start_game()
    comm = CommentatorAI(engine)
    
    # テンパイ手配を作成
    player = engine.state.players[0]
    player.hand = [
        Tile(TileSuit.MAN, 1), Tile(TileSuit.MAN, 2), Tile(TileSuit.MAN, 3),
        Tile(TileSuit.PIN, 4), Tile(TileSuit.PIN, 5), Tile(TileSuit.PIN, 6),
        Tile(TileSuit.SOU, 7), Tile(TileSuit.SOU, 8), Tile(TileSuit.SOU, 9),
        Tile(TileSuit.WIND, 1), Tile(TileSuit.WIND, 1), Tile(TileSuit.WIND, 1),
        Tile(TileSuit.WIND, 2), Tile(TileSuit.WIND, 3) # リャンメン待ち等の余剰牌
    ]
    
    res = comm.analyze(0)
    assert "top3" in res
    assert "explanation" in res
    assert len(res["top3"]) > 0

    # 危険度テスト
    danger = comm._estimate_danger(1, [0]*34, {"is_riichi": False})
    assert danger < 0.2

    danger_riichi = comm._estimate_danger(1, [0]*34, {"is_riichi": True})
    assert danger_riichi >= 0.4

def test_commentator_empty_hand():
    engine = GameEngine()
    engine.start_game()
    comm = CommentatorAI(engine)
    
    engine.state.players[0].hand = []
    res = comm.analyze(0)
    assert len(res["top3"]) == 0
    assert res["explanation"] == "判定不可"

def test_generate_commentary():
    engine = GameEngine()
    comm = CommentatorAI(engine)
    top3_mortal = [
        {"tile_idx": 0, "tile_name": "1m", "prob": 0.8},
        {"tile_idx": 1, "tile_name": "2m", "prob": 0.1}
    ]
    top3_rule = [
        {"tile_idx": 0, "tile_name": "1m", "acceptance": 10, "attack_score": 10.0, "defense_score": 0.1, "balance_score": 1.0},
        {"tile_idx": 1, "tile_name": "2m", "acceptance": 5, "attack_score": 5.0, "defense_score": 0.8, "balance_score": 4.0}
    ]
    exp = comm._generate_dual_commentary(top3_mortal, top3_rule, {"turn": 5, "is_riichi": False})
    assert "is_agree" in exp
    assert exp["is_agree"] is True
    assert "1m" in exp["synthesis"]
