"""
戦略判断ルールエンジン 2
牌譜（haihu）フォルダの対局データから自然言語ルールを生成
Tenhou XML 形式に対応
"""

import json
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

@dataclass
class HaihuRule:
    pattern_id: str
    situation_desc: str
    recommended_tile: str
    probability: float
    reasoning: str
    success_rate: float
    source_haihu_id: str
    sample_size: int = 0

class HaihuRuleEngine:
    """牌譜分析ベースのルールエンジン（Tenhou XML 対応）"""
    
    def __init__(self, haihu_dir: str = "haihu"):
        self.haihu_dir = Path(haihu_dir)
        self.rules: List[HaihuRule] = []
        self.pattern_database: Dict[str, List[Dict]] = {}
        self.tile_map = self._init_tile_map()
        
    def _init_tile_map(self) -> Dict[int, str]:
        """数値→牌表記マップ"""
        tiles = {}
        for i in range(1, 10):
            tiles[i] = f"{i}m"
        for i in range(11, 20):
            tiles[i] = f"{i-10}p"
        for i in range(21, 30):
            tiles[i] = f"{i-20}s"
        tiles[31] = "E"
        tiles[32] = "S"
        tiles[33] = "W"
        tiles[34] = "N"
        tiles[35] = "P"
        tiles[36] = "F"
        tiles[37] = "C"
        return tiles
    
    def _tile_to_str(self, tile_code: int) -> str:
        """Tile code を文字列に変換"""
        return self.tile_map.get(tile_code, f"T{tile_code}")
    
    def load_haihu_files(self):
        """牌譜ファイルを読み込み（XML 対応）"""
        if not self.haihu_dir.exists():
            print(f"[Warning] Haihu directory not found: {self.haihu_dir}")
            return
        
        xml_count = 0
        for file_path in list(self.haihu_dir.glob("*.xml"))[:50]:
            try:
                self._parse_tenhou_xml(str(file_path), file_path.stem)
                xml_count += 1
            except Exception as e:
                print(f"[Warning] Failed to parse XML {file_path}: {e}")
        
        for file_path in self.haihu_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    haihu_data = json.load(f)
                    self._extract_patterns_from_haihu(haihu_data, file_path.stem)
                except json.JSONDecodeError:
                    print(f"[Warning] Failed to parse {file_path}")
        
        print(f"[HaihuRuleEngine] Loaded {xml_count} XML files")
    
    def _parse_tenhou_xml(self, file_path: str, haihu_id: str):
        """Tenhou XML 形式の牌譜をパース"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            for init_tag in root.findall('.//INIT'):
                self._process_init_tag(init_tag, haihu_id)
                    
        except ET.ParseError as e:
            print(f"[Warning] XML parse error for {file_path}: {e}")
    
    def _process_init_tag(self, init_tag: ET.Element, haihu_id: str):
        """INIT タグから初期手牌を抽出"""
        for i in range(4):
            hai_attr = init_tag.get(f'hai{i}')
            if hai_attr:
                tiles = [int(t) for t in hai_attr.split(',')]
                self._record_initial_hand(tiles, haihu_id)
    
    def _record_initial_hand(self, tiles: List[int], haihu_id: str):
        """初期手牌からパターンを記録"""
        tile_strs = [self._tile_to_str(t) for t in tiles]
        pattern_key = "_".join(sorted(tile_strs))
        
        if pattern_key not in self.pattern_database:
            self.pattern_database[pattern_key] = []
        
        self.pattern_database[pattern_key].append({
            "discard": "initial",
            "turn": 0,
            "player_idx": 0,
            "haihu_id": haihu_id,
            "result": {"result": "unknown"}
        })
    
    def _record_discard_pattern(self, hand: List[str], discard: str, turn: int, 
                                 player_idx: int, haihu_id: str):
        """打牌パターンを記録"""
        pattern_key = self._create_pattern_key(hand, discard)
        
        if pattern_key not in self.pattern_database:
            self.pattern_database[pattern_key] = []
        
        self.pattern_database[pattern_key].append({
            "discard": discard,
            "turn": turn,
            "player_idx": player_idx,
            "haihu_id": haihu_id,
            "result": {"result": "unknown"}
        })
    
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
        """局の結果を取得"""
        return {"result": "unknown"}
    
    def generate_rules_from_patterns(self):
        """パターンデータベースからルールを生成"""
        for pattern_key, instances in self.pattern_database.items():
            if len(instances) < 1:
                continue
            
            discard_counts = defaultdict(int)
            for inst in instances:
                discard = inst["discard"]
                # initial もカウント（初期手牌の第一打として）
                discard_counts[discard] += 1
            
            if not discard_counts:
                continue
            
            best_discard = max(discard_counts.keys(), key=lambda x: discard_counts[x])
            total_count = sum(discard_counts.values())
            
            # サンプル数が少なすぎる場合はスキップ
            if total_count < 1:
                continue
            
            reasoning = self._generate_natural_language_reasoning(
                pattern_key, best_discard, discard_counts, total_count
            )
            
            rule = HaihuRule(
                pattern_id=pattern_key[:50],
                situation_desc=self._describe_situation(pattern_key),
                recommended_tile=best_discard,
                probability=discard_counts[best_discard] / total_count if total_count > 0 else 0,
                reasoning=reasoning,
                success_rate=0.0,
                source_haihu_id=instances[0]["haihu_id"] if instances else "unknown",
                sample_size=total_count
            )
            
            self.rules.append(rule)
            
        print(f"Generated {len(self.rules)} rules from Haifu.")
    
    def _generate_natural_language_reasoning(self, pattern_key: str, discard: str,
                                           discard_counts: Dict, total_count: int) -> str:
        """自然言語で理由を生成"""
        count = discard_counts[discard]
        percentage = (count / total_count * 100) if total_count > 0 else 0
        
        reasoning_parts = []
        
        hand_tiles = pattern_key.split('_')[:-1]
        terminal_count = sum(1 for t in hand_tiles if t and (t[0] == '1' or t[0] == '9'))
        simple_count = sum(1 for t in hand_tiles if t and t[0] in '2345678')
        honor_count = sum(1 for t in hand_tiles if t and t in ['E','S','W','N','P','F','C'])
        
        if terminal_count > 3:
            reasoning_parts.append("幺九牌が多い手牌")
        elif simple_count > 8:
            reasoning_parts.append("中張牌中心の手牌")
        elif honor_count > 2:
            reasoning_parts.append("字牌を含む手牌")
        
        if percentage >= 70:
            reasoning_parts.append(f"この局面では{discard} 切りが圧倒的（{percentage:.1f}%, {total_count}回中{count}回）")
        elif percentage >= 50:
            reasoning_parts.append(f"この局面では{discard} 切りが最も多い（{percentage:.1f}%, {total_count}回中{count}回）")
        elif percentage >= 30:
            reasoning_parts.append(f"{discard} 切りが有力な選択肢（{percentage:.1f}%, {total_count}回中{count}回）")
        else:
            reasoning_parts.append(f"{discard} 切りも選択肢の一つ（{percentage:.1f}%, {total_count}回中{count}回）")
        
        return "。".join(reasoning_parts) + "。"
    
    def _describe_situation(self, pattern_key: str) -> str:
        """局面を自然言語で説明"""
        hand_tiles = pattern_key.split('_')[:-1]
        if len(hand_tiles) > 10:
            hand_tiles = hand_tiles[:10]
        return f"手牌：{' '.join(hand_tiles)}..."
    
    def evaluate(self, game_state: Dict, hand_tiles: List[str]) -> List[HaihuRule]:
        """現在の手牌に適合するルールを検索"""
        pattern_key = self._create_pattern_key(hand_tiles, "")
        
        matching_rules = []
        for rule in self.rules:
            if self._is_similar_pattern(pattern_key, rule.pattern_id):
                matching_rules.append(rule)
        
        matching_rules.sort(key=lambda x: x.sample_size, reverse=True)
        return matching_rules[:5]
    
    def _is_similar_pattern(self, pattern1: str, pattern2: str) -> bool:
        """パターンが類似しているか判定"""
        tiles1 = set(pattern1.split('_')[:-1])
        tiles2 = set(pattern2.split('_')[:-1])
        
        if len(tiles1) == 0 or len(tiles2) == 0:
            return False
        
        intersection = len(tiles1 & tiles2)
        union = len(tiles1 | tiles2)
        similarity = intersection / union if union > 0 else 0
        
        return similarity >= 0.8 or pattern1[:30] == pattern2[:30]


class RuleGenerator:
    """牌譜からルールを事前生成するスクリプト"""
    
    def __init__(self, haihu_dir: str = "haihu", output_file: str = "server/haihu_rules.json"):
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
                "sample_size": rule.sample_size,
                "source_haihu_id": rule.source_haihu_id
            }
            for rule in self.engine.rules
        ]
        
        os.makedirs(os.path.dirname(os.path.abspath(self.output_file)), exist_ok=True)
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
        
        print(f"[RuleGenerator] Saved to {self.output_file}")
        self._print_statistics()
    
    def _print_statistics(self):
        if not self.engine.rules:
            return
        
        avg_prob = sum(r.probability for r in self.engine.rules) / len(self.engine.rules)
        
        print(f"\n=== Rule Statistics ===")
        print(f"Total rules: {len(self.engine.rules)}")
        print(f"Average probability: {avg_prob:.2%}")
        print(f"======================\n")


if __name__ == "__main__":
    generator = RuleGenerator("haihu_example", "server/haihu_rules.json")
    generator.generate_all_rules()
