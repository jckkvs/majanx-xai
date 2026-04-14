# scripts/benchmark_jantama.py
import json
import statistics
import time
import os
from pathlib import Path
import sys

# Ensure the parent directory is in the path so we can import from server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.ensemble_ai import EnsembleAI

def calculate_latency_p95(latencies):
    if not latencies:
        return 0.0
    return statistics.quantiles(latencies, n=100, method='inclusive')[94]

def calculate_match_rate(results):
    if not results:
        return 0.0
    return statistics.mean([r["match"] for r in results])

def run_benchmark(model_path: str, replay_dir: Path, n_samples: int = 5000):
    ai = EnsembleAI(model_path)
    results = []
    
    # If directory doesn't exist, use mock data to verify execution structure
    if not replay_dir.exists() or not list(replay_dir.glob("*.json")):
        print(f"Directory {replay_dir} not found or empty. Using mock benchmark data.")
        mock_state = {
            "turn": 5, "score_diff": -1000, "rank": 3, "hand": ["1m", "2m", "3m", "4p", "5p", "6p", "1z", "1z"],
            "riichi_players": [], "turn": 5, "discard_player": None
        }
        for i in range(100): # Small sample size for testing
            mock_action = {"tile": "1z"}
            pred = ai.recommend(mock_state, mock_state["hand"], 0)
            results.append({
                "correct": mock_action,
                "predicted": pred,
                "latency": pred["latency_ms"],
                "match": pred["tile"] == mock_action.get("tile", "")
            })
    else:
        for replay_file in replay_dir.glob("*.json"):
            with open(replay_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for turn in data.get("turns", []):
                if turn.get("actor") != 0: continue
                state = turn["state"]
                correct_action = turn["action"]
                
                pred = ai.recommend(state, state.get("hand", []), 0)
                results.append({
                    "correct": correct_action,
                    "predicted": pred,
                    "latency": pred["latency_ms"],
                    "match": pred["tile"] == correct_action.get("tile", "") or 
                             pred.get("action") == correct_action.get("action", "")
                })
                if len(results) >= n_samples:
                    break
            if len(results) >= n_samples:
                break
                
    match_rate = calculate_match_rate(results)
    p95_lat = calculate_latency_p95([r["latency"] for r in results])
    
    print(f"Match Rate: {match_rate:.3f} | P95 Latency: {p95_lat:.1f}ms")
    
    # Jantama target thresholds
    if match_rate < 0.75:
        print(f"WARNING: Match rate {match_rate} below 0.75 threshold")
    if p95_lat > 20.0:
        print(f"WARNING: Latency {p95_lat}ms exceeds 20.0ms limit")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Jantama Standard Benchmark")
    parser.add_argument("--model", type=str, default="", help="Path to model weights")
    parser.add_argument("--replays", type=str, default="logs/replays", help="Directory containing replay JSONs")
    parser.add_argument("--samples", type=int, default=5000, help="Number of samples to evaluate")
    args = parser.parse_args()
    
    run_benchmark(args.model, Path(args.replays), args.samples)
