import json

new_rules = [
  {
    "id": "READ_RIICHI_DECLARATION_TIMING_GAP",
    "category": "reading",
    "trigger_conditions": [
      "has_tenpai == true",
      "riichi_declaration_delayed_by_1_turn == true",
      "delayed_discard_tile_type == 'middle_tile'",
      "delayed_discard_is_not_safe_tile == true"
    ],
    "qualitative_logic": {
      "principle": "テンパイからの1巡遅れリーチは、待ちの不安定性または意図的誘導（罠）のサイン",
      "checklists": [
        "即リーチよりも危険度が高い（不確定・誘導）",
        "遅らせた間に切った牌のスジやまたぎを特に警戒"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "riichi_delay_analysis",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_KAN_DECLARATION_HIDDEN_INTENT",
    "category": "reading",
    "trigger_conditions": [
      "furo_type in ['daiminkan', 'kakan']",
      "kan_tile_type == 'middle_tile'",
      "immediate_post_kan_action in ['riichi', 'tenpai_discard']"
    ],
    "qualitative_logic": {
      "principle": "中張牌の明槓/加槓直後のリーチ・テンパイは、打点急上昇と待ちの完全固定（単騎・嵌張）のサイン",
      "checklists": [
        "通常2翻手でもカン直後は4-5翻手と見なして防御優先",
        "カンにより固定されたカンチャン・単騎待ちを警戒"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "kan_subsequent_riichi_danger_analysis",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_DISCARD_SEQUENCE_REVERSAL",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 5",
      "discard_sequence_is_reversed == true",
      "is_isolated_tile_disposal == false"
    ],
    "qualitative_logic": {
      "principle": "中盤以降の逆順切りは、特定スートの完全放棄（染め手）または反対側への誤認誘導シグナル",
      "checklists": [
        "逆順切りの反対側（例: 8→6→4なら1-3）が危険",
        "染め手警戒と誤認誘導の両面から他スートへの警戒を強化"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "reverse_discard_sequence_analysis",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_SAFE_TILE_HOLDING_DURATION",
    "category": "reading",
    "trigger_conditions": [
      "held_safe_tile_turns >= 3",
      "safe_tile_type == 'middle_tile'",
      "post_safe_tile_discard_is_dangerous == true"
    ],
    "qualitative_logic": {
      "principle": "中張安全牌の長期保持と直後の危険牌切りは、テンパイ維持（ツモ切り用）と待ち隠蔽のサイン",
      "checklists": [
        "安全牌保持中の安全な見た目に騙されず、既にテンパイしていると判断",
        "保持していた安全牌が切られた直後の打牌が極めて危険"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "safe_tile_hold_and_release_danger_ratio",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_MELD_SKIP_PATTERN",
    "category": "reading",
    "trigger_conditions": [
      "skipped_meld_opportunity == true",
      "skipped_tile_type == 'middle_tile'",
      "hand_shape_allows_meld == true"
    ],
    "qualitative_logic": {
      "principle": "鳴ける中張牌の見逃しは、メンゼン高打点（リーチ・裏ドラ・多面張）維持のサイン",
      "checklists": [
        "鳴かなかった中張牌のスジやまたぎは、メンゼン待ちの急所の可能性が高い",
        "メンゼン維持のため危険度が通常より増していると認識"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "meld_skip_high_value_correlation",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_TSUMOGIRI_CONSECUTIVE",
    "category": "reading",
    "trigger_conditions": [
      "consecutive_tsumogiri_turns >= 3",
      "no_valid_tile_drawn == true"
    ],
    "qualitative_logic": {
      "principle": "3巡以上の連続ツモ切り（手変わりなし）は、完全テンパイまたは待ち固定のサイン",
      "checklists": [
        "リーチ宣言がいつでも来ると認識し、防御準備を完了",
        "ツモ切りが続いている間の手牌（空切りでない限り）が極めて危険"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "tsumogiri_consecutive_tenpai_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_HONOR_TILE_EARLY_EXHAUSTION",
    "category": "reading",
    "trigger_conditions": [
      "turn <= 6",
      "discarded_honor_tile_types_count >= 4",
      "all_honors_discarded == true"
    ],
    "qualitative_logic": {
      "principle": "序盤の多種字牌すべて切り捨ては、字牌に頼らない染め手や速度特化手のサイン",
      "checklists": [
        "数牌（特に中張牌）の危険度が跳ね上がる",
        "特定スートの高危険度化（染め手警戒）に対応せよ"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "early_honor_exhaustion_some_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_DRAG_TILE_RETENTION",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 7",
      "turn <= 11",
      "dora_tile_held_in_hand == true",
      "discarded_tile_is_safe == true",
      "dora_is_isolated_or_toitsu == true"
    ],
    "qualitative_logic": {
      "principle": "中盤でのドラ（孤立/対子）保留かつ安全牌切りは、打点隠蔽・高打点狙いのサイン",
      "checklists": [
        "見かけの打点（2翻）より実際の打点（4-5翻）が高いと見積もる",
        "ドラ単騎やドラ対子の待ちを警戒"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "dora_retention_hidden_value_analysis",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_WALL_BREAK_IMMEDIATE_RIICHI",
    "category": "reading",
    "trigger_conditions": [
      "wall_break_discard_occurred == true",
      "discarded_tile_type == 'middle_tile'",
      "immediate_post_discard_action == 'riichi'"
    ],
    "qualitative_logic": {
      "principle": "中張牌の壁崩し直後の即リーチは、壁理論の逆利用（残り1枚待ち確定）のサイン",
      "checklists": [
        "壁崩し牌の残り1枚が極めて危険",
        "通常なら安全と思われる壁周辺が高危険化している"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "wall_break_riichi_danger_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_DOUBLE_SIDED_WAIT_DECEPTION",
    "category": "reading",
    "trigger_conditions": [
      "double_sided_taatsu_broken == true",
      "changed_to_kanchan_wait == true",
      "discarded_tile_type == 'middle_tile'"
    ],
    "qualitative_logic": {
      "principle": "両面塔子崩しからの嵌張変化は、待ち隠蔽（引っ掛け）と高打点のサイン",
      "checklists": [
        "両面と見せかけた嵌張待ち（例: 3m待ち）が極めて危険",
        "安全と油断したスジ牌が捕まるため警戒"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "double_sided_deception_kanchan_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_LATE_GAME_SAFE_TILE_EXCHANGE",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 14",
      "safe_tile_exchanged_between_two_players == true",
      "exchanged_tile_is_dangerous_to_third_party == true"
    ],
    "qualitative_logic": {
      "principle": "終盤での2名による互いの現物交換は、相互不戦およびトップ・2位による第三者排除のゲーム",
      "checklists": [
        "交換されている現物は安全だが、交換されていない牌が極めて危険",
        "自分は第三者として防御を最優先し、無理な放銃を避ける"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "late_safe_exchange_third_party_danger",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_MID_GAME_SHAPE_FREEZE_BREAK",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 7",
      "turn <= 11",
      "shape_freeze_was_active == true",
      "shape_freeze_broken_by_valid_tile_draw == true"
    ],
    "qualitative_logic": {
      "principle": "中盤での形状フリーズ（有効牌スルー）の突然の解除は、待ち確定と打点向上の時間切れサイン",
      "checklists": [
        "解除直後の打牌が極めて危険（待ちが確定した証拠）",
        "隠していた待ちが解除によって露見するため、安全牌選定を再評価"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "shape_freeze_break_tenpai_rate",
      "status": "pending_validation"
    }
  }
]

with open(r'c:\Users\horie\majang\server\rules\phoenix_catalog.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

data['rules'].extend(new_rules)

with open(r'c:\Users\horie\majang\server\rules\phoenix_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
