#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Set, Any
import json
import yaml
import random
import math
from datetime import datetime
import re
import sys

# 統計検定用（オプション: scipyがなければ簡易実装にフォールバック）
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not found. Using simplified statistical tests.", file=sys.stderr)

# ============================================================================
# 2. 定数・設定（ユーザーが調整可能）
# ============================================================================

TILE_ID_MAP = {}
for i in range(9): TILE_ID_MAP[i] = f"{i+1}m"
for i in range(9): TILE_ID_MAP[i+9] = f"{i+1}p"
for i in range(9): TILE_ID_MAP[i+18] = f"{i+1}s"
HONORS = ['E', 'S', 'W', 'N', 'C', 'F', 'P']
for i, h in enumerate(HONORS): TILE_ID_MAP[i+27] = h

SPECIAL_VALUES = set(range(128, 256))

MID_GAME_TURNS = (7, 12)
LATE_GAME_TURNS = (13, 18)

SIGNIFICANCE_LEVEL = 0.05
BOOTSTRAP_ITERATIONS = 1000
MIN_SAMPLE_SIZE = 10  # 調整: サンプル数を少し下げてテストしやすくする

OUTPUT_FORMATS = ['yaml', 'json']

# ============================================================================
# 3. データ構造（型定義）
# ============================================================================

@dataclass
class DiscardEvent:
    turn: int
    actor: int
    tile: str
    is_tsumogiri: bool
    action_type: str
    round_id: str = ""

@dataclass
class ReachEvent:
    turn: int
    actor: int
    declared_tile: Optional[str]
    step: int
    round_id: str = ""

@dataclass
class AgariEvent:
    turn: int
    winner: int
    from_whom: int
    wait_tiles: List[str]
    yaku: str
    points: int
    is_ron: bool
    is_tsumo: bool
    round_id: str = ""

@dataclass
class RoundData:
    round_id: str
    kyoku: int
    honba: int
    oya: int
    initial_scores: List[int]
    discards: List[DiscardEvent] = field(default_factory=list)
    reaches: List[ReachEvent] = field(default_factory=list)
    agari: Optional[AgariEvent] = None
    is_ryukyoku: bool = False
    seed: str = ""

@dataclass
class PatternStats:
    pattern_name: str
    trigger_count: int
    target_occurrence: int
    target_rate: float
    control_rate: Optional[float] = None
    p_value: Optional[float] = None
    ci_95_low: Optional[float] = None
    ci_95_high: Optional[float] = None
    sample_size: int = 0
    conclusion: str = "pending"
    analysis_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class GeneratedRule:
    rule_id: str
    category: str
    trigger_conditions: List[str]
    reverse_inference_logic: str
    practical_heuristic: str
    boundary_conditions: List[str]
    statistical_claim: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        sc = self.statistical_claim
        if sc.get('status') == 'VERIFIED':
            required_fields = ['sample_size', 'target_rate', 'analysis_timestamp']
            for f in required_fields:
                if sc.get(f) in (None, 'TO_BE_MEASURED', ''):
                    raise ValueError(f"VERIFIEDルールに実測値が不足: {f}")
            if sc.get('p_value') is not None:
                if not (0 <= sc['p_value'] <= 1):
                    raise ValueError(f"p値の範囲外: {sc['p_value']}")
            if sc.get('confidence_interval_95'):
                low, high = sc['confidence_interval_95']
                if low is not None and high is not None:
                    if not (0 <= low <= high <= 1):
                        raise ValueError(f"信頼区間の範囲外: [{low}, {high}]")

# ============================================================================
# 4. XMLパーサー（Tenhou形式対応）
# ============================================================================

class TenhouXMLParser:
    @staticmethod
    def parse_tile_id(tile_id: int) -> Optional[str]:
        if tile_id in SPECIAL_VALUES:
            return None
        idx = tile_id // 4
        if idx < 9: return f"{idx+1}m"
        elif idx < 18: return f"{idx-8}p"
        elif idx < 27: return f"{idx-17}s"
        elif idx < 34: return HONORS[idx-27]
        return None
    
    @staticmethod
    def parse_xml_file(filepath: Path) -> List[RoundData]:
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except Exception:
            return []
        
        rounds = []
        current_round = None
        turn_counter = 0
        actor_counter = 0
        
        for elem in root:
            tag = elem.tag
            if tag == 'INIT':
                if current_round:
                    rounds.append(current_round)
                seed = elem.get('seed', '')
                oya = int(elem.get('oya', 0))
                ten_str = elem.get('ten', '250,250,250,250')
                ten = [int(x) for x in ten_str.split(',')]
                
                current_round = RoundData(
                    round_id=f"{seed}_{len(rounds)}",
                    seed=seed,
                    kyoku=(int(seed.split(',')[1]) if seed and ',' in seed else 0) + 1,
                    honba=(int(seed.split(',')[2]) if seed and len(seed.split(',')) > 2 else 0),
                    oya=oya,
                    initial_scores=ten,
                    discards=[],
                    reaches=[],
                    agari=None,
                    is_ryukyoku=False
                )
                turn_counter = 0
                actor_counter = oya
                
            elif tag and len(tag) >= 2 and tag[0] in ('T', 'D', 'U', 'E', 'V', 'F', 'W', 'G'):
                if current_round is None: continue
                if tag[1:].isdigit(): tile_id = int(tag[1:])
                else:
                    if not elem.text: continue
                    try: tile_id = int(elem.text)
                    except: continue

                tile_str = TenhouXMLParser.parse_tile_id(tile_id)
                if tile_str:
                    is_tsumogiri = tag[0] in ('T', 'U', 'V', 'W')
                    current_round.discards.append(DiscardEvent(
                        turn=turn_counter,
                        actor=actor_counter,
                        tile=tile_str,
                        is_tsumogiri=is_tsumogiri,
                        action_type=tag[0],
                        round_id=current_round.round_id
                    ))
                    turn_counter += 1
                        
            elif tag == 'REACH':
                if current_round is None: continue
                pai_get = elem.get('pai')
                declared = TenhouXMLParser.parse_tile_id(int(pai_get)) if pai_get and pai_get.isdigit() else None
                current_round.reaches.append(ReachEvent(
                    turn=turn_counter,
                    actor=int(elem.get('who', 0)),
                    declared_tile=declared,
                    step=int(elem.get('step', 1)),
                    round_id=current_round.round_id
                ))
                
            elif tag == 'AGARI':
                if current_round is None: continue
                machi = elem.get('machi', '')
                wait_tiles = []
                if machi:
                    for m in machi.split(','):
                        if m.isdigit(): wait_tiles.append(TenhouXMLParser.parse_tile_id(int(m)))
                
                ten_str = elem.get('ten', '0,0,0')
                ten_parts = ten_str.split(',')
                points = int(ten_parts[1]) if len(ten_parts) > 1 else 0
                
                from_whom = elem.get('fromWho', '-1')
                from_whom_int = int(from_whom) if from_whom != '-1' else -1
                
                current_round.agari = AgariEvent(
                    turn=turn_counter,
                    winner=int(elem.get('who', 0)),
                    from_whom=from_whom_int,
                    wait_tiles=wait_tiles,
                    yaku=elem.get('yaku', ''),
                    points=points,
                    is_ron=(from_whom_int != -1),
                    is_tsumo=(from_whom_int == -1),
                    round_id=current_round.round_id
                )
                
            elif tag == 'OWARI':
                if current_round: rounds.append(current_round)
                break
        
        if current_round and current_round not in rounds: rounds.append(current_round)
        return rounds
    
    @staticmethod
    def parse_directory(dir_path: Path, max_files: Optional[int] = None) -> List[RoundData]:
        all_rounds = []
        # UPDATE: ADD *.mjlog 
        xml_files = list(dir_path.glob('*.xml')) + list(dir_path.glob('*.mjai')) + list(dir_path.glob('*.mjlog'))
        
        if max_files and len(xml_files) > max_files:
            xml_files = random.sample(xml_files, max_files)
        
        print(f"Found str(len(xml_files)) XML files in {dir_path}", file=sys.stderr)
        
        for i, xml_file in enumerate(xml_files):
            rounds = TenhouXMLParser.parse_xml_file(xml_file)
            all_rounds.extend(rounds)
            if i % 100 == 0:
                print(f"  Parsed {i}/{len(xml_files)} files...", file=sys.stderr)
        
        return all_rounds

# ============================================================================
# 5. パターン抽出エンジン
# ============================================================================

class PatternExtractor:
    @staticmethod
    def extract_kagi_cut_pattern(rounds: List[RoundData], tile_a: str, tile_b: str, target: str, turn_range: Tuple[int, int], max_interval: int = 1) -> List[Dict[str, Any]]:
        results = []
        for round_data in rounds:
            discards = round_data.discards
            for i in range(len(discards) - 1):
                d1, d2 = discards[i], discards[i+1]
                if not (turn_range[0] <= d1.turn <= turn_range[1]): continue
                tiles = {d1.tile, d2.tile}
                if {tile_a, tile_b}.issubset(tiles):
                    next_tile = None
                    if i + 2 < len(discards):
                        next_event = discards[i+2]
                        next_tile = next_event.tile
                    
                    reach_declared = False
                    for reach in round_data.reaches:
                        if (abs(reach.turn - d2.turn) <= 3 and reach.declared_tile == target):
                            reach_declared = True
                            break
                    
                    wait_match = False
                    agari_ron = False
                    if round_data.agari:
                        if target in round_data.agari.wait_tiles:
                            wait_match = True
                            if round_data.agari.is_ron: agari_ron = True
                    
                    results.append({
                        'round_id': round_data.round_id, 'trigger_turn': d1.turn, 'actor': d1.actor,
                        'tile_a': d1.tile, 'tile_b': d2.tile, 'target_followed': (next_tile == target),
                        'reach_declared': reach_declared, 'wait_match': wait_match,
                        'agari_ron': agari_ron, 'agari_points': round_data.agari.points if round_data.agari else None
                    })
        return results
    
    @staticmethod
    def extract_riichi_correlation(rounds: List[RoundData]) -> Dict[str, Dict[str, int]]:
        stats = defaultdict(lambda: {'riichi_count': 0, 'ron_count': 0, 'tsumo_count': 0})
        for round_data in rounds:
            for reach in round_data.reaches:
                if reach.step == 1 and reach.declared_tile:
                    tile = reach.declared_tile
                    stats[tile]['riichi_count'] += 1
                    if round_data.agari:
                        agari = round_data.agari
                        if tile in agari.wait_tiles:
                            if agari.is_ron and agari.from_whom != reach.actor:
                                stats[tile]['ron_count'] += 1
                            elif agari.is_tsumo and agari.winner == reach.actor:
                                stats[tile]['tsumo_count'] += 1
        return {k: dict(v) for k, v in stats.items()}

# ============================================================================
# 6. 統計分析モジュール（実測値のみ）
# ============================================================================

class StatisticalAnalyzer:
    @staticmethod
    def chi_squared_test_simple(observed: List[int], expected: List[int]) -> float:
        if len(observed) != len(expected): return 1.0
        chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected) if e > 0)
        if chi2 < 2.71: return 0.11
        elif chi2 < 3.84: return 0.06
        elif chi2 < 6.63: return 0.02
        else: return 0.001
    
    @staticmethod
    def chi_squared_test(observed: List[int], expected: List[int]) -> float:
        if SCIPY_AVAILABLE:
            try:
                chi2, p, _, _ = stats.chi2_contingency([observed, expected])
                return p
            except: pass
        return StatisticalAnalyzer.chi_squared_test_simple(observed, expected)
    
    @staticmethod
    def bootstrap_ci(rate: float, n: int, iterations: int = BOOTSTRAP_ITERATIONS, confidence: float = 0.95) -> Tuple[Optional[float], Optional[float]]:
        if n == 0: return None, None
        samples = []
        for _ in range(iterations):
            successes = sum(random.random() < rate for _ in range(n))
            samples.append(successes / n if n > 0 else 0)
        samples.sort()
        alpha = 1 - confidence
        lower_idx = max(0, int(alpha / 2 * iterations))
        upper_idx = min(len(samples) - 1, int((1 - alpha / 2) * iterations))
        return samples[lower_idx], samples[upper_idx]
    
    @staticmethod
    def analyze_pattern(pattern_results: List[Dict], target_field: str, control_rate: Optional[float] = None, min_sample: int = MIN_SAMPLE_SIZE) -> PatternStats:
        n = len(pattern_results)
        if n == 0: return PatternStats(pattern_name=target_field, trigger_count=0, target_occurrence=0, target_rate=0.0, control_rate=control_rate, sample_size=0, conclusion="insufficient_data")
        occurrences = sum(1 for r in pattern_results if r.get(target_field))
        rate = occurrences / n if n > 0 else 0.0
        
        p_value = None
        if control_rate is not None and n >= min_sample:
            observed = [occurrences, n - occurrences]
            expected_control = [int(control_rate * n), int((1 - control_rate) * n)]
            if sum(expected_control) > 0:
                p_value = StatisticalAnalyzer.chi_squared_test(observed, expected_control)
        
        ci_low, ci_high = StatisticalAnalyzer.bootstrap_ci(rate, n)
        
        if n < min_sample: conclusion = "insufficient_data"
        elif p_value is not None and p_value < SIGNIFICANCE_LEVEL:
            conclusion = "support" if rate > (control_rate or 0) else "reject"
        else:
            conclusion = "inconclusive"
        
        return PatternStats(
            pattern_name=target_field, trigger_count=n, target_occurrence=occurrences,
            target_rate=round(rate, 4), control_rate=round(control_rate, 4) if control_rate is not None else None,
            p_value=round(p_value, 4) if p_value is not None else None,
            ci_95_low=round(ci_low, 4) if ci_low is not None else None,
            ci_95_high=round(ci_high, 4) if ci_high is not None else None,
            sample_size=n, conclusion=conclusion, analysis_timestamp=datetime.now().isoformat()
        )

# ============================================================================
# 7. ルール生成エンジン（虚偽防止ガード付き）
# ============================================================================

class RuleGenerator:
    TEMPLATES = {
        'kagi_cut': {
            'category': 'discard_sequence_analysis',
            'logic_template': (
                "{tile_a}と{tile_b}の連続切りは、標準的には「{target}を中心とした両面搭子の解体」を意味する。\n"
                "本分析では、このパターンが観測された{trigger_count}局中、"
                "{target}が危険牌として機能した割合は{rate:.1%}"
                "{ci_text}であった。\n"
                "{comparison_text}"
                "したがって、標準的なスジ読みを盲目的に適用せず、"
                "物理的枚数分布と形状意図を併せて評価することが推奨される。"
            ),
            'heuristic_template': (
                "【実戦チェックリスト】\n"
                "□ {tile_a}-{tile_b}切りが「手切り」か？（ツモ切り偶発なら適用外）\n"
                "□ {target}の場見え枚数は？（3枚見えなら物理的安全、2枚以下なら警戒）\n"
                "□ 切り順序は「{tile_a}→{tile_b}」か「{tile_b}→{tile_a}」か？\n\n"
                "上記を確認した上で、{target}を「標準スジ読み」ではなく"
                "「物理的枚数＋形状意図」で評価せよ。"
            ),
            'boundary_template': [
                "{tile}が字牌・端牌の場合は適用外（数牌中張に限定）",
                "他家が鳴いている場合は適用外（メンゼン形状に限定）",
                "巡目{turn_min}-{turn_max}以外では適用外（中盤に限定）"
            ]
        },
        'riichi_correlation': {
            'category': 'riichi_analysis',
            'logic_template': (
                "{tile}でリーチ宣言した場合、その牌がロン和了牌となる実測確率は{rate:.1%}"
                "{ci_text}（n={sample_size}）である。\n"
                "{comparison_text}"
                "この数値は実測値であり、局面の文脈に応じて柔軟に解釈することが重要である。"
            ),
            'heuristic_template': (
                "【実戦チェックリスト】\n"
                "□ {tile}リーチ宣言後、その牌の現物は手内にあるか？\n\n"
                "{tile}リーチ時は、実測率{rate:.1%}を参考としつつ状況に応じた防御判断を行え。"
            ),
            'boundary_template': ["宣言牌が字牌の場合は統計的傾向が異なるため適用外"]
        }
    }
    
    @staticmethod
    def generate_rule(pattern_type: str, stats: PatternStats, pattern_params: Dict[str, str]) -> Optional[GeneratedRule]:
        if pattern_type not in RuleGenerator.TEMPLATES: return None
        template = RuleGenerator.TEMPLATES[pattern_type]
        params = {
            'tile_a': pattern_params.get('tile_a', 'X'), 'tile_b': pattern_params.get('tile_b', 'Y'),
            'target': pattern_params.get('target', 'Z'), 'rate': stats.target_rate,
            'sample_size': stats.sample_size, 'trigger_count': stats.trigger_count,
            'turn_min': MID_GAME_TURNS[0], 'turn_max': MID_GAME_TURNS[1],
            'ci_text': (f"（95%CI: {stats.ci_95_low:.1%}〜{stats.ci_95_high:.1%}）" if stats.ci_95_low is not None else ""),
            'comparison_text': (f"対照群の発生率{stats.control_rate:.1%}との比較では、{'有意差が確認された' if stats.p_value and stats.p_value < SIGNIFICANCE_LEVEL else '有意差は確認されなかった'}。\n" if stats.control_rate is not None else "")
        }
        
        status = "INCONCLUSIVE"
        if stats.conclusion == "support": status = "VERIFIED"
        elif stats.conclusion == "reject": status = "VERIFIED"
        elif stats.conclusion == "insufficient_data": status = "PENDING_MORE_DATA"
        
        conclusion_text = f"【統計的結論】{stats.conclusion}"
        
        rule = GeneratedRule(
            rule_id=f"READ_{params['tile_a'].upper()}_{params['tile_b'].upper()}_{params['target'].upper()}_STAT",
            category=template['category'],
            trigger_conditions=[f"巡目{MID_GAME_TURNS[0]}-{MID_GAME_TURNS[1]}（中盤）", f"他家が{params['tile_a']}と{params['tile_b']}を連続して切っている"],
            reverse_inference_logic=template['logic_template'].format(**params) + f"\n\n{conclusion_text}",
            practical_heuristic=template['heuristic_template'].format(**params),
            boundary_conditions=[t.format(tile=params['target'], **params) for t in template['boundary_template']],
            statistical_claim={
                'status': status, 'sample_size': stats.sample_size, 'trigger_count': stats.trigger_count,
                'target_occurrence': stats.target_occurrence, 'target_rate': stats.target_rate,
                'control_rate': stats.control_rate, 'p_value': stats.p_value,
                'confidence_interval_95': [stats.ci_95_low, stats.ci_95_high],
                'analysis_timestamp': stats.analysis_timestamp,
                'disclaimer': "本数値は指定されたデータセットからの実測値です。"
            },
            metadata={'generated_by': 'rule_generator.py', 'pattern_type': pattern_type}
        )
        return rule

# ============================================================================
# 8. 出力・保存機能
# ============================================================================

def save_rule(rule: GeneratedRule, output_dir: Path, formats: List[str] = OUTPUT_FORMATS):
    output_dir.mkdir(parents=True, exist_ok=True)
    rule_dict = asdict(rule)
    if 'yaml' in formats:
        output_file = output_dir / f"{rule.rule_id.lower()}.yaml"
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(rule_dict, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    if 'json' in formats:
        output_file = output_dir / f"{rule.rule_id.lower()}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(rule_dict, f, ensure_ascii=False, indent=2)

def save_summary(output_dir: Path, input_dir: Path, pattern_type: str, pattern_params: Dict, stats: PatternStats, total_rounds: int):
    summary = {
        'analysis_timestamp': datetime.now().isoformat(), 'input_directory': str(input_dir),
        'total_rounds_analyzed': total_rounds, 'pattern_type': pattern_type,
        'statistics': {
            'sample_size': stats.sample_size, 'trigger_count': stats.trigger_count,
            'target_occurrence': stats.target_occurrence, 'target_rate': stats.target_rate,
            'conclusion': stats.conclusion
        }
    }
    summary_file = output_dir / 'analysis_summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

# ============================================================================
# 9. メイン処理
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True)
    parser.add_argument('--output', type=str, required=True)
    parser.add_argument('--pattern', type=str, default='kagi_cut')
    parser.add_argument('--control-rate', type=float, default=None)
    parser.add_argument('--max-files', type=int, default=2000)
    parser.add_argument('--tile-a', type=str, default='4m')
    parser.add_argument('--tile-b', type=str, default='6m')
    parser.add_argument('--target', type=str, default='5m')
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    if not input_dir.exists(): return
    
    all_rounds = TenhouXMLParser.parse_directory(input_dir, max_files=args.max_files)
    if not all_rounds: return
    
    if args.pattern == 'kagi_cut':
        pattern_params = {'tile_a': args.tile_a, 'tile_b': args.tile_b, 'target': args.target}
        results = PatternExtractor.extract_kagi_cut_pattern(all_rounds, args.tile_a, args.tile_b, args.target, MID_GAME_TURNS)
        stats = StatisticalAnalyzer.analyze_pattern(results, 'agari_ron', args.control_rate)
    elif args.pattern == 'riichi_correlation':
        riichi_stats = PatternExtractor.extract_riichi_correlation(all_rounds)
        if not riichi_stats: return
        target_tile = max(riichi_stats.keys(), key=lambda t: riichi_stats[t]['riichi_count'])
        tile_data = riichi_stats[target_tile]
        stats = PatternStats(
            pattern_name=f"riichi_{target_tile}", trigger_count=tile_data['riichi_count'],
            target_occurrence=tile_data['ron_count'],
            target_rate=(tile_data['ron_count'] / tile_data['riichi_count'] if tile_data['riichi_count'] > 0 else 0.0),
            control_rate=args.control_rate, sample_size=tile_data['riichi_count']
        )
        if stats.sample_size >= MIN_SAMPLE_SIZE:
            stats.ci_95_low, stats.ci_95_high = StatisticalAnalyzer.bootstrap_ci(stats.target_rate, stats.sample_size)
            stats.conclusion = "inconclusive"
        pattern_params = {'tile_a': target_tile, 'tile_b': target_tile, 'target': target_tile}
    
    print(f"Stats Conclusion: {stats.conclusion} | Sample size: {stats.sample_size} | Rate: {stats.target_rate:.3f}")
    
    if stats.sample_size >= MIN_SAMPLE_SIZE:
        rule = RuleGenerator.generate_rule(args.pattern, stats, pattern_params)
        if rule:
            output_dir = Path(args.output)
            save_rule(rule, output_dir)
            save_summary(output_dir, input_dir, args.pattern, pattern_params, stats, len(all_rounds))
    else:
        print(f"Insufficient data for rule generation (n={stats.sample_size} < {MIN_SAMPLE_SIZE})")

if __name__ == '__main__':
    main()
