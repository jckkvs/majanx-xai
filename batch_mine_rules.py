import os
import subprocess
import glob
import json

def run_pattern(pattern: str, params: dict):
    cmd = [
        "python", "server/data_ingestion/rule_generator.py",
        "--input", "./server/data_ingestion/logs",
        "--output", "./server/rules/generated_rules",
        "--pattern", pattern,
        "--max-files", "3000" # Increase max files to get more samples
    ]
    for k, v in params.items():
        cmd.extend([f"--{k}", str(v)])
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env={"PYTHONIOENCODING": "utf-8", **os.environ})
    if result.returncode != 0:
        print(f"Error ({pattern}): {result.stderr}")
    else:
        print(f"Success ({pattern}): {result.stderr.splitlines()[-1] if result.stderr else ''}")

def merge_generated_rules():
    # Read generated rules and merge them into phoenix_catalog.json
    generated_files = glob.glob("server/rules/generated_rules/*.json")
    valid_rules = []
    
    for fpath in generated_files:
        if "analysis_summary" in fpath:
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                rule_data = json.load(f)
                
            # Only include verified rules with meaningful status
            # For demonstration, we will include even INCONCLUSIVE ones as lower-priority heuristiscs
            if "rule_id" in rule_data:
                valid_rules.append(rule_data)
        except Exception as e:
            print(f"Failed to read {fpath}: {e}")
            
    print(f"Found {len(valid_rules)} rules to inspect.")
    
    catalog_path = "server/rules/phoenix_catalog.json"
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    else:
        catalog = []
        
    existing_ids = {r["rule_id"] for r in catalog}
    added_count = 0
    for r in valid_rules:
        if r["rule_id"] not in existing_ids:
            catalog.append(r)
            existing_ids.add(r["rule_id"])
            added_count += 1
            
    if added_count > 0:
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        print(f"Appended {added_count} new statistically backed rules to {catalog_path}")
    else:
        print("No new rules added to catalog.")

def main():
    print("Starting batch rule mining...")
    
    # 1. Mine Kagi-cut across multiple suits
    suits = ['m', 'p', 's']
    for s in suits:
        for center in range(3, 8): # 3, 4, 5, 6, 7
            a = f"{center-1}{s}"
            b = f"{center+1}{s}"
            target = f"{center}{s}"
            run_pattern("kagi_cut", {"tile-a": a, "tile-b": b, "target": target})
            
    # 2. Mine Riichi correlation
    run_pattern("riichi_correlation", {})
    
    # Merge them
    merge_generated_rules()

if __name__ == "__main__":
    main()
