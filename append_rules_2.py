import json

new_rules = [
  {
    "id": "READ_DRAG_TILES_SYMMETRY",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 7",
      "hand_contains_dora_and_adjacent_tile == true",
      "adjacent_tile_discarded_before_dora == true",
      "dora_tile_retained_as_isolated == true"
    ],
    "qualitative_logic": {
      "principle": "中盤でドラとその隣接牌を分割処理する行為は、打点隠蔽および特定役・ドラ待ち確定のサイン",
      "checklists": [
        "ドラ牌自体が「待ち」や役の構成要素である可能性が高い",
        "ドラ単騎などドラを活用した役を警戒せよ"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "dora_symmetry_split_correlation",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_RIICHI_AFTER_KAN_DORA_CHANGE",
    "category": "reading",
    "trigger_conditions": [
      "post_kan_dora_reveal_occurred == true",
      "new_kan_dora_type == 'middle_tile'",
      "immediate_action_is_riichi == true"
    ],
    "qualitative_logic": {
      "principle": "カンによるドラ変化直後の即リーチは、打点の飛躍的向上（満貫・跳満級）を伴った強烈な心理的圧迫のサイン",
      "checklists": [
        "通常リーチとは異なり、打点を極限まで重視して防御せよ",
        "放銃リスクが尋常でないため、現物以外は絶対に切らない"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "kan_dora_riichi_value_spike",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_MID_RANGE_ISOLATION",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 7 and turn <= 11",
      "isolated_middle_tile_retained == true",
      "safe_tiles_discarded_prior_to_it == true"
    ],
    "qualitative_logic": {
      "principle": "中盤の安全牌切り＆中張孤立牌の長期保留は、手牌柔軟性の維持と聴牌または特定牌待ちの接近サイン",
      "checklists": [
        "孤立牌自体は危険ではないが、それが手出しで処理・あるいは形が変わった瞬間が極めて危険",
        "保留されている孤立牌のスジやまたぎを警戒"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "mid_range_isolated_retention_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_SEAT_BIAS_IN_MELD",
    "category": "reading",
    "trigger_conditions": [
      "bias_in_meld_source_seat == true",
      "melded_tile_type == 'middle_tile'"
    ],
    "qualitative_logic": {
      "principle": "特定席からの鳴き偏重（対面ポン狙いや上家チー特化など）は、防御姿勢や速度優先といった戦術的意図のサイン",
      "checklists": [
        "対面ポン偏重は打点維持・メンゼン崩れ回避意図（手が整っている）",
        "上家チー偏重はツモ番スキップ・速度特化意図（和了が近い）",
        "鳴きの席順偏向を分析し相手の方向性を逆読みせよ"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "meld_seat_bias_strategy_correlation",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_SAFE_TILE_TSUMOGIRI_CONSECUTIVE",
    "category": "reading",
    "trigger_conditions": [
      "consecutive_safe_tile_tsumogiri_turns >= 3",
      "no_valid_tile_drawn == true"
    ],
    "qualitative_logic": {
      "principle": "安全牌の3巡以上連続ツモ切りは、聴牌が完全に固定されており手変わりを求めていない明確なサイン",
      "checklists": [
        "いつでもリーチが来ると認識し防御準備を完了せよ",
        "安全牌がツモ切られている間の「手牌」が極めて危険"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "safe_tsumogiri_tenpai_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_LATE_GAME_RIICHI_STICK_ACCUMULATION",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 14",
      "accumulated_riichi_sticks >= 2",
      "riichi_declaration_tile_type == 'middle_tile'"
    ],
    "qualitative_logic": {
      "principle": "終盤かつ供託リーチ棒2本以上の状況でのリーチは、和了よりも供託回収価値や順位圧力に主眼が置かれているサイン",
      "checklists": [
        "純粋な手牌の強さよりも順位争いを重視",
        "自分がトップなら順位維持でオリ、ラス圏なら期待値が高いとみて押し推奨等、局面戦略を優先"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "late_riichi_stick_accumulation_push_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_HONOR_TILE_PAIR_RETENTION",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 7 and turn <= 11",
      "retained_honor_pairs_counts >= 2",
      "prioritized_middle_tile_discard == true"
    ],
    "qualitative_logic": {
      "principle": "中盤での字牌対子2組以上の保留＆数牌優先切りは、対々手や字一色・染め手への転換サイン",
      "checklists": [
        "数牌のスジ理論が通用しなくなり、字牌の生牌や対子候補周辺が極めて危険",
        "単騎・双碰待ちを最大限に警戒せよ"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "honor_pair_retention_yaku_shift",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_DRAG_TILE_DISCARD_AFTER_REACH",
    "category": "reading",
    "trigger_conditions": [
      "discard_after_riichi_is_dora == true",
      "dora_was_isolated_or_toitsu == true"
    ],
    "qualitative_logic": {
      "principle": "リーチ後の手出し・ツモ切りドラは、待ちが極限まで固定され（単騎待ち等）、かつ打点の確保がすでに万全であるサイン",
      "checklists": [
        "ドラ牌自体は安全だが、残された別の待ちが極めて狭く確定している",
        "単騎待ちの候補牌（字牌や端牌など）を警戒せよ"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "riichi_dora_discard_tanki_rate",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_MID_GAME_SAFE_TILE_EXCHANGE",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 7 and turn <= 11",
      "mutual_safe_tile_exchange_between_players == true",
      "exchanged_safe_tiles_are_middle_tiles == true"
    ],
    "qualitative_logic": {
      "principle": "中盤における2名以上の現物（中張牌）交換は、互いの手牌質の低下や速度低下、相互牽制のサイン",
      "checklists": [
        "交換されている現物は安全だが、交換に加わっていない牌の危険度上昇に注意",
        "相手の手が整っていないため、自分は攻撃に転じるチャンスと見なす"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "mid_game_mutual_exchange_speed_drop",
      "status": "pending_validation"
    }
  },
  {
    "id": "READ_LATE_GAME_TSUMOGIRI_DANGER",
    "category": "reading",
    "trigger_conditions": [
      "turn >= 14",
      "tsumogiri_is_dangerous_middle_tile == true"
    ],
    "qualitative_logic": {
      "principle": "終盤での生牌・非スジ等の危険中張牌のツモ切りは、聴牌が確定し和了への強烈な執着があるサイン",
      "checklists": [
        "ツモ切られた危険牌だけでなく、手牌内の待ちも確定的に危険",
        "和了への執着が究極的に高まっているので防御を最優先せよ"
      ]
    },
    "quantitative_schema": {
      "dataset": "phoenix_replay_2023",
      "period": "TBD",
      "sample_size": "TBD",
      "confidence_interval_95": "TBD",
      "methodology": "late_dangerous_tsumogiri_tenpai",
      "status": "pending_validation"
    }
  }
]

import json

with open(r'c:\Users\horie\majang\server\rules\phoenix_catalog.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for r in new_rules:
    data['rules'].append(r)

with open(r'c:\Users\horie\majang\server\rules\phoenix_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
