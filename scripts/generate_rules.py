import json
import os

def generate_high_quality_catalogs():
    os.makedirs("server/rules", exist_ok=True)
    
    # 【防御・読みカテゴリ】＋【状況判断カテゴリ】など -> strategy_catalog
    strategy_rules = [
        # DEF-READ
        {
            "id": "DEF-READ-001",
            "cond": {"turn_min": 8, "turn_max": 24, "target_action": "riichi_5"},
            "w": {"attack": 0.1, "defense": 0.9, "situation": 0.8},
            "rec": "safe_or_ori", "intent": "両スジ罠警戒（2/8高危険）"
        },
        {
            "id": "DEF-READ-002",
            "cond": {"turn_min": 8, "turn_max": 24, "target_action": "middle_to_terminal"},
            "w": {"attack": 0.2, "defense": 0.8, "situation": 0.7},
            "rec": "safe_or_ori", "intent": "聴牌移行シグナル警戒"
        },
        {
            "id": "DEF-READ-003",
            "cond": {"turn_min": 1, "turn_max": 24, "target_action": "pon_tsumogiri_x3"},
            "w": {"attack": 0.0, "defense": 1.0, "situation": 0.9},
            "rec": "genbutsu_only", "intent": "鳴き聴牌完全警戒"
        },
        {
            "id": "DEF-READ-004",
            "cond": {"turn_min": 9, "turn_max": 24, "target_action": "dora_then_safe"},
            "w": {"attack": 0.3, "defense": 0.7, "situation": 0.8},
            "rec": "safe_or_ori", "intent": "ダマテン警戒（ドラ切り後安牌）"
        },
        {
            "id": "DEF-READ-005",
            "cond": {"turn_min": 1, "turn_max": 24, "target_action": "honor_mid_terminal"},
            "w": {"attack": 0.4, "defense": 0.6, "situation": 0.6},
            "rec": "early_defense", "intent": "手牌整理完了シグナル対応"
        },
        
        # OFF-SHAPE
        {
            "id": "OFF-SHAPE-001",
            "cond": {"turn_min": 1, "turn_max": 12, "hand_shape": "4_connected"},
            "w": {"attack": 0.8, "defense": 0.2, "situation": 0.5},
            "rec": "keep_4_connected", "intent": "4連形維持（両面2つ分）"
        },
        {
            "id": "OFF-SHAPE-002",
            "cond": {"turn_min": 1, "turn_max": 12, "hand_shape": "nakabukure"},
            "w": {"attack": 0.7, "defense": 0.3, "situation": 0.5},
            "rec": "keep_nakabukure", "intent": "中膨れ維持（カンチャン＋両面進化）"
        },
        {
            "id": "OFF-SHAPE-003",
            "cond": {"turn_min": 12, "turn_max": 24, "hand_shape": "ryankan"},
            "w": {"attack": 0.6, "defense": 0.4, "situation": 0.4},
            "rec": "discard_ryankan", "intent": "リャンカン見切り（進化余地低）"
        },
        {
            "id": "OFF-SHAPE-004",
            "cond": {"turn_min": 1, "turn_max": 24, "hand_shape": "5block_over"},
            "w": {"attack": 0.6, "defense": 0.4, "situation": 0.5},
            "rec": "discard_toitsu", "intent": "対子落とし（5ブロック理論）"
        },
        {
            "id": "OFF-SHAPE-005",
            "cond": {"turn_min": 1, "turn_max": 24, "hand_shape": "aka_complex"},
            "w": {"attack": 0.9, "defense": 0.1, "situation": 0.8},
            "rec": "keep_aka", "intent": "赤ドラ複合形維持（打点＋速度）"
        },

        # SIT-SCORE
        {
            "id": "SIT-SCORE-001",
            "cond": {"turn_min": 8, "turn_max": 24, "score_min": -12000, "rank": 3, "round": "S4"},
            "w": {"attack": 0.9, "defense": 0.1, "situation": 0.9},
            "rec": "mangan_aim", "intent": "満貫狙い（ラス目前提の逆転）"
        },
        {
            "id": "SIT-SCORE-002",
            "cond": {"turn_min": 1, "turn_max": 24, "score_min": 4000, "rank": 1, "riichi_min": 1, "honba_min": 3},
            "w": {"attack": 0.2, "defense": 0.8, "situation": 1.0},
            "rec": "strategic_deal_in", "intent": "戦略的放銃（トップ本場リセット）"
        },
        {
            "id": "SIT-SCORE-003",
            "cond": {"turn_min": 6, "turn_max": 24, "score_min": -3000, "rank": 2, "dealer": True},
            "w": {"attack": 0.9, "defense": 0.1, "situation": 0.8},
            "rec": "push_for_renchan", "intent": "連荘狙い攻め閾値低下"
        },
        {
            "id": "SIT-SCORE-004",
            "cond": {"turn_min": 1, "turn_max": 24, "score_max": 25000, "riichi_min": 1},
            "w": {"attack": 0.0, "defense": 1.0, "situation": 1.0},
            "rec": "immediate_ori", "intent": "箱テン回避即オリ"
        },
        {
            "id": "SIT-SCORE-005",
            "cond": {"turn_min": 1, "turn_max": 24, "honba_min": 5, "rank": 4, "shanten_max": 1, "riichi_min": 0},
            "w": {"attack": 1.0, "defense": 0.0, "situation": 0.9},
            "rec": "zen_tsuppa", "intent": "本場5以上のラス目全押し"
        }
    ]

    # Mortal解釈用の逆推論ルール (SPEC-READなどAIが推奨した場合の深読み解説)
    interpret_rules = [
        {
            "id": "SPEC-READ-001",
            "target": "any",
            "danger_cond": ["med", "high"],
            "intent": "スジ罠警戒",
            "tpl": "{tile}切りの意図: リーチ後の中張切りに対する逆スジ（スジ罠）警戒"
        },
        {
            "id": "SPEC-READ-002",
            "target": "any",
            "danger_cond": ["low", "med"],
            "intent": "壁崩れ読み",
            "tpl": "{tile}の推奨: 場に見えた壁崩れ周辺ターツの危険度上昇を先読み"
        },
        {
            "id": "SPEC-READ-003",
            "target": "any",
            "danger_cond": ["high"],
            "intent": "フリテン誘導回避",
            "tpl": "{tile}ツモ切り: 自身フリテン時の戦略的ツモ切り（放銃回避優先）"
        },
        {
            "id": "SPEC-READ-004",
            "target": "z",
            "danger_cond": ["high"],
            "intent": "終盤単騎警戒",
            "tpl": "終盤端牌・字牌の単騎待ちピンポイント警戒"
        },
        {
            "id": "SPEC-READ-005",
            "target": "safe",
            "danger_cond": ["low"],
            "intent": "見逃し戦略",
            "tpl": "順位不変時の見逃し・放銃リスク回避の判断"
        }
    ]

    with open("server/rules/strategy_catalog.json", "w", encoding="utf-8") as f:
        json.dump(strategy_rules, f, ensure_ascii=False, indent=2)
    print(f"Generated {len(strategy_rules)} strategy rules.")
    
    with open("server/rules/interpret_catalog.json", "w", encoding="utf-8") as f:
        json.dump(interpret_rules, f, ensure_ascii=False, indent=2)
    print(f"Generated {len(interpret_rules)} interpret rules.")

if __name__ == "__main__":
    generate_high_quality_catalogs()
