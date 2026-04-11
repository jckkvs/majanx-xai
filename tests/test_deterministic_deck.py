from server.core.deterministic_deck import DeterministicDeck

def test_deterministic_deck():
    d1 = DeterministicDeck(12345)
    tiles1 = d1.draw(14)
    d2 = DeterministicDeck(12345)
    tiles2 = d2.draw(14)
    
    assert tiles1 == tiles2
    assert d1.verify_integrity() is True
