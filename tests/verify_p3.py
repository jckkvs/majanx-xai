# tests/verify_p3.py
import httpx
import json
import asyncio

async def main():
    url = "http://127.0.0.1:8000/api/v1/inference/suggest"
    payload = {
        "state": {
            "hand": ["1m", "2m", "3m", "5p", "5p", "7s", "8s", "9s", "2z", "3z", "4z", "5z", "6z"],
            "context": {"round": "東2", "score_diff": -5000, "is_dealer": False, "turn_count": 8}
        },
        "engine": "ensemble"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=5.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print("--- Response Structure ---")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Validation
                expl = data.get("explanation", {})
                if expl.get("summary") and expl.get("technical_factors") and expl.get("strategic_factors"):
                    print("\n✅ SUCCESS: Hierarchical structure confirmed.")
                else:
                    print("\n❌ FAILURE: Missing explanation tiers.")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
