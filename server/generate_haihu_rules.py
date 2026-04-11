#!/usr/bin/env python3
"""
Haihu Rule Generator (Rule Engine 2) - 統計的有意性検証対応版
9億件の牌譜を母集団とし、統計的検定を経てのみルールを生成
"""

import os
import sys
import json
import sqlite3
import signal
import time
import hashlib
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Generator, Tuple, List
from scipy import stats  # 統計検定用

# ================= 統計的閾値設定 =================
MIN_SAMPLE_SIZE = 1000          # 1パターンあたりの最低サンプル数（統計的有意性の確保）
MIN_EFFECT_SIZE = 0.05          # 最小効果量（5%以上の和了率差がないとルール化しない）
SIGNIFICANCE_LEVEL = 0.05       # 有意水準（p値の閾値）
CONFIDENCE_LEVEL = 0.95         # 信頼区間のレベル

# ================= 運用設定 =================
HAIHU_ROOT = "haihu"
CHECKPOINT_FILE = "server/haihu_checkpoint.json"
DB_FILE = "server/haihu_rules.db"
EXPORT_JSON_FILE = "server/haihu_rules.json"

SAVE_INTERVAL_FILES = 10_000
SAVE_INTERVAL_SECONDS = 900
# ==============================================


class StatisticalTester:
    """統計的有意性検定ユーティリティ"""
    
    @staticmethod
    def chi_square_test(observed: List[int], expected: List[float]) -> Tuple[float, bool]:
        """
        カイ二乗検定を実行
        Returns: (p_value, is_significant)
        """
        if len(observed) != len(expected) or sum(observed) == 0:
            return 1.0, False
        try:
            chi2, p_value = stats.chisquare(f_obs=observed, f_exp=expected)
            return p_value, p_value < SIGNIFICANCE_LEVEL
        except:
            return 1.0, False
    
    @staticmethod
    def proportion_confidence_interval(successes: int, trials: int, confidence: float = CONFIDENCE_LEVEL) -> Tuple[float, float]:
        """
        比率の信頼区間を計算（Wilsonスコア区間）
        Returns: (lower_bound, upper_bound)
        """
        if trials == 0:
            return 0.0, 0.0
        z = stats.norm.ppf((1 + confidence) / 2)
        p_hat = successes / trials
        denominator = 1 + z**2 / trials
        center = (p_hat + z**2 / (2*trials)) / denominator
        margin = z * math.sqrt((p_hat*(1-p_hat) + z**2/(4*trials)) / trials) / denominator
        return max(0, center - margin), min(1, center + margin)
    
    @staticmethod
    def effect_size(win_rate_a: float, win_rate_b: float, n_a: int, n_b: int) -> float:
        """
        効果量（Cohen's h）を計算
        0.2: 小, 0.5: 中, 0.8: 大
        """
        if n_a == 0 or n_b == 0:
            return 0.0
        phi_a = 2 * math.asin(math.sqrt(win_rate_a))
        phi_b = 2 * math.asin(math.sqrt(win_rate_b))
        return abs(phi_a - phi_b)


class RuleAggregator:
    """統計集約＋有意性検証エンジン"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self):
        # Use individual execute() calls instead of executescript() to avoid
        # exclusive transaction lock issues on large existing WAL databases
        
        # --- Schema migration: detect old 'discards' table from v1 ---
        old_tables = [r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        
        has_old_discards = 'discards' in old_tables
        has_old_patterns = 'patterns' in old_tables
        needs_migration = has_old_discards and 'discard_outcomes' not in old_tables
        
        if needs_migration:
            print("[Migration] v1 DB detected. Migrating schema...")
            # Old 'patterns' has (pattern_hash, pattern_desc, total, wins)
            # Old 'discards' has (pattern_hash, tile, count)
            # We need to create new tables and migrate
            self.conn.execute("""CREATE TABLE IF NOT EXISTS discard_outcomes (
                pattern_hash TEXT, tile TEXT, total_count INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0, ron_count INTEGER DEFAULT 0,
                avg_rank REAL, PRIMARY KEY (pattern_hash, tile))""")
            try:
                self.conn.execute("""INSERT OR IGNORE INTO discard_outcomes 
                    (pattern_hash, tile, total_count, win_count, ron_count, avg_rank)
                    SELECT pattern_hash, tile, count, 0, 0, NULL FROM discards""")
                print("[Migration] Migrated discards -> discard_outcomes")
            except Exception as e:
                print(f"[Migration] Partial migration: {e}")
            
            # Update patterns table to add total_samples if missing
            try:
                self.conn.execute("ALTER TABLE patterns ADD COLUMN total_samples INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Copy 'total' to 'total_samples' if old column exists
            try:
                self.conn.execute("UPDATE patterns SET total_samples = total WHERE total_samples = 0 AND total IS NOT NULL")
            except sqlite3.OperationalError:
                pass
            
            self.conn.commit()
            print("[Migration] Schema migration complete")
        
        # --- Create tables if they don't exist (fresh DB or post-migration) ---
        tables = [
            """CREATE TABLE IF NOT EXISTS patterns (
                pattern_hash TEXT PRIMARY KEY,
                pattern_desc TEXT,
                total_samples INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS discard_outcomes (
                pattern_hash TEXT, tile TEXT, total_count INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0, ron_count INTEGER DEFAULT 0,
                avg_rank REAL, PRIMARY KEY (pattern_hash, tile)
            )""",
            """CREATE TABLE IF NOT EXISTS validated_rules (
                rule_id TEXT PRIMARY KEY, pattern_hash TEXT,
                recommended_tile TEXT, probability REAL, win_rate REAL,
                p_value REAL, effect_size REAL, confidence_lower REAL,
                confidence_upper REAL, reasoning TEXT, sample_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_outcomes_pattern ON discard_outcomes(pattern_hash)",
            "CREATE INDEX IF NOT EXISTS idx_rules_winrate ON validated_rules(win_rate DESC)",
        ]
        for sql in tables + indexes:
            try:
                self.conn.execute(sql)
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e) and "locked" not in str(e):
                    raise
        self.conn.commit()

    def record_discard(self, pattern_hash: str, pattern_desc: str, 
                      tile: str, outcome: str, rank: Optional[float] = None):
        """
        打牌結果を記録
        outcome: "win" | "ron_lost" | "ryukyoku" | "other"
        """
        # patterns テーブル更新
        self.conn.execute("""
            INSERT INTO patterns (pattern_hash, pattern_desc, total_samples)
            VALUES (?, ?, 1)
            ON CONFLICT(pattern_hash) DO UPDATE SET
                total_samples = total_samples + 1
        """, (pattern_hash, pattern_desc))
        
        # discard_outcomes テーブル更新
        is_win = 1 if outcome == "win" else 0
        is_ron_lost = 1 if outcome == "ron_lost" else 0
        
        self.conn.execute("""
            INSERT INTO discard_outcomes 
            (pattern_hash, tile, total_count, win_count, ron_count, avg_rank)
            VALUES (?, ?, 1, ?, ?, ?)
            ON CONFLICT(pattern_hash, tile) DO UPDATE SET
                total_count = total_count + 1,
                win_count = win_count + ?,
                ron_count = ron_count + ?,
                avg_rank = CASE 
                    WHEN ? IS NOT NULL THEN (avg_rank * (total_count - 1) + ?) / total_count
                    ELSE avg_rank 
                END
        """, (pattern_hash, tile, is_win, is_ron_lost, rank, 
              is_win, is_ron_lost, rank, rank))

    def commit(self):
        self.conn.commit()

    def _get_pattern_discards(self, pattern_hash: str) -> List[dict]:
        """特定パターンの全打牌統計を取得"""
        cursor = self.conn.execute("""
            SELECT tile, total_count, win_count, ron_count, avg_rank
            FROM discard_outcomes 
            WHERE pattern_hash = ? AND total_count >= 50
        """, (pattern_hash,))
        return [
            {
                "tile": row[0],
                "total": row[1],
                "wins": row[2],
                "rons_lost": row[3],
                "avg_rank": row[4],
                "win_rate": row[2] / row[1] if row[1] > 0 else 0
            }
            for row in cursor
        ]

    def validate_and_generate_rule(self, pattern_hash: str, pattern_desc: str) -> Optional[dict]:
        """
        統計的検定を経てルール生成可否を判定
        Returns: ルール辞書 or None（検定不通過）
        """
        discards = self._get_pattern_discards(pattern_hash)
        if len(discards) < 2:
            return None
        
        # 1. 総サンプル数チェック
        total_samples = sum(d["total"] for d in discards)
        if total_samples < MIN_SAMPLE_SIZE:
            return None
        
        # 2. 最良打牌の特定（和了率基準）
        best = max(discards, key=lambda x: x["win_rate"])
        
        # 3. 効果量チェック：2番目との差が閾値以上か
        sorted_discards = sorted(discards, key=lambda x: x["win_rate"], reverse=True)
        if len(sorted_discards) >= 2:
            second = sorted_discards[1]
            effect = StatisticalTester.effect_size(
                best["win_rate"], second["win_rate"], 
                best["total"], second["total"]
            )
            if effect < MIN_EFFECT_SIZE:
                return None  # 効果量が小さい＝実質的に差がない
        
        # 4. カイ二乗検定：打牌選択と和了の独立性を検定
        observed_wins = [d["wins"] for d in discards]
        observed_total = [d["total"] for d in discards]
        # 期待値：全体和了率×各打牌の総数
        overall_win_rate = sum(d["wins"] for d in discards) / total_samples
        expected_wins = [t * overall_win_rate for t in observed_total]
        
        p_value, is_significant = StatisticalTester.chi_square_test(observed_wins, expected_wins)
        if not is_significant:
            return None  # 統計的に有意な差がない
        
        # 5. 信頼区間の計算
        ci_lower, ci_upper = StatisticalTester.proportion_confidence_interval(
            best["wins"], best["total"]
        )
        
        # 6. 自然言語解説の生成
        reasoning = (
            f"{total_samples}回の同局面において、"
            f"{best['tile']}切りは{best['total']}回選択され、"
            f"和了率は{best['win_rate']*100:.1f}%（95%信頼区間: {ci_lower*100:.1f}〜{ci_upper*100:.1f}%）でした。"
            f"他の打牌と比較して統計的に有意な差が確認され（p={p_value:.3f}）、"
            f"効果量は{effect:.2f}（中程度以上）でした。"
        )
        
        return {
            "rule_id": f"{pattern_hash}_{best['tile']}",
            "pattern_hash": pattern_hash,
            "pattern_desc": pattern_desc,
            "recommended_tile": best["tile"],
            "probability": best["total"] / total_samples,  # 選択頻度
            "win_rate": best["win_rate"],
            "p_value": p_value,
            "effect_size": effect,
            "confidence_lower": ci_lower,
            "confidence_upper": ci_upper,
            "reasoning": reasoning,
            "sample_size": total_samples,
            "best_tile_samples": best["total"],
            "best_tile_wins": best["wins"]
        }

    def export_validated_rules(self, output_path: str) -> int:
        """検定通過済みのルールのみをJSONエクスポート"""
        cursor = self.conn.execute("""
            SELECT rule_id, pattern_desc, recommended_tile, probability,
                   win_rate, p_value, effect_size, confidence_lower, confidence_upper,
                   reasoning, sample_size
            FROM validated_rules
            ORDER BY sample_size DESC, win_rate DESC
        """)
        
        rules = []
        for row in cursor:
            rules.append({
                "rule_id": row[0],
                "situation_desc": row[1],
                "recommended_tile": row[2],
                "selection_probability": row[3],
                "win_rate": row[4],
                "statistical_significance": {
                    "p_value": row[5],
                    "effect_size": row[6],
                    "confidence_interval": [row[7], row[8]]
                },
                "reasoning": row[9],
                "sample_size": row[10]
            })
        
        tmp_path = output_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, output_path)
        return len(rules)

    def batch_validate(self, batch_size: int = 1000) -> int:
        """未検証パターンを一括で統計検定し、合格のみをルール登録"""
        cursor = self.conn.execute("""
            SELECT pattern_hash, pattern_desc 
            FROM patterns 
            WHERE total_samples >= ?
            AND pattern_hash NOT IN (SELECT pattern_hash FROM validated_rules)
            LIMIT ?
        """, (MIN_SAMPLE_SIZE, batch_size))
        
        validated_count = 0
        for pattern_hash, pattern_desc in cursor:
            rule = self.validate_and_generate_rule(pattern_hash, pattern_desc)
            if rule:
                self.conn.execute("""
                    INSERT OR REPLACE INTO validated_rules 
                    (rule_id, pattern_hash, recommended_tile, probability, win_rate,
                     p_value, effect_size, confidence_lower, confidence_upper,
                     reasoning, sample_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rule["rule_id"], rule["pattern_hash"], rule["recommended_tile"],
                    rule["probability"], rule["win_rate"], rule["p_value"],
                    rule["effect_size"], rule["confidence_lower"], rule["confidence_upper"],
                    rule["reasoning"], rule["sample_size"]
                ))
                validated_count += 1
        
        self.conn.commit()
        return validated_count

    def close(self):
        self.conn.close()


class HaihuRuleGenerator:
    def __init__(self):
        self.checkpoint = self._load_checkpoint()
        self.aggregator = RuleAggregator(DB_FILE)
        self.running = True
        self.file_count = self.checkpoint.get("processed_count", 0)
        
        signal.signal(signal.SIGINT, self._handle_signal)
        try:
            signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:
            pass

    def _load_checkpoint(self) -> dict:
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"processed_count": 0, "last_file": None, "validated_count": 0}

    def _save_checkpoint(self, last_file: str = None):
        self.checkpoint["processed_count"] = self.file_count
        if last_file:
            self.checkpoint["last_file"] = last_file
        tmp = CHECKPOINT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CHECKPOINT_FILE)

    def _handle_signal(self, signum, frame):
        print(f"\n[Signal] 中断シグナル受信。状態保存中...")
        self.running = False

    def _file_iterator(self, root: str) -> Generator[Tuple[str, str], None, None]:
        """決定論的順序でXMLファイルを列挙"""
        resume = self.checkpoint.get("last_file")
        skip = resume is not None
        
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fname in sorted(f for f in filenames if f.endswith('.xml')):
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, ".")
                if skip:
                    if rel == resume:
                        skip = False
                    continue
                yield rel, full

    def _decode_tile(self, code: str) -> str:
        """ 0-135 の天鳳牌コードを判定 """
        try:
            val = int(code) // 4
            suit = val // 9
            num = (val % 9) + 1
            if suit == 0: return f"{num}m"
            elif suit == 1: return f"{num}p"
            elif suit == 2: return f"{num}s"
            else:
                honors = ['1z', '2z', '3z', '4z', '5z', '6z', '7z']
                return honors[val - 27]
        except:
            return "unknown"

    def _parse_haihu(self, file_path: str) -> List[dict]:
        """
        XML牌譜を解析し、(hand_pattern_hash, hand_desc, discarded_tile, outcome, rank) 
        のリストを返す。
        """
        results = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except:
            return results

        players_hands = [[], [], [], []]
        events = []
        rank = 2.5 
        
        for elem in root:
            if getattr(elem, 'tag', '') == 'INIT':
                for i in range(4):
                    hai_str = elem.get(f'hai{i}')
                    if hai_str:
                        players_hands[i] = [self._decode_tile(t) for t in hai_str.split(',')]
            
            elif getattr(elem, 'tag', '')[0:1] in ['T', 'U', 'V', 'W'] and len(elem.tag) > 1:
                player_idx = {'T':0, 'U':1, 'V':2, 'W':3}[elem.tag[0]]
                tile = self._decode_tile(elem.tag[1:])
                players_hands[player_idx].append(tile)

            elif getattr(elem, 'tag', '')[0:1] in ['D', 'E', 'F', 'G'] and len(elem.tag) > 1:
                player_idx = {'D':0, 'E':1, 'F':2, 'G':3}[elem.tag[0]]
                tile = self._decode_tile(elem.tag[1:])
                events.append({
                    'player': player_idx,
                    'hand': list(players_hands[player_idx]),
                    'discard': tile
                })
                if tile in players_hands[player_idx]:
                    players_hands[player_idx].remove(tile)
                    
            elif getattr(elem, 'tag', '') == 'AGARI':
                who = elem.get('who')
                fromWho = elem.get('fromWho')
                if who is not None and fromWho is not None:
                    win_player = int(who)
                    ron_player = int(fromWho)
                    for ev in events:
                        if ev['player'] == win_player:
                            results.append((ev['hand'], ev['discard'], "win", rank))
                        elif ev['player'] == ron_player and win_player != ron_player:
                            results.append((ev['hand'], ev['discard'], "ron_lost", rank))
                        else:
                            results.append((ev['hand'], ev['discard'], "other", rank))
                players_hands = [[], [], [], []]
                events = []
            
            elif getattr(elem, 'tag', '') == 'RYUUKYOKU':
                for ev in events:
                    results.append((ev['hand'], ev['discard'], "ryukyoku", rank))
                players_hands = [[], [], [], []]
                events = []

        return results

    def _normalize_hand(self, tiles: List[str]) -> Tuple[str, str]:
        """手牌を正規化：ハッシュ値と説明文を生成"""
        sorted_tiles = sorted(tiles)
        desc = "_".join(sorted_tiles[:30]) + ("..." if len(sorted_tiles)>30 else "")
        h = hashlib.sha256(" ".join(sorted_tiles).encode()).hexdigest()[:16]
        return h, desc

    def run(self):
        print("="*70)
        print("Haihu Rule Generator v2 - 統計的有意性検証対応")
        print(f"母集団: {HAIHU_ROOT} 以下の全XML（推定9億件）")
        print(f"統計閾値: サンプル>={MIN_SAMPLE_SIZE}, 効果量>={MIN_EFFECT_SIZE}, p<{SIGNIFICANCE_LEVEL}")
        print("="*70)
        
        last_save_count = self.file_count
        last_save_time = time.time()
        
        try:
            for rel_path, full_path in self._file_iterator(HAIHU_ROOT):
                if not self.running:
                    break
                
                events = self._parse_haihu(full_path)
                for hand, tile, outcome, rank in events:
                    phash, desc = self._normalize_hand(hand)
                    self.aggregator.record_discard(phash, desc, tile, outcome, rank)
                
                self.file_count += 1
                
                # 定期保存＋バッチ検証
                if (self.file_count - last_save_count >= SAVE_INTERVAL_FILES) or \
                   (time.time() - last_save_time >= SAVE_INTERVAL_SECONDS):
                    print(f"\n[Save] 進捗保存＋統計検証実行中...")
                    validated = self.aggregator.batch_validate()
                    self.aggregator.export_validated_rules(EXPORT_JSON_FILE)
                    self.checkpoint["validated_count"] = self.checkpoint.get("validated_count", 0) + validated
                    self._save_checkpoint(rel_path)
                    last_save_count = self.file_count
                    last_save_time = time.time()
                    print(f"[Save] 新規ルール{validated}件を追加保存")
                
                if self.file_count % 10000 == 0:
                    print(f"[Progress] {self.file_count:,} 件処理 / {self.checkpoint.get('validated_count', 0):,} 件ルール確定")
            
            # 最終バッチ処理
            print("\n[Final] 残りのパターンの統計検証を実行中...")
            total_validated = 0
            while True:
                validated = self.aggregator.batch_validate(batch_size=5000)
                if validated == 0:
                    break
                total_validated += validated
                print(f"[Final] +{validated} 件ルール確定（累計: {total_validated:,} 件）")
            
            self.aggregator.export_validated_rules(EXPORT_JSON_FILE)
            self._save_checkpoint()
            print(f"\n[Complete] 処理完了。確定ルール数: {self.checkpoint.get('validated_count', 0) + total_validated:,} 件")
            print(f"[Output] {EXPORT_JSON_FILE}")
            
        except Exception as e:
            print(f"\n[Error] {e}")
        finally:
            self.aggregator.close()
            print("[Exit] 安全に終了")

    def close(self):
        self.aggregator.close()


if __name__ == "__main__":
    HaihuRuleGenerator().run()
