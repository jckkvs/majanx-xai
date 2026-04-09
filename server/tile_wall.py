"""
server/tile_wall.py
MVP用: 文字列ベースの牌山・状態管理
"""
import random

class TileWall:
    TOTAL = 136
    DEAD_WALL = 14
    HAND_SIZE = 13
    DEALER_HAND_SIZE = 14

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.wall: list[str] = []
        self.dead_wall: list[str] = []
        self.dora_indicator: str = ""

    def build(self) -> None:
        suits = [f"{r}{s}" for s in "mps" for r in range(1, 10)]
        honors = ["E", "S", "W", "N", "C", "F", "P"]
        self.wall = [t for t in suits + honors for _ in range(4)]
        self.rng.shuffle(self.wall)
        
        self.dead_wall = self.wall[-self.DEAD_WALL:]
        self.wall = self.wall[:-self.DEAD_WALL]
        self.dora_indicator = self.dead_wall[4]

    def draw(self) -> str | None:
        return self.wall.pop() if self.wall else None
        
    def is_exhausted(self) -> bool:
        return len(self.wall) == 0
