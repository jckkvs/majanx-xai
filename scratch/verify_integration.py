from server.game_loop import GameLoop
from server.ensemble_ai import EnsembleAI

def test_integration():
    print("Starting Integration Test...")
    game = GameLoop(seed=123)
    ai = EnsembleAI()
    
    # Start game
    state = game.start()
    print(f"Initial State: {state['game_state']}, Hand: {state['hand']}")
    
    # AI recommendation
    rec = ai.recommend(state, state["hand"], 0)
    print(f"AI Recommendation: {rec}")
    
    # Execute discard
    tile_to_discard = rec["tile"]
    next_state = game.process_discard(0, tile_to_discard)
    print(f"Next State: {next_state['game_state']}, Hand: {next_state['hand']}")
    
    print("Integration Test Passed!")

if __name__ == "__main__":
    test_integration()
