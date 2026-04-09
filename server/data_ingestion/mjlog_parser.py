import xml.etree.ElementTree as ET
from typing import List, Dict, Any

class MjlogParser:
    """
    天鳳の生XMLログ (.mjlog) を解析し、扱いやすいイベント群のリストに変換するパーサー
    MJAIフォーマットや、独自AIの入力特徴量作成のための前処理として機能します。
    """
    
    def __init__(self):
        # 0〜135の牌IDを文字列に変換する簡易マップ (1m~9s, 1z~7z)
        self.tile_map = self._build_tile_map()

    def _build_tile_map(self) -> List[str]:
        suits = ["m", "p", "s"]
        mapping = []
        for s in suits:
            mapping += [f"{i}{s}" for i in range(1, 10)]
        mapping += [f"{i}z" for i in range(1, 8)]
        
        full_mapping = []
        # 天鳳の牌IDは0〜135。34種×4枚。
        # 簡易的に [1m, 1m, 1m, 1m, 2m, ...] のように割り当てる
        for i in range(34):
            for _ in range(4):
                full_mapping.append(mapping[i])
        
        # 赤ドラ考慮 (16=5m赤, 52=5p赤, 88=5s赤)
        # 今回は一旦通常牌と同じ文字列にするか、赤ドラプレフィックスをつけることも可能ですが、
        # ベースとなる種類マッピングとして保持
        return full_mapping

    def get_tile_name(self, tile_id: int) -> str:
        if 0 <= tile_id < len(self.tile_map):
            return self.tile_map[tile_id]
        return str(tile_id)

    def parse_file(self, filepath: str) -> List[Dict[str, Any]]:
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            return self.parse_elements(root)
        except Exception as e:
            print(f"Error parsing mjlog file {filepath}: {e}")
            return []

    def parse_string(self, xml_string: str) -> List[Dict[str, Any]]:
        try:
            root = ET.fromstring(xml_string)
            return self.parse_elements(root)
        except Exception as e:
            print(f"Error parsing mjlog string: {e}")
            return []

    def parse_elements(self, root: ET.Element) -> List[Dict[str, Any]]:
        events = []
        
        # プレイヤーのツモ・打牌に対応するプレフィックス
        # T=0(自家), U=1(下家), V=2(対面), W=3(上家)  -> ツモ
        # D=0(自家), E=1(下家), F=2(対面), G=3(上家)  -> 打牌
        tsumo_map = {'T': 0, 'U': 1, 'V': 2, 'W': 3}
        discard_map = {'D': 0, 'E': 1, 'F': 2, 'G': 3}

        for child in root:
            tag = child.tag
            attrs = child.attrib

            if tag == 'UN':
                # ユーザー情報
                events.append({
                    "type": "users",
                    "names": [attrs.get('n0', ''), attrs.get('n1', ''), attrs.get('n2', ''), attrs.get('n3', '')],
                    "dan": attrs.get('dan', ''),
                    "rate": attrs.get('rate', '')
                })
            
            elif tag == 'TAIKYOKU':
                events.append({"type": "start_game", "oya": attrs.get('oya', '0')})
                
            elif tag == 'INIT':
                # 曲の開始
                hai_arrays = []
                for i in range(4):
                    hai_str = attrs.get(f'hai{i}', '')
                    hai_arrays.append([int(x) for x in hai_str.split(',') if x])
                
                events.append({
                    "type": "start_kyoku",
                    "oya": int(attrs.get('oya', 0)),
                    "ten": [int(x) * 100 for x in attrs.get('ten', '').split(',')],
                    "seed": attrs.get('seed', ''),
                    "hands": hai_arrays
                })

            elif tag in ['AGARI', 'RYUUKYOKU']:
                evt = {"type": "end_kyoku", "reason": tag}
                for k, v in attrs.items():
                    evt[k] = v
                events.append(evt)

            elif tag == 'REACH':
                events.append({
                    "type": "reach",
                    "actor": int(attrs.get('who', 0)),
                    "step": int(attrs.get('step', 1)),
                    "ten": attrs.get('ten', '')
                })

            elif tag == 'N':
                # 鳴き (チー・ポン・カン)
                # 実際の解析法は m のビットマップをパースする必要があるが、一旦raw保持
                events.append({
                    "type": "naki",
                    "actor": int(attrs.get('who', 0)),
                    "m": int(attrs.get('m', 0))
                })

            elif tag == 'DORA':
                events.append({
                    "type": "dora",
                    "hai": int(attrs.get('hai', 0))
                })
                
            else:
                # T115 などのツモ、D64 などの打牌処理
                if len(tag) > 1 and tag[0].isalpha() and tag[1:].isdigit():
                    prefix = tag[0]
                    tile_id = int(tag[1:])
                    
                    if prefix in tsumo_map:
                        events.append({
                            "type": "tsumo",
                            "actor": tsumo_map[prefix],
                            "pai": tile_id,
                            "pai_str": self.get_tile_name(tile_id)
                        })
                    elif prefix in discard_map:
                        events.append({
                            "type": "dahai",
                            "actor": discard_map[prefix],
                            "pai": tile_id,
                            "pai_str": self.get_tile_name(tile_id)
                        })

        return events

# 簡易テストコード
if __name__ == "__main__":
    import sys
    parser = MjlogParser()
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        evts = parser.parse_file(filepath)
        for e in evts[:20]:
            print(e)
        print(f"... total {len(evts)} events parsed.")
    else:
        print("Usage: python mjlog_parser.py <path_to_mjlog_file>")
