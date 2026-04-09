import os
import glob
import json
import concurrent.futures
from typing import List, Dict, Any
try:
    from .mjlog_parser import MjlogParser
except ImportError:
    from mjlog_parser import MjlogParser

class StatisticalAnalyzer:
    """
    大量の mjlog XML 形式ファイルをパースし、
    鳳凰・特上等の基礎統計データ（アガリ率、放銃率、立直率など）
    および定性的傾向を抽出する。
    """
    def __init__(self, data_dirs: List[str] = None):
        self.data_dirs = data_dirs or ["haihu_example", "C:/Users/horie/majang/haihu", "server/data_ingestion/logs"]
        self.parser = MjlogParser()
        
        # グローバルな集計変数
        self.global_stats = {
            "total_games": 0,
            "total_kyokus": 0,
            "total_reaches": 0,
            "total_naki": 0,
            "total_agari_tsumo": 0,
            "total_agari_ron": 0,
            "total_ryuukyoku": 0,
            "total_discards": 0,
            "total_tsumo_turns": 0
        }

    def run_pipeline(self) -> Dict[str, Any]:
        all_files = []
        for d in self.data_dirs:
            if os.path.exists(d):
                all_files.extend(glob.glob(os.path.join(d, "*.xml")))
                all_files.extend(glob.glob(os.path.join(d, "*.mjlog")))
        
        # 重複削除
        all_files = list(set(all_files))
        print(f"Found {len(all_files)} total log files for analysis.")

        if not all_files:
            print("No log files found in specified directories.")
            return self.global_stats

        # 並列処理で全ファイルをパースして統計を集計する
        # ファイル数が多いため上限を設けるかChunksで行う
        # 今回はデモ＋MVPのためProcessPoolExecutorを使用
        
        processed_count = 0
        # 簡易実装：メモリに乗せるため順次処理またはバッチ（最大数万）
        # Pythonの速度だと1万件のXMLパースで数分程度
        with concurrent.futures.ProcessPoolExecutor() as executor:
            chunk_size = 1000
            futures = [executor.submit(self._process_single_file, f) for f in all_files]
            
            for future in concurrent.futures.as_completed(futures):
                stats = future.result()
                self._merge_stats(stats)
                processed_count += 1
                if processed_count % 1000 == 0:
                    print(f"[{processed_count}/{len(all_files)}] files processed...")

        self.global_stats["total_games"] = processed_count
        self._calculate_rates()
        return self.global_stats

    def _process_single_file(self, filepath: str) -> Dict[str, Any]:
        """個別のファイルをパースして、その1半荘分の統計結果を返す"""
        parser = MjlogParser() # マルチプロセスのためのインスタンス
        events = parser.parse_file(filepath)
        
        stats = {
            "kyokus": 0,
            "reaches": 0,
            "naki": 0,
            "agari_tsumo": 0,
            "agari_ron": 0,
            "ryuukyoku": 0,
            "discards": 0,
            "tsumo_turns": 0
        }

        for ev in events:
            t = ev.get("type", "")
            if t == "start_kyoku":
                stats["kyokus"] += 1
            elif t == "reach" and ev.get("step") == 1:
                stats["reaches"] += 1
            elif t == "naki":
                stats["naki"] += 1
            elif t == "dahai":
                stats["discards"] += 1
            elif t == "tsumo":
                stats["tsumo_turns"] += 1
            elif t == "end_kyoku":
                reason = ev.get("reason", "")
                if reason == "AGARI":
                    who = ev.get("who", -1)
                    from_who = ev.get("fromWho", -1)
                    if who == from_who:
                        stats["agari_tsumo"] += 1
                    else:
                        stats["agari_ron"] += 1
                elif reason == "RYUUKYOKU":
                    stats["ryuukyoku"] += 1

        return stats

    def _merge_stats(self, partial_stats: Dict[str, Any]):
        self.global_stats["total_kyokus"] += partial_stats.get("kyokus", 0)
        self.global_stats["total_reaches"] += partial_stats.get("reaches", 0)
        self.global_stats["total_naki"] += partial_stats.get("naki", 0)
        self.global_stats["total_agari_tsumo"] += partial_stats.get("agari_tsumo", 0)
        self.global_stats["total_agari_ron"] += partial_stats.get("agari_ron", 0)
        self.global_stats["total_ryuukyoku"] += partial_stats.get("ryuukyoku", 0)
        self.global_stats["total_discards"] += partial_stats.get("discards", 0)
        self.global_stats["total_tsumo_turns"] += partial_stats.get("tsumo_turns", 0)

    def _calculate_rates(self):
        """絶対数から相対的な「率」を計算する（1局あたり、1巡あたり等）"""
        k = self.global_stats["total_kyokus"] or 1
        t = self.global_stats["total_tsumo_turns"] or 1

        self.global_stats["metrics"] = {
            "avg_reach_per_kyoku": self.global_stats["total_reaches"] / k,
            "avg_naki_per_kyoku": self.global_stats["total_naki"] / k,
            "agari_tsumo_rate_per_kyoku": self.global_stats["total_agari_tsumo"] / k,
            "agari_ron_rate_per_kyoku": self.global_stats["total_agari_ron"] / k,
            "ryuukyoku_rate": self.global_stats["total_ryuukyoku"] / k,
            # ツモ/ロンの比率
            "tsumo_win_ratio": self.global_stats["total_agari_tsumo"] / (self.global_stats["total_agari_tsumo"] + self.global_stats["total_agari_ron"] + 1)
        }

if __name__ == "__main__":
    analyzer = StatisticalAnalyzer()
    results = analyzer.run_pipeline()
    
    output_path = "server/data_ingestion/analysis_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"Analysis completed successfully. Extracted base metrics for {results['total_games']} games.")
    print("Metrics:")
    for k, v in results.get("metrics", {}).items():
        print(f"  {k}: {round(v, 4)}")
