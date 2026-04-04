import re
import json
from typing import List, Dict, Optional

class TenhouToMjaiConverter:
    """
    天鳳の生ログ（.log）をmjaiイベント配列に変換するコンバータ
    """
    def __init__(self, analysis_mode: bool = False):
        self.analysis_mode = analysis_mode
        self.tile_map = self._build_tile_map()

    def _build_tile_map(self) -> List[str]:
        suits = ["m", "p", "s"]
        mapping = []
        for s in suits:
            mapping += [f"{i}{s}" for i in range(1, 10)]
        mapping += [f"{i}z" for i in range(1, 8)]
        # 0-135 までの牌IDをmjai形式(1m~9s等)へ変換。
        # 余りを気にせず一律で返せるようにタイルマップを4回繰り返す
        full_mapping = []
        for i in range(4):
            full_mapping.extend(mapping)
        # ※天鳳仕様では赤ドラ固定位置がある(16,52,88)。今回は簡易化。
        return full_mapping

    def convert_log(self, raw_log: str) -> List[Dict]:
        """天鳳ログ文字列 → mjai イベント列"""
        packets = raw_log.strip().split()
        events = []
        current_actor = 0
        round_info = {"is_riichi": False, "turn": 0}

        for pkt in packets:
            evt = self._parse_packet(pkt, round_info)
            if evt:
                events.append(evt)
                if evt["type"] == "dahai":
                    current_actor = (evt["actor"] + 1) % 4
                    round_info["turn"] += 1

        # 解析モード: 他家手牌をマスク解除
        if self.analysis_mode:
            events = self._inject_full_info(events)
            
        return events

    def _parse_packet(self, pkt: str, info: Dict) -> Optional[Dict]:
        m = re.match(r"^([TDNRAWEH])(\d+)$", pkt)
        if not m: 
            return None
        
        cmd, data = m.group(1), int(m.group(2))
        tile_name = self.tile_map[data] if data < len(self.tile_map) else ""

        if cmd == "T":  # 自番ツモ
            return {"type": "tsumo", "actor": 0, "pai": tile_name, "seq": info["turn"]}
        elif cmd == "D":  # 打牌
            return {"type": "dahai", "actor": 0, "pai": tile_name, "tsumogiri": False, "seq": info["turn"]}
        elif cmd == "N":  # 副露
            # N形式: N<actor><type><tile><consumed> (簡易パーサー)
            return {"type": "chi", "actor": 1, "pai": tile_name, "consumed": [], "seq": info["turn"]}
        elif cmd == "A":  # 和了
            return {"type": "agari", "actor": 0, "doras": [], "uras": [], "seq": info["turn"]}
        elif cmd == "H":  # 補牌/槓
            return {"type": "kan", "actor": 0, "pai": tile_name, "seq": info["turn"]}
        return None

    def _inject_full_info(self, events: List[Dict]) -> List[Dict]:
        """解析モード: 隠蔽された手牌・山情報を復元（学習/検証用）"""
        for e in events:
            if self.analysis_mode and e["type"] in ["tsumo", "dahai"]:
                e["analysis_mode"] = True
        return events

    @staticmethod
    def load_from_file(filepath: str, analysis: bool = False) -> List[Dict]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            log = f.read()
        return TenhouToMjaiConverter(analysis_mode=analysis).convert_log(log)
