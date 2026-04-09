"""
server/action_validator.py
MVP用簡易鳴き・和了判定
"""

def can_pon(hand: list[str], tile: str) -> bool:
    count = hand.count(tile)
    return count >= 2

def can_chi(hand: list[str], tile: str, seat_diff: int) -> bool:
    if seat_diff != 1:  # 下家からのみ
        return False
    if tile[-1] not in "mps":
        return False
        
    num = int(tile[0])
    suit = tile[-1]
    
    # -2, -1
    if num >= 3 and f"{num-2}{suit}" in hand and f"{num-1}{suit}" in hand:
        return True
    # -1, +1
    if 2 <= num <= 8 and f"{num-1}{suit}" in hand and f"{num+1}{suit}" in hand:
        return True
    # +1, +2
    if num <= 7 and f"{num+1}{suit}" in hand and f"{num+2}{suit}" in hand:
        return True
        
    return False

def can_kan(hand: list[str], tile: str) -> bool:
    return hand.count(tile) >= 3

def can_ron(hand: list[str], tile: str) -> bool:
    # 実際はShantenやAgariを用いるがMVPのためダミーとして常にFalseか、
    # 特定の牌姿だけハードコード対応するかだが、ここでは外部ライブラリ無しで
    # モックとして False を返す。必要なら mahjong lib を呼び出す。
    return False
