#!/usr/bin/env python3
"""
牌譜からルールを事前生成するスクリプト
"""
from server.rule_engine_2 import RuleGenerator
import os
import json

def create_dummy_haihu():
    """テスト用にダミーの牌譜データを生成する"""
    os.makedirs("haihu", exist_ok=True)
    dummy_data = {
        "rounds": [
            {
                "players": [
                    {
                        "discards": ["1m", "2p", "3s", "1m", "2p", "3s", "1m"],
                        "hand_history": [
                            ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "S", "W", "N"],
                            ["2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "S", "W", "N"],
                            ["3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "S", "W", "N"],
                            ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "S", "W", "N"],
                            ["2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "S", "W", "N"],
                            ["3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "S", "W", "N"],
                            ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "S", "W", "N"],
                        ]
                    }
                ]
            }
        ]
    }
    with open("haihu/dummy.json", "w", encoding="utf-8") as f:
        json.dump(dummy_data, f)
    print("Created dummy haihu file for testing.")

def main():
    print("=" * 60)
    print("牌譜分析ルール生成スクリプト")
    print("=" * 60)
    
    # テスト用のダミー牌譜を生成
    create_dummy_haihu()
    
    generator = RuleGenerator(
        haihu_dir="haihu",
        output_file="server/haihu_rules.json"
    )
    
    generator.generate_all_rules()
    
    print("\nルール生成完了！")
    print("生成されたルールは server/haihu_rules.json に保存されました")

if __name__ == "__main__":
    main()
