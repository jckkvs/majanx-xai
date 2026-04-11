import hashlib
import struct
from typing import List, Tuple

class DeterministicDeck:
    def __init__(self, seed: int):
        self._state = seed & 0xFFFFFFFF
        self._deck: List[str] = self._generate_deck()
        self._hash: str = ""
        self._shuffled: List[str] = self._shuffle()
        self._consumed: List[str] = []

    def _generate_deck(self) -> List[str]:
        suits = ['m', 'p', 's']
        deck = [f"{s}{n}" for s in suits for n in range(1, 10)] * 4
        deck.extend([f"{i}z" for i in range(1, 8)] * 4)
        return deck

    def _xorshift32(self) -> int:
        self._state ^= (self._state << 13) & 0xFFFFFFFF
        self._state ^= (self._state >> 17) & 0xFFFFFFFF
        self._state ^= (self._state << 5) & 0xFFFFFFFF
        return self._state & 0xFFFFFFFF

    def _shuffle(self) -> List[str]:
        deck = self._deck.copy()
        for i in range(len(deck) - 1, 0, -1):
            j = self._xorshift32() % (i + 1)
            deck[i], deck[j] = deck[j], deck[i]
        self._hash = hashlib.sha256("".join(deck).encode()).hexdigest()
        return deck

    def draw(self, count: int = 1) -> List[str]:
        tiles = self._shuffled[:count]
        self._shuffled = self._shuffled[count:]
        self._consumed.extend(tiles)
        return tiles

    def verify_integrity(self) -> bool:
        current_hash = hashlib.sha256("".join(self._consumed + self._shuffled).encode()).hexdigest()
        return current_hash == self._hash
