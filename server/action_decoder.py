from typing import Dict, Union

def decode_action(idx: int, prob: float, q_val: float) -> Dict[str, Union[str, float, int]]:
    """
    46次元インデックスを牌ID・アクション・数値へ変換する。
    Mortalの出力インデックス(0-45)を解釈する。
    """
    if idx < 34:
        # 打牌 (0-33: 1m-9m, 1p-9p, 1s-9s, 1z-7z)
        suits = ['m', 'p', 's', 'z']
        suit = suits[idx // 9]
        num = (idx % 9) + 1
        tile_id = f"{num}{suit}"
        action_type = "dahai"
    elif idx == 34:
        tile_id = "tsumogiri"
        action_type = "tsumogiri"
    elif idx == 35:
        tile_id = "chi"
        action_type = "chi"
    elif idx == 36:
        tile_id = "pon"
        action_type = "pon"
    elif idx in (37, 38, 39):
        tile_id = ["ankan", "kakan", "daiminkan"][idx - 37]
        action_type = tile_id
    elif idx == 40:
        tile_id = "hora"
        action_type = "hora"
    elif idx == 41:
        tile_id = "ryukyoku"
        action_type = "ryukyoku"
    elif idx == 42:
        tile_id = "kakan"
        action_type = "kakan"
    elif idx == 43:
        tile_id = "nuki" # 抜きドラ等
        action_type = "nuki"
    else:
        tile_id = "none"
        action_type = "skip"

    return {
        "tile_id": tile_id,
        "action_type": action_type,
        "probability": float(prob),
        "q_value": float(q_val),
        "index": idx
    }
