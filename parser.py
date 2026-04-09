def parse_tenhou_tile(raw_val: int) -> dict:
    """
    Tenhou形式の牌値を正確に解析
    raw_val: 例) 128, 132, 5, 31 など
    """
    BASE_MAP = {
        **{i: f"{i+1}m" for i in range(9)},      # 0-8: 萬子
        **{i+9: f"{i+1}p" for i in range(9)},    # 9-17: 筒子
        **{i+18: f"{i+1}s" for i in range(9)},   # 18-26: 索子
        **{i+27: h for i, h in enumerate(['E','S','W','N','P','F','C'])}  # 27-33: 字牌
    }
    
    base = raw_val & 0x3F  # 下位6ビットが基本牌(0-33)
    flags = raw_val & 0xC0  # 上位2ビットがフラグ
    
    return {
        "tile": BASE_MAP.get(base, f"UNK_{base}"),
        "is_red": bool(flags & 0x40),           # 0x40: 赤ドラ
        "is_dora_indicator": bool(flags & 0x80), # 0x80: ドラ表示
        "raw": raw_val
    }

def parse_meld_code(m_str: str) -> dict:
    """
    <N m="24619"/> などの鳴きエンコードを解析
    完全解読は複雑なため、生値を保持しつつ主要情報を抽出
    """
    m = int(m_str)
    return {
        "raw": m,
        # 簡単なプレースホルダー実装
        "meld_type": "unknown", 
        "tiles_used": [], 
        "exposed_method": "unknown" 
    }
