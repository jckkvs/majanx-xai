# server/core/explanation/codes.py

REASON_CODES = {
    # --- 技術的要因 (Technical) ---
    "ryoute": {"label": "両面待ち維持", "category": "wait"},
    "kanchan": {"label": "嵌張待ち改善", "category": "wait"},
    "shanten_down": {"label": "向聴数前進", "category": "efficiency"},
    "anzen": {"label": "安全度優先", "category": "defense"},
    "dora_keep": {"label": "ドラ保持", "category": "value"},
    "aka_keep": {"label": "赤ドラ保持", "category": "value"},
    "shape": {"label": "手形優先", "category": "efficiency"},
    "furiten_avoid": {"label": "フリテン回避", "category": "rule"},
    
    # --- 戦略的要因 (Strategic) ---
    "oya_attack": {"label": "親番の攻め", "category": "context"},
    "betaori": {"label": "ベタ降り判断", "category": "strategy"},
    "mawashi": {"label": "回し打ち", "category": "strategy"},
    "endgame": {"label": "終盤の粘り", "category": "context"},
    "top_keep": {"label": "トップ死守", "category": "position"},
    "las_avoid": {"label": "ラス回避優先", "category": "position"},
    "riichi_support": {"label": "リーチ期待値追求", "category": "strategy"},
    "dama_benefit": {"label": "ダマ押し判断", "category": "strategy"},
}
