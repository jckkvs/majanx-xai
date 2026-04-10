"""
戦略判断ルールエンジン2
牌譜（haihu）フォルダの対局データから自然言語ルールを生成
"""

import json
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path

@dataclass
class HaihuRule:
    pattern_id: str
    situation_desc: str
    recommended_tile: str
    probability: float
    reasoning: str
    success_rate: float
    source_haihu_id: str

class HaihuRuleEngine:
    """牌譜分析ベースのルールエンジン"""
    
    def __init__(self, haihu_dir: str = "haihu"):
        self.haihu_dir = Path(haihu_dir)
        self.rules: List[HaihuRule] = []
        self.pattern_database: Dict[str, List[Dict]] = {}
        
    def load_haihu_files(self):
        """牌譜ファイルを読み込み"""
        if not self.haihu_dir.exists():
            print(f"[Warning] Haihu directory not found: {self.haihu_dir}")
            return
        
        for file_path in self.haihu_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    haihu_data = json.load(f)
                    self._extract_patterns_from_haihu(haihu_data, file_path.stem)
                except json.JSONDecodeError:
                    print(f"[Warning] Failed to parse {file_path}")
    
    def _extract_patterns_from_haihu(self, haihu_data: Dict, haihu_id: str):
        """牌譜からパターンを抽出"""
        for round_data in haihu_data.get("rounds", []):
            self._analyze_round(round_data, haihu_id)
    
    def _analyze_round(self, round_data: Dict, haihu_id: str):
        """一局を分析してルールを生成"""
        for player_idx, player_data in enumerate(round_data.get("players", [])):
            discards = player_data.get("discards", [])
            hand_history = player_data.get("hand_history", [])
            
            for turn, (discard, hand) in enumerate(zip(discards, hand_history)):
                self._analyze_discard(discard, hand, turn, player_idx, haihu_id)
    
    def _analyze_discard(self, discard: str, hand: List[str], turn: int, 
                        player_idx: int, haihu_id: str):
        """打牌を分析してルールを生成"""
        pattern_key = self._create_pattern_key(hand, discard)
        
        if pattern_key not in self.pattern_database:
            self.pattern_database[pattern_key] = []
        
        self.pattern_database[pattern_key].append({
            "discard": discard,
            "turn": turn,
            "player_idx": player_idx,
            "haihu_id": haihu_id,
            "result": self._get_round_result(haihu_id, player_idx)
        })
    
    def _create_pattern_key(self, hand: List[str], discard: str) -> str:
        """手牌パターンのキーを生成"""
        sorted_hand = sorted(hand)
        return f"{'_'.join(sorted_hand)}_{discard}"
    
    def _get_round_result(self, haihu_id: str, player_idx: int) -> Dict:
        """局の結果を取得（あがり/振り込み/流局など）"""
        return {"result": "unknown"}  # ダミー実装
    
    def generate_rules_from_patterns(self):
        """パターンデータベースからルールを生成"""
        for pattern_key, instances in self.pattern_database.items():
            if len(instances) < 3:  # 3回未満のパターンは除外
                continue
            
            discard_counts = {}
            success_counts = {}
            
            for inst in instances:
                discard = inst["discard"]
                discard_counts[discard] = discard_counts.get(discard, 0) + 1
                
                if inst["result"]["result"] in ["win", "tsumo", "ron"]:
                    success_counts[discard] = success_counts.get(discard, 0) + 1
            
            best_discard = max(discard_counts.keys(), key=lambda x: discard_counts[x])
            total_count = len(instances)
            success_count = success_counts.get(best_discard, 0)
            success_rate = success_count / total_count if total_count > 0 else 0
            
            reasoning = self._generate_natural_language_reasoning(
                pattern_key, best_discard, discard_counts, success_rate
            )
            
            rule = HaihuRule(
                pattern_id=pattern_key[:20],
                situation_desc=self._describe_situation(pattern_key),
                recommended_tile=best_discard,
                probability=discard_counts[best_discard] / total_count,
                reasoning=reasoning,
                success_rate=success_rate,
                source_haihu_id=instances[0]["haihu_id"]
            )
            
            self.rules.append(rule)
            
        print(f"Generated {len(self.rules)} rules from Haifu.")
    
    def _generate_natural_language_reasoning(self, pattern_key: str, discard: str,
                                           discard_counts: Dict, success_rate: float) -> str:
        """自然言語で理由を生成"""
        total = sum(discard_counts.values())
        count = discard_counts[discard]
        percentage = (count / total * 100) if total > 0 else 0
        
        reasoning_parts = []
        if percentage >= 70:
            reasoning_parts.append(f"この手牌では{discard}切りが圧倒的（{percentage:.1f}%）")
        elif percentage >= 50:
            reasoning_parts.append(f"この手牌では{discard}切りが最も多い（{percentage:.1f}%）")
        else:
            reasoning_parts.append(f"{discard}切りも選択肢の一つ（{percentage:.1f}%）")
        
        if success_rate >= 0.4:
            reasoning_parts.append(f"成功率{success_rate*100:.1f}%と良好")
        elif success_rate >= 0.2:
            reasoning_parts.append(f"成功率{success_rate*100:.1f}%")
        else:
            reasoning_parts.append(f"成功率は{success_rate*100:.1f}%と低め")
        
        return "。".join(reasoning_parts) + "。"
    
    def _describe_situation(self, pattern_key: str) -> str:
        """局面を自然言語で説明"""
        return f"手牌パターン: {pattern_key[:50]}..."
    
    def evaluate(self, game_state: Dict, hand_tiles: List[str]) -> List[HaihuRule]:
        """現在の手牌に適合するルールを検索"""
        pattern_key = self._create_pattern_key(hand_tiles, "")
        
        matching_rules = []
        for rule in self.rules:
            if self._is_similar_pattern(pattern_key, rule.pattern_id):
                matching_rules.append(rule)
        
        matching_rules.sort(key=lambda x: x.probability, reverse=True)
        return matching_rules[:5]
    
    def _is_similar_pattern(self, pattern1: str, pattern2: str) -> bool:
        """パターンが類似しているか判定"""
        return pattern1[:20] == pattern2[:20] or pattern2[:20] in pattern1

class RuleGenerator:
    """牌譜からルールを事前生成するスクリプト"""
    
    def __init__(self, haihu_dir: str = "haihu", output_file: str = "haihu_rules.json"):
        self.engine = HaihuRuleEngine(haihu_dir)
        self.output_file = output_file
    
    def generate_all_rules(self):
        print("[RuleGenerator] Loading haihu files...")
        self.engine.load_haihu_files()
        
        print("[RuleGenerator] Generating rules from patterns...")
        self.engine.generate_rules_from_patterns()
        
        print(f"[RuleGenerator] Generated {len(self.engine.rules)} rules")
        
        rules_data = [
            {
                "pattern_id": rule.pattern_id,
                "situation_desc": rule.situation_desc,
                "recommended_tile": rule.recommended_tile,
                "probability": rule.probability,
                "reasoning": rule.reasoning,
                "success_rate": rule.success_rate,
                "source_haihu_id": rule.source_haihu_id
            }
            for rule in self.engine.rules
        ]
        
        # Ensure directory exists for output_file if needed
        os.makedirs(os.path.dirname(os.path.abspath(self.output_file)), exist_ok=True)
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
        
        print(f"[RuleGenerator] Saved to {self.output_file}")
        self._print_statistics()
    
    def _print_statistics(self):
        if not self.engine.rules:
            return
        
        avg_prob = sum(r.probability for r in self.engine.rules) / len(self.engine.rules)
        avg_success = sum(r.success_rate for r in self.engine.rules) / len(self.engine.rules)
        
        print(f"\n=== Rule Statistics ===")
        print(f"Total rules: {len(self.engine.rules)}")
        print(f"Average probability: {avg_prob:.2%}")
        print(f"Average success rate: {avg_success:.2%}")
        print(f"======================\n")
