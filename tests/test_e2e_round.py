"""
tests/test_e2e_round.py
MVP用: 簡易文字列JSONインターフェースでのE2Eラウンド進行テスト
"""
import pytest
from server.game_loop import GameLoop

def test_single_round_completion():
    # 1. サーバー起動・WebSocket接続（に代わる初期化）
    game = GameLoop()
    
    # 2. 配牌・手牌表示確認
    snapshot = game.start()
    assert snapshot["game_state"] == "DISCARDING"
    assert len(snapshot["hand"]) == 14
    assert len(snapshot["discards"][0]) == 0
    
    # 3. 18巡分 自動/手動打牌送信
    for _ in range(18):
        if game.state == game.STATE.ROUND_END:
            break
            
        current_seat = game.turn_idx
        # ツモった牌を切る程度の超単純シミュレーション
        if game.players[current_seat].hand:
            first_tile = game.players[current_seat].hand[0]
            game.process_discard(current_seat, first_tile)
            
    # ROUND_END もしくは山切れが近い状態になっているか
    # 18巡×4＝72枚なので、ROUND_ENDにはまだ達しないが、例外なく回ることを確認
    assert game.state in [game.STATE.DISCARDING, game.STATE.ROUND_END]

def test_action_validator():
    from server.action_validator import can_pon, can_chi
    hand = ["1m", "1m", "3m", "4m", "5p"]
    assert can_pon(hand, "1m") == True
    assert can_pon(hand, "3m") == False
    
    # チー (1m, 2m, 3m)
    hand2 = ["1m", "2m", "5p"]
    assert can_chi(hand2, "3m", 1) == True
    assert can_chi(hand2, "3m", 2) == False  # 対面からのチーは不可
