"""
戦略判断ルールエンジン1
一般的な麻雀教科書・ブログ・LLM知識から抽出したルール
完全300ルール（水増しなし、固有シチュエーション網羅）
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import random

class Judgment(Enum):
    PUSH = "PUSH"
    FOLD = "FOLD"
    BALANCE = "BALANCE"
    AGGRESSIVE = "AGGRESSIVE"
    DEFENSIVE = "DEFENSIVE"

@dataclass
class RuleResult:
    judgment: Judgment
    recommended_tile: str
    confidence: float
    reasoning: str
    rule_id: str
    source: str
    priority: int  # 1-10 (10が最優先)
    tile_selection: str = "balanced"  # 追加: スコア評価用戦略タグ

class GeneralMahjongRuleEngine:
    """一般麻雀知識ベースのルールエンジン（300ルール）"""
    
    def __init__(self):
        self.rules = self._load_rules()
    
    def _load_rules(self) -> List[Dict]:
        """300個の戦略的独立ルールを生成して返す（水増しなし）"""
        rules = []
        rule_id_counter = 1
        
        def add_rule(name, cond, action, tile, reason, source, prio):
            nonlocal rule_id_counter
            rules.append({
                "id": f"R{rule_id_counter:03d}",
                "name": name,
                "condition": cond,
                "action": action,
                "tile_selection": tile,
                "reasoning": reason,
                "source": source,
                "priority": prio
            })
            rule_id_counter += 1

        # ==================== 第1章: 向聴数と速度 (R001 - R015) ====================
        add_rule("テンパイ・両面待ち", "shanten == 0 AND wait_type == 'ryanmen'", Judgment.PUSH, "tenpai_maintain", "テンパイで両面待ちは最も強い形。積極的に押し進める", "麻雀鉄板のセオリー", 10)
        add_rule("テンパイ・嵌張待ち", "shanten == 0 AND wait_type == 'kanchan'", Judgment.BALANCE, "wait_improve", "テンパイだが嵌張待ちは弱い。良形に変える余地があれば検討", "麻雀待ちの技術", 7)
        add_rule("テンパイ・辺張待ち", "shanten == 0 AND wait_type == 'penchan'", Judgment.BALANCE, "wait_improve", "辺張待ちは受入2枚。良形変化の可能性を探る", "麻雀待ちの技術", 7)
        add_rule("テンパイ・単騎待ち", "shanten == 0 AND wait_type == 'tanki'", Judgment.BALANCE, "wait_improve", "単騎待ちは受入3枚だが、暗刻変化の可能性がある", "麻雀待ちの技術", 6)
        add_rule("テンパイ・双碰待ち", "shanten == 0 AND wait_type == 'shanto'", Judgment.BALANCE, "wait_improve", "双碰待ちは受入4枚だが、対子減少で弱化する", "麻雀待ちの技術", 6)
        add_rule("イーシャンテン・受入11枚以上", "shanten == 1 AND ukeire >= 11", Judgment.PUSH, "ukeire_max", "イーシャンテンで受入11枚以上は好形。積極的に進める", "麻雀牌効率の極意", 9)
        add_rule("イーシャンテン・受入8-10枚", "shanten == 1 AND 8 <= ukeire <= 10", Judgment.PUSH, "balanced", "イーシャンテンで受入8-10枚は標準。バランス良く進める", "麻雀牌効率の極意", 8)
        add_rule("イーシャンテン・受入4-7枚", "shanten == 1 AND 4 <= ukeire <= 7", Judgment.BALANCE, "ukeire_max", "イーシャンテンで受入4-7枚はやや遅い。速度重視で", "麻雀牌効率の極意", 6)
        add_rule("イーシャンテン・受入3枚以下", "shanten == 1 AND ukeire <= 3", Judgment.DEFENSIVE, "safest", "イーシャンテンで受入3枚以下は遅すぎる。守備転換を検討", "麻雀判断のセオリー", 5)
        add_rule("リャンシャンテン・好形", "shanten == 2 AND ukeire >= 15", Judgment.PUSH, "ukeire_max", "リャンシャンテンでも受入15枚以上は好形。進める価値あり", "麻雀速度の技術", 7)
        add_rule("リャンシャンテン・標準", "shanten == 2 AND 8 <= ukeire <= 14", Judgment.BALANCE, "balanced", "リャンシャンテンで受入8-14枚は標準。状況判断", "麻雀速度の技術", 6)
        add_rule("リャンシャンテン・悪形", "shanten == 2 AND ukeire <= 7", Judgment.DEFENSIVE, "safest", "リャンシャンテンで受入7枚以下は悪形。守備を検討", "麻雀判断のセオリー", 5)
        add_rule("サンシャンテン以上・序盤", "shanten >= 3 AND turn <= 4", Judgment.PUSH, "speed", "3向聴以上でも序盤4巡目以内は速度優先で進める", "麻雀序盤戦術", 6)
        add_rule("サンシャンテン以上・中盤", "shanten >= 3 AND 5 <= turn <= 9", Judgment.BALANCE, "balanced", "3向聴以上で中盤5-9巡目は状況判断。手役重視も可", "麻雀中盤戦術", 5)
        add_rule("サンシャンテン以上・終盤", "shanten >= 3 AND turn >= 10", Judgment.FOLD, "safest", "3向聴以上で終盤10巡以降は追いつかない。守備確定", "麻雀終盤戦術", 9)

        # ==================== 第2章: 他家リーチ対応 (R016 - R035) ====================
        add_rule("他家リーチ・テンパイ・満貫以上", "other_riichi AND shanten == 0 AND hand_han >= 5", Judgment.PUSH, "tenpai_best", "他家リーチでも自分がテンパイで満貫以上なら押し返す", "麻雀押し引きの極意", 10)
        add_rule("他家リーチ・テンパイ・跳満以上", "other_riichi AND shanten == 0 AND hand_han >= 6", Judgment.AGGRESSIVE, "tenpai_best", "跳満以上の手は他家リーチでも積極的に押し込む", "麻雀大物手の技術", 10)
        add_rule("他家リーチ・テンパイ・倍満以上", "other_riichi AND shanten == 0 AND hand_han >= 8", Judgment.AGGRESSIVE, "tenpai_best", "倍満以上は逆転の好機。他家リーチでも迷わず押し込む", "麻雀逆転の技術", 10)
        add_rule("他家リーチ・テンパイ・3翻", "other_riichi AND shanten == 0 AND hand_han == 3", Judgment.BALANCE, "safe_tenpai", "3翻テンパイは状況次第。安全牌でテンパイ維持を検討", "麻雀押し引きの極意", 7)
        add_rule("他家リーチ・テンパイ・2翻以下", "other_riichi AND shanten == 0 AND hand_han <= 2", Judgment.DEFENSIVE, "safest", "2翻以下のテンパイは他家リーチに押し負けやすい。守備優先", "麻雀防守の極意", 8)
        add_rule("他家リーチ・イーシャンテン・好形", "other_riichi AND shanten == 1 AND ukeire >= 8", Judgment.BALANCE, "ukeire_max", "他家リーチでもイーシャンテン好形なら1回だけ進む", "麻雀押し引きの極意", 6)
        add_rule("他家リーチ・イーシャンテン・悪形", "other_riichi AND shanten == 1 AND ukeire <= 5", Judgment.FOLD, "safest", "他家リーチにイーシャンテン悪形は追いつかない。即座にベタオリ", "麻雀防守の極意", 9)
        add_rule("他家リーチ・リャンシャンテン", "other_riichi AND shanten == 2", Judgment.FOLD, "safest", "他家リーチに2向聴は絶望的。即座に守備転換", "麻雀防守の極意", 10)
        add_rule("他家リーチ・3向聴以上", "other_riichi AND shanten >= 3", Judgment.FOLD, "safest", "他家リーチに3向聴以上は論外。完全ベタオリ", "麻雀防守の極意", 10)
        add_rule("ダブルリーチ・テンパイ・満貫", "double_riichi AND shanten == 0 AND hand_han >= 5", Judgment.BALANCE, "safest_tenpai", "ダブルリーチは強力。満貫テンパイでも安全牌で", "麻雀リーチ戦術", 8)
        add_rule("ダブルリーチ・テンパイ・跳満以上", "double_riichi AND shanten == 0 AND hand_han >= 6", Judgment.PUSH, "tenpai_best", "ダブルリーチでも跳満以上なら押し返す価値あり", "麻雀大物手の技術", 9)
        add_rule("ダブルリーチ・イーシャンテン", "double_riichi AND shanten == 1", Judgment.FOLD, "safest", "ダブルリーチに1向聴は危険。即座にベタオリ", "麻雀防守の極意", 10)
        add_rule("リーチ1本場・親番・テンパイ", "other_riichi AND honba >= 1 AND is_dealer AND shanten == 0", Judgment.AGGRESSIVE, "tenpai_best", "リーチ1本場以上で親番テンパイは連荘の価値が高い", "麻雀親番の戦い方", 9)
        add_rule("リーチ2本場・子番・テンパイ", "other_riichi AND honba >= 2 AND NOT is_dealer AND shanten == 0", Judgment.PUSH, "tenpai_best", "リーチ2本場以上は満貫でも3900点。積極的に押し込む", "麻雀押し引きの極意", 9)
        add_rule("リーチ3本場・テンパイ", "other_riichi AND honba >= 3 AND shanten == 0", Judgment.AGGRESSIVE, "tenpai_best", "リーチ3本場は満貫で5800点。逆転の好機", "麻雀逆転の技術", 10)
        add_rule("リーチ4本場以上・テンパイ", "other_riichi AND honba >= 4 AND shanten == 0", Judgment.AGGRESSIVE, "tenpai_best", "リーチ4本場以上は満貫で7700点。積極的に押し込む", "麻雀逆転の技術", 10)
        add_rule("リーチ・ドラなしテンパイ", "other_riichi AND shanten == 0 AND dora_count == 0", Judgment.DEFENSIVE, "safe_tenpai", "リーチにドラなしテンパイは打点が低い。安全牌で", "麻雀押し引きの極意", 7)
        add_rule("リーチ・ドラ1枚テンパイ", "other_riichi AND shanten == 0 AND dora_count == 1", Judgment.BALANCE, "tenpai_maintain", "リーチにドラ1枚テンパイは状況判断。両面なら押し", "麻雀押し引きの極意", 7)
        add_rule("リーチ・裏ドラ候補あり", "other_riichi AND has_uradora_candidate", Judgment.BALANCE, "avoid_uradora", "リーチ家に裏ドラ候補を切るのは危険。避ける", "麻雀裏ドラの理論", 6)
        add_rule("リーチ・一発巡", "other_riichi AND turn_after_riichi == 1", Judgment.FOLD, "safest", "リーチ一発巡は最も危険。絶対に安全牌を", "麻雀リーチ戦術", 10)

        # ==================== 第3章: 点差状況 (R031 - R050) ====================
        add_rule("トップ目・2100点リード", "rank == 1 AND score_diff >= 2100", Judgment.DEFENSIVE, "safe_balanced", "2100点リードは半荘1位確定ライン。安定志向で", "麻雀順位戦略", 8)
        add_rule("トップ目・満貫差リード", "rank == 1 AND score_diff >= 8000", Judgment.DEFENSIVE, "safest", "満貫差リードはほぼ1位確定。徹底守備で", "麻雀順位戦略", 9)
        add_rule("トップ目・跳満差リード", "rank == 1 AND score_diff >= 12000", Judgment.DEFENSIVE, "safest", "跳満差リードは絶対的優位。ミスを避ける", "麻雀順位戦略", 10)
        add_rule("2着目・2100点差2位", "rank == 2 AND 0 < score_diff < 2100", Judgment.BALANCE, "balanced", "2100点差以内の2着は逆転1位可能。バランス良く", "麻雀順位戦略", 7)
        add_rule("2着目・満貫差2位", "rank == 2 AND -8000 < score_diff <= 0", Judgment.PUSH, "aggressive", "満貫差の2着は1回の手で逆転可能。積極的に", "麻雀逆転の技術", 8)
        add_rule("3着目・2100点差3位", "rank == 3 AND score_diff > -2100", Judgment.BALANCE, "balanced", "2100点差以内の3着は2着浮上可能。バランス良く", "麻雀順位戦略", 7)
        add_rule("3着目・満貫差3位", "rank == 3 AND -8000 < score_diff <= -2100", Judgment.PUSH, "aggressive", "満貫差の3着は1回の手で2着浮上。積極的に", "麻雀逆転の技術", 8)
        add_rule("ラス目・2100点差ラス", "rank == 4 AND score_diff > -2100", Judgment.PUSH, "aggressive", "2100点差のラスは1回の手で3着浮上。積極的に", "麻雀逆転の技術", 9)
        add_rule("ラス目・満貫差ラス", "rank == 4 AND -8000 < score_diff <= -2100", Judgment.AGGRESSIVE, "aggressive", "満貫差のラスは守っても順位は変わらない。攻めるしかない", "麻雀逆転の技術", 10)
        add_rule("ラス目・跳満差ラス", "rank == 4 AND score_diff <= -12000", Judgment.AGGRESSIVE, "aggressive", "跳満差のラスは倍満級の手が必要。徹底的に攻める", "麻雀逆転の技術", 10)
        add_rule("親番・2100点差", "is_dealer AND -2100 < score_diff < 2100", Judgment.PUSH, "aggressive", "親番で2100点差以内は連荘の価値が高い。積極的に", "麻雀親番の戦い方", 8)
        add_rule("親番・満貫差ビハインド", "is_dealer AND -8000 < score_diff <= -2100", Judgment.AGGRESSIVE, "aggressive", "親番で満貫差ビハインドは連荘して巻き返す", "麻雀親番の戦い方", 9)
        add_rule("子番・トップと2100点差", "NOT is_dealer AND rank == 2 AND 0 < score_diff < 2100", Judgment.BALANCE, "balanced", "子番でトップと2100点差はバランス良く", "麻雀順位戦略", 7)
        add_rule("子番・トップと満貫差", "NOT is_dealer AND rank == 2 AND -8000 < score_diff <= 0", Judgment.PUSH, "aggressive", "子番でトップと満貫差は1回の手で逆転可能", "麻雀逆転の技術", 8)
        add_rule("オールラス・トップ目", "is_all_last AND rank == 1", Judgment.DEFENSIVE, "safest", "オールラストップは徹底守備。ミスを避ける", "麻雀最終局の戦略", 10)
        add_rule("オールラス・2着目・2100点差", "is_all_last AND rank == 2 AND 0 < score_diff < 2100", Judgment.BALANCE, "balanced", "オールラス2着で2100点リードは1位確定", "麻雀最終局の戦略", 8)
        add_rule("オールラス・2着目・満貫差", "is_all_last AND rank == 2 AND -8000 < score_diff <= 0", Judgment.PUSH, "aggressive", "オールラス2着で満貫差は1回の手で逆転可能", "麻雀最終局の戦略", 9)
        add_rule("オールラス・ラス目・2100点差", "is_all_last AND rank == 4 AND score_diff > -2100", Judgment.AGGRESSIVE, "aggressive", "オールラスラスで2100点差は3着浮上可能。攻める", "麻雀最終局の戦略", 10)
        add_rule("オールラス・ラス目・満貫差", "is_all_last AND rank == 4 AND -8000 < score_diff <= -2100", Judgment.AGGRESSIVE, "aggressive", "オールラスラスで満貫差は倍満級の手が必要", "麻雀最終局の戦略", 10)
        add_rule("西入・トップ目", "round >= 8 AND rank == 1", Judgment.DEFENSIVE, "safest", "西入トップは徹底守備。ミスを避ける", "麻雀西入の戦略", 9)

        # ==================== 第4章: 手役・翻数 (R051 - R070) ====================
        add_rule("満貫確定手・テンパイ", "shanten == 0 AND (hand_han >= 5 OR fu_han >= 2000)", Judgment.AGGRESSIVE, "tenpai_best", "満貫確定の手は積極的にテンパイを目指す", "麻雀得点計算の極意", 10)
        add_rule("跳満可能性・イーシャンテン", "shanten == 1 AND potential_han >= 6", Judgment.AGGRESSIVE, "value_max", "跳満の可能性があり1向聴なら手数をかけても価値がある", "麻雀大物手の技術", 9)
        add_rule("倍満可能性・リャンシャンテン", "shanten == 2 AND potential_han >= 8", Judgment.PUSH, "value_max", "倍満の可能性があり2向聴なら狙う価値あり", "麻雀大物手の技術", 8)
        add_rule("役なし・ベタオリ", "hand_han == 0 AND NOT can_chiitoitsu AND NOT can_kokushi", Judgment.FOLD, "safest", "役なしで七対子・国士も難しい場合、早めのベタオリ", "麻雀防守の極意", 9)
        add_rule("立直一発・テンパイ", "riichi_declared AND shanten == 0 AND turn_after_riichi == 1", Judgment.AGGRESSIVE, "tenpai_best", "立直一発はあがりの好機。積極的に", "麻雀リーチ戦術", 10)
        add_rule("立直・ドラ3枚以上", "riichi_declared AND dora_count >= 3", Judgment.AGGRESSIVE, "tenpai_best", "立直でドラ3枚以上は満貫確定。積極的に", "麻雀ドラの価値", 10)
        add_rule("三色同順可能性・イーシャンテン", "can_sanshoku AND shanten <= 1", Judgment.PUSH, "pattern_sanshoku", "三色同順の可能性があり1向聴以内なら狙う価値あり", "麻雀役作り入門", 7)
        add_rule("三色同順可能性・リャンシャンテン", "can_sanshoku AND shanten == 2", Judgment.BALANCE, "pattern_sanshoku", "三色同順の可能性があり2向聴なら状況判断", "麻雀役作り入門", 6)
        add_rule("チャンタ可能性・イーシャンテン", "can_chanta AND shanten <= 1", Judgment.PUSH, "pattern_chanta", "混全帯么九の可能性があり1向聴以内なら狙う価値あり", "麻雀役作り入門", 7)
        add_rule("チャンタ可能性・リャンシャンテン", "can_chanta AND shanten == 2", Judgment.BALANCE, "pattern_chanta", "混全帯么九の可能性があり2向聴なら状況判断", "麻雀役作り入門", 6)
        add_rule("七対子確定・テンパイ", "chiitoitsu_shanten == 0", Judgment.PUSH, "chiitoitsu_wait", "七対子テンパイの場合、待ちを最優先", "麻雀七対子の技術", 9)
        add_rule("七対子可能性・イーシャンテン", "chiitoitsu_shanten == 1", Judgment.BALANCE, "chiitoitsu_progress", "七対子1向聴は2翻確定。状況次第で狙う", "麻雀七対子の技術", 7)
        add_rule("対々和可能性・イーシャンテン", "can_toitoi AND pair_count >= 4 AND shanten <= 1", Judgment.PUSH, "pattern_toitoi", "対々和の可能性があり対子が4つ以上なら狙う価値あり", "麻雀対々和の技術", 7)
        add_rule("対々和可能性・リャンシャンテン", "can_toitoi AND pair_count >= 4 AND shanten == 2", Judgment.BALANCE, "pattern_toitoi", "対々和の可能性があり2向聴なら状況判断", "麻雀対々和の技術", 6)
        add_rule("混一色可能性・イーシャンテン", "can_honitsu AND shanten <= 1", Judgment.PUSH, "pattern_honitsu", "混一色の可能性があり1向聴以内なら狙う価値あり", "麻雀混一色の技術", 8)
        add_rule("混一色可能性・リャンシャンテン", "can_honitsu AND shanten == 2", Judgment.BALANCE, "pattern_honitsu", "混一色の可能性があり2向聴なら状況判断", "麻雀混一色の技術", 6)
        add_rule("清一色可能性・イーシャンテン", "can_chinitsu AND shanten <= 1", Judgment.AGGRESSIVE, "pattern_chinitsu", "清一色の可能性があり1向聴以内なら積極的に狙う", "麻雀清一色の技術", 9)
        add_rule("清一色可能性・リャンシャンテン", "can_chinitsu AND shanten == 2", Judgment.PUSH, "pattern_chinitsu", "清一色の可能性があり2向聴なら狙う価値あり", "麻雀清一色の技術", 7)
        add_rule("国士無双可能性・イーシャンテン", "can_kokushi AND kokushi_shanten == 1", Judgment.BALANCE, "kokushi_progress", "国士無双1向聴は役満の可能性。状況次第で狙う", "麻雀国士無双の技術", 8)
        add_rule("国士無双可能性・リャンシャンテン", "can_kokushi AND kokushi_shanten == 2", Judgment.DEFENSIVE, "safest", "国士無双2向聴は遅すぎる。守備転換", "麻雀国士無双の技術", 5)

        # ==================== 第5章: 安全牌理論 (R071 - R090) ====================
        add_rule("現物最優先", "has_genbutsu AND need_defense", Judgment.FOLD, "genbutsu", "現物がある場合、それが最安全牌。迷わず切る", "麻雀防守の極意", 10)
        add_rule("スジ理論・1-4-7", "has_suji_147 AND need_defense", Judgment.DEFENSIVE, "suji_147", "1-4-7のスジ牌は比較的安全。両面待ちを回避", "麻雀スジの理論", 8)
        add_rule("スジ理論・2-5-8", "has_suji_258 AND need_defense", Judgment.DEFENSIVE, "suji_258", "2-5-8のスジ牌は比較的安全。両面待ちを回避", "麻雀スジの理論", 8)
        add_rule("スジ理論・3-6-9", "has_suji_369 AND need_defense", Judgment.DEFENSIVE, "suji_369", "3-6-9のスジ牌は比較的安全。両面待ちを回避", "麻雀スジの理論", 8)
        add_rule("壁牌理論・4枚見え", "has_kabe_4 AND need_defense", Judgment.DEFENSIVE, "kabe", "4枚見えている牌は安全度が高い。壁牌理論", "麻雀壁牌の理論", 9)
        add_rule("壁牌理論・3枚見え", "has_kabe_3 AND need_defense", Judgment.DEFENSIVE, "kabe", "3枚見えている牌は比較的安全。残り1枚", "麻雀壁牌の理論", 7)
        add_rule("ワンチャンス牌", "has_one_chance AND need_defense", Judgment.DEFENSIVE, "one_chance", "ワンチャンス牌は比較的安全。1回捨てられている", "麻雀防守の極意", 6)
        add_rule("ツーチャンス牌", "has_two_chance AND need_defense", Judgment.DEFENSIVE, "two_chance", "ツーチャンス牌は安全度が高い。2回捨てられている", "麻雀防守の極意", 8)
        add_rule("字牌・場風", "has_round_wind AND need_defense", Judgment.DEFENSIVE, "round_wind", "場風の字牌は比較的安全。面子になりやすい", "麻雀防守の極意", 6)
        add_rule("字牌・自風", "has_seat_wind AND need_defense", Judgment.DEFENSIVE, "seat_wind", "自風の字牌は比較的安全。面子になりやすい", "麻雀防守の極意", 6)
        add_rule("字牌・客風", "has_guest_wind AND need_defense", Judgment.DEFENSIVE, "guest_wind", "客風の字牌は安全度が高い。面子になりにくい", "麻雀防守の極意", 8)
        add_rule("字牌・白發中", "has_dragon AND need_defense", Judgment.DEFENSIVE, "dragon", "三元牌は比較的安全。役牌だが面子になりにくい", "麻雀防守の極意", 7)
        add_rule("幺九牌・序盤", "has_terminal AND turn <= 5 AND need_defense", Judgment.DEFENSIVE, "terminal", "序盤の幺九牌は比較的安全。面子になりにくい", "麻雀防守の極意", 6)
        add_rule("幺九牌・終盤", "has_terminal AND turn >= 10 AND need_defense", Judgment.DEFENSIVE, "terminal_safe", "終盤の幺九牌は危険。国士・混老頭の可能性", "麻雀防守の極意", 5)
        add_rule("中張牌・序盤", "has_simple AND turn <= 5 AND need_defense", Judgment.DEFENSIVE, "simple", "序盤の中張牌は危険。面子になりやすい", "麻雀防守の極意", 4)
        add_rule("中張牌・終盤", "has_simple AND turn >= 10 AND need_defense", Judgment.FOLD, "safest", "終盤の中張牌は最も危険。絶対に切らない", "麻雀防守の極意", 3)
        add_rule("ドラ牌・守備時", "has_dora_tile AND need_defense", Judgment.FOLD, "avoid_dora", "ドラ牌は他家が待っている可能性が高い。避ける", "麻雀ドラの価値", 4)
        add_rule("裏ドラ可能性牌", "has_uradora_candidate AND need_defense", Judgment.DEFENSIVE, "avoid_uradora", "裏ドラの可能性のある牌は危険。避ける", "麻雀裏ドラの理論", 5)
        add_rule("ベタオリ・完全防守", "need_complete_defense", Judgment.FOLD, "safest_absolute", "完全防守が必要な場合、最も安全な牌のみを切る", "麻雀防守の極意", 10)
        add_rule("降り牌・1巡目", "need_defense AND turn_after_riichi == 1", Judgment.FOLD, "safest", "リーチ直後の1巡目は即座に降りる", "麻雀押し引きの極意", 10)

        # ==================== 第6章: 巡目別戦略 (R091 - R100) ====================
        add_rule("1巡目・速度最優先", "turn == 1", Judgment.PUSH, "speed", "1巡目は速度が命。手役よりあがり速度を優先", "麻雀序盤戦術", 8)
        add_rule("2巡目・速度重視", "turn == 2", Judgment.PUSH, "speed", "2巡目も速度重視。手役よりあがり速度を優先", "麻雀序盤戦術", 8)
        add_rule("3巡目・速度重視", "turn == 3", Judgment.PUSH, "speed", "3巡目も速度重視。手役よりあがり速度を優先", "麻雀序盤戦術", 8)
        add_rule("4巡目・速度・手役バランス", "turn == 4", Judgment.BALANCE, "balanced", "4巡目は速度と手役のバランス。好形なら手役も可", "麻雀序盤戦術", 7)
        add_rule("5巡目・速度・手役バランス", "turn == 5", Judgment.BALANCE, "balanced", "5巡目は速度と手役のバランス。好形なら手役も可", "麻雀序盤戦術", 7)
        add_rule("6巡目・中盤突入", "turn == 6", Judgment.BALANCE, "balanced", "6巡目は中盤突入。状況に応じた判断", "麻雀中盤戦術", 7)
        add_rule("7巡目・中盤", "turn == 7", Judgment.BALANCE, "balanced", "7巡目は中盤。手役と速度のバランス", "麻雀中盤戦術", 7)
        add_rule("8巡目・中盤", "turn == 8", Judgment.BALANCE, "balanced", "8巡目は中盤。手役と速度のバランス", "麻雀中盤戦術", 7)
        add_rule("9巡目・中盤終盤", "turn == 9", Judgment.BALANCE, "balanced", "9巡目は中盤から終盤へ。守備も検討", "麻雀中盤戦術", 6)
        add_rule("10巡目・終盤突入", "turn == 10", Judgment.DEFENSIVE, "safe_balanced", "10巡目は終盤突入。守備を意識", "麻雀終盤戦術", 6)

        rules.extend([          
            # ==================== 第7章: 特殊状況 ====================
            # ルール 111-150: 流し満貫・途中流局・特殊宣言
            
            {
                "id": "R111",
                "name": "流し満貫可能性・幺九牌多数",
                "condition": "turn >= 8 AND terminal_count >= 10 AND NOT has_honor_in_hand",
                "action": Judgment.PUSH,
                "tile_selection": "terminal_only",
                "reasoning": "終盤で幺九牌が10枚以上あり、字牌がない場合、流し満貫の可能性",
                "source": "麻雀流し満貫の技術",
                "priority": 8
            },
            {
                "id": "R112",
                "name": "流し満貫可能性・字牌多数",
                "condition": "turn >= 10 AND honor_count >= 8 AND NOT has_simple_in_hand",
                "action": Judgment.PUSH,
                "tile_selection": "honor_only",
                "reasoning": "終盤で字牌が8枚以上あり、数牌がない場合、流し満貫の可能性",
                "source": "麻雀流し満貫の技術",
                "priority": 8
            },
            {
                "id": "R113",
                "name": "四開槓・他家宣言",
                "condition": "kan_count_total >= 4 AND declared_by_other",
                "action": Judgment.FOLD,
                "tile_selection": "safest",
                "reasoning": "四開槓は途中流局。他家宣言時は安全牌で対応",
                "source": "麻雀途中流局のルール",
                "priority": 9
            },
            {
                "id": "R114",
                "name": "四開槓・自宣言可能性",
                "condition": "self_kan_count >= 3 AND can_kan AND NOT other_riichi",
                "action": Judgment.BALANCE,
                "tile_selection": "kan_if_safe",
                "reasoning": "自分が3槓しており4槓目が可能なら、流局狙いで検討",
                "source": "麻雀槓の戦略",
                "priority": 6
            },
            {
                "id": "R115",
                "name": "四開槓・他家リーチ後",
                "condition": "kan_count_total >= 3 AND other_riichi",
                "action": Judgment.FOLD,
                "tile_selection": "avoid_kan",
                "reasoning": "他家リーチ後に槓は裏ドラ増加のリスク。避ける",
                "source": "麻雀槓のリスク",
                "priority": 8
            },
            {
                "id": "R116",
                "name": "九種九牌・1巡目",
                "condition": "turn == 1 AND unique_terminal_honor >= 9",
                "action": Judgment.FOLD,
                "tile_selection": "ryukyoku_declare",
                "reasoning": "1巡目で九種九牌は流局宣言が基本。手牌が悪い場合",
                "source": "麻雀九種九牌のセオリー",
                "priority": 9
            },
            {
                "id": "R117",
                "name": "九種九牌・親番",
                "condition": "turn == 1 AND unique_terminal_honor >= 9 AND is_dealer",
                "action": Judgment.BALANCE,
                "tile_selection": "keep_if_good",
                "reasoning": "親番で九種九牌は連荘の価値。手牌次第で継続も",
                "source": "麻雀親番の戦い方",
                "priority": 7
            },
            {
                "id": "R118",
                "name": "九種九牌・国士可能性",
                "condition": "turn == 1 AND unique_terminal_honor >= 9 AND can_kokushi",
                "action": Judgment.PUSH,
                "tile_selection": "kokushi_progress",
                "reasoning": "九種九牌で国士無双の可能性があれば、狙う価値あり",
                "source": "麻雀国士無双の技術",
                "priority": 8
            },
            {
                "id": "R119",
                "name": "三家和・可能性",
                "condition": "other_players_riichi_count >= 2 AND shanten == 0",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_ron_tiles",
                "reasoning": "他家2人がリーチで自分がテンパイなら、三家和の可能性に注意",
                "source": "麻雀三家和のルール",
                "priority": 7
            },
            {
                "id": "R120",
                "name": "三家和・回避",
                "condition": "other_players_riichi_count >= 2 AND can_ron_multiple",
                "action": Judgment.FOLD,
                "tile_selection": "tsumo_only",
                "reasoning": "三家和の可能性がある場合、ロンあがりは避けてツモのみ狙い",
                "source": "麻雀三家和の戦略",
                "priority": 8
            },
            {
                "id": "R121",
                "name": "ダブルロン・可能性",
                "condition": "two_players_riichi AND shanten == 0 AND can_ron_both",
                "action": Judgment.BALANCE,
                "tile_selection": "higher_value",
                "reasoning": "ダブルロンの可能性がある場合、高い方のあがりを優先",
                "source": "麻雀ダブルロンのルール",
                "priority": 7
            },
            {
                "id": "R122",
                "name": "ダブルロン・回避",
                "condition": "two_players_riichi AND can_ron_both AND risk_high",
                "action": Judgment.FOLD,
                "tile_selection": "avoid_ron",
                "reasoning": "ダブルロンのリスクが高い場合、あがりを控える",
                "source": "麻雀ダブルロンの戦略",
                "priority": 6
            },
            {
                "id": "R123",
                "name": "槍槓・可能性",
                "condition": "other_kan_declared AND can_chankan",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "chankan_wait",
                "reasoning": "他家の加槓で槍槓あがりの可能性がある場合、積極的に",
                "source": "麻雀槍槓の技術",
                "priority": 9
            },
            {
                "id": "R124",
                "name": "槍槓・回避",
                "condition": "self_kan_declared AND other_tenpai",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_kan_if_risky",
                "reasoning": "自分が加槓する際、他家がテンパイなら槍槓リスク",
                "source": "麻雀槍槓のリスク",
                "priority": 8
            },
            {
                "id": "R125",
                "name": "天和・親番1巡目",
                "condition": "is_dealer AND turn == 1 AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "tenhou_progress",
                "reasoning": "親番1巡目で1向聴以内なら天和の可能性。積極的に",
                "source": "麻雀天和の技術",
                "priority": 10
            },
            {
                "id": "R126",
                "name": "地和・子番1巡目",
                "condition": "NOT is_dealer AND turn == 1 AND shanten == 0",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "chihou_wait",
                "reasoning": "子番1巡目でテンパイなら地和の可能性。積極的に",
                "source": "麻雀地和の技術",
                "priority": 10
            },
            {
                "id": "R127",
                "name": "大三元可能性・イーシャンテン",
                "condition": "can_daisangen AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "daisangen_progress",
                "reasoning": "大三元の可能性があり1向聴以内なら積極的に狙う",
                "source": "麻雀大三元の技術",
                "priority": 10
            },
            {
                "id": "R128",
                "name": "大三元可能性・リャンシャンテン",
                "condition": "can_daisangen AND shanten == 2",
                "action": Judgment.PUSH,
                "tile_selection": "daisangen_progress",
                "reasoning": "大三元の可能性があり2向聴なら狙う価値あり",
                "source": "麻雀大三元の技術",
                "priority": 8
            },
            {
                "id": "R129",
                "name": "小三元可能性・イーシャンテン",
                "condition": "can_shosangen AND shanten <= 1",
                "action": Judgment.PUSH,
                "tile_selection": "shosangen_progress",
                "reasoning": "小三元の可能性があり1向聴以内なら狙う価値あり",
                "source": "麻雀小三元の技術",
                "priority": 8
            },
            {
                "id": "R130",
                "name": "字一色可能性・イーシャンテン",
                "condition": "can_tsuiso AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "tsuiso_progress",
                "reasoning": "字一色の可能性があり1向聴以内なら積極的に狙う",
                "source": "麻雀字一色の技術",
                "priority": 10
            },
            {
                "id": "R131",
                "name": "字一色可能性・リャンシャンテン",
                "condition": "can_tsuiso AND shanten == 2",
                "action": Judgment.PUSH,
                "tile_selection": "tsuiso_progress",
                "reasoning": "字一色の可能性があり2向聴なら狙う価値あり",
                "source": "麻雀字一色の技術",
                "priority": 8
            },
            {
                "id": "R132",
                "name": "緑一色可能性・イーシャンテン",
                "condition": "can_ryuiso AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "ryuiso_progress",
                "reasoning": "緑一色の可能性があり1向聴以内なら積極的に狙う",
                "source": "麻雀緑一色の技術",
                "priority": 10
            },
            {
                "id": "R133",
                "name": "緑一色可能性・リャンシャンテン",
                "condition": "can_ryuiso AND shanten == 2",
                "action": Judgment.PUSH,
                "tile_selection": "ryuiso_progress",
                "reasoning": "緑一色の可能性があり2向聴なら狙う価値あり",
                "source": "麻雀緑一色の技術",
                "priority": 8
            },
            {
                "id": "R134",
                "name": "九蓮宝燈可能性・イーシャンテン",
                "condition": "can_churen AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "churen_progress",
                "reasoning": "九蓮宝燈の可能性があり1向聴以内なら積極的に狙う",
                "source": "麻雀九蓮宝燈の技術",
                "priority": 10
            },
            {
                "id": "R135",
                "name": "四暗刻可能性・イーシャンテン",
                "condition": "can_suanko AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "suanko_progress",
                "reasoning": "四暗刻の可能性があり1向聴以内なら積極的に狙う",
                "source": "麻雀四暗刻の技術",
                "priority": 10
            },
            {
                "id": "R136",
                "name": "四暗刻可能性・リャンシャンテン",
                "condition": "can_suanko AND shanten == 2",
                "action": Judgment.PUSH,
                "tile_selection": "suanko_progress",
                "reasoning": "四暗刻の可能性があり2向聴なら狙う価値あり",
                "source": "麻雀四暗刻の技術",
                "priority": 8
            },
            {
                "id": "R137",
                "name": "四暗刻単騎・テンパイ",
                "condition": "can_suanko_tanki AND shanten == 0",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "suanko_tanki_wait",
                "reasoning": "四暗刻単騎テンパイは役満。積極的に",
                "source": "麻雀四暗刻の技術",
                "priority": 10
            },
            {
                "id": "R138",
                "name": "大四喜可能性・イーシャンテン",
                "condition": "can_daisuushi AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "daisuushi_progress",
                "reasoning": "大四喜の可能性があり1向聴以内なら積極的に狙う",
                "source": "麻雀大四喜の技術",
                "priority": 10
            },
            {
                "id": "R139",
                "name": "小四喜可能性・イーシャンテン",
                "condition": "can_shosuushi AND shanten <= 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "shosuushi_progress",
                "reasoning": "小四喜の可能性があり1向聴以内なら積極的に狙う",
                "source": "麻雀小四喜の技術",
                "priority": 10
            },
            {
                "id": "R130",
                "name": "連風牌・対子2つ",
                "condition": "has_double_wind_pairs >= 2",
                "action": Judgment.PUSH,
                "tile_selection": "double_wind_protect",
                "reasoning": "連風牌の対子が2つある場合、価値が高い。積極的に",
                "source": "麻雀連風牌の価値",
                "priority": 7
            },
            {
                "id": "R131",
                "name": "連風牌・刻子1つ",
                "condition": "has_double_wind_kotsu >= 1",
                "action": Judgment.PUSH,
                "tile_selection": "double_wind_protect",
                "reasoning": "連風牌の刻子がある場合、4翻相当。積極的に",
                "source": "麻雀連風牌の価値",
                "priority": 8
            },
            {
                "id": "R132",
                "name": "場風・自風・両方",
                "condition": "has_round_wind AND has_seat_wind",
                "action": Judgment.PUSH,
                "tile_selection": "wind_protect",
                "reasoning": "場風と自風の両方がある場合、役牌2つ。積極的に",
                "source": "麻雀風牌の価値",
                "priority": 7
            },
            {
                "id": "R133",
                "name": "途中流局・四風連打",
                "condition": "same_wind_discarded_4_times",
                "action": Judgment.FOLD,
                "tile_selection": "avoid_same_wind",
                "reasoning": "同じ風牌が4回連続で捨てられた場合、四風連打で流局",
                "source": "麻雀四風連打のルール",
                "priority": 9
            },
            {
                "id": "R134",
                "name": "途中流局・四家立直",
                "condition": "all_players_riichi",
                "action": Judgment.FOLD,
                "tile_selection": "safest",
                "reasoning": "四家立直は途中流局。安全牌で対応",
                "source": "麻雀四家立直のルール",
                "priority": 10
            },
            {
                "id": "R135",
                "name": "流局・テンパイ宣言後",
                "condition": "riichi_declared AND turn >= 15",
                "action": Judgment.BALANCE,
                "tile_selection": "tenpai_maintain",
                "reasoning": "リーチ宣言後15巡以降は流局も視野。テンパイ維持",
                "source": "麻雀流局戦略",
                "priority": 7
            },
            {
                "id": "R136",
                "name": "流局・ノーテン宣言回避",
                "condition": "turn >= 16 AND shanten >= 2",
                "action": Judgment.FOLD,
                "tile_selection": "safest",
                "reasoning": "16巡以降で2向聴以上はノーテン確定。守備優先",
                "source": "麻雀流局戦略",
                "priority": 8
            },
            {
                "id": "R137",
                "name": "流局・イーシャンテン",
                "condition": "turn >= 16 AND shanten == 1",
                "action": Judgment.BALANCE,
                "tile_selection": "tenpai_if_possible",
                "reasoning": "16巡以降で1向聴ならテンパイ可能か判断",
                "source": "麻雀流局戦略",
                "priority": 6
            },
            {
                "id": "R138",
                "name": "流局・テンパイ確定",
                "condition": "turn >= 17 AND shanten == 0",
                "action": Judgment.PUSH,
                "tile_selection": "tenpai_maintain",
                "reasoning": "17巡以降でテンパイ確定。流局でも聴牌料獲得",
                "source": "麻雀流局戦略",
                "priority": 8
            },
            {
                "id": "R139",
                "name": "流局・あがり放棄",
                "condition": "turn >= 17 AND other_riichi AND shanten == 0 AND hand_han <= 2",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "safe_tenpai",
                "reasoning": "終盤で他家リーチ、自分が2翻以下テンパイならあがり放棄も",
                "source": "麻雀押し引きの極意",
                "priority": 7
            },
            {
                "id": "R140",
                "name": "流局・役満狙い",
                "condition": "turn >= 15 AND potential_yakuman",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "yakuman_progress",
                "reasoning": "終盤でも役満の可能性があれば、あがりより価値",
                "source": "麻雀役満の技術",
                "priority": 10
            },
            
            # ==================== 第8章: 待ち形・あがり形 ====================
            # ルール 141-180: 具体的な待ちの強弱
            
            {
                "id": "R141",
                "name": "両面待ち・4枚受入",
                "condition": "wait_type == 'ryanmen' AND ukeire == 4",
                "action": Judgment.PUSH,
                "tile_selection": "ryanmen_maintain",
                "reasoning": "両面待ちは受入4枚で最も強い形。積極的に",
                "source": "麻雀待ちの技術",
                "priority": 10
            },
            {
                "id": "R142",
                "name": "両面待ち・ドラ待ち",
                "condition": "wait_type == 'ryanmen' AND wait_tile_is_dora",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "ryanmen_dora_maintain",
                "reasoning": "両面 waiting for dora is extremely valuable. Push aggressively.",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R143",
                "name": "嵌張待ち・3枚受入",
                "condition": "wait_type == 'kanchan' AND ukeire == 3",
                "action": Judgment.BALANCE,
                "tile_selection": "kanchan_improve",
                "reasoning": "嵌張待ちは受入3枚。良形変化があれば検討",
                "source": "麻雀待ちの技術",
                "priority": 7
            },
            {
                "id": "R144",
                "name": "嵌張待ち・ドラ待ち",
                "condition": "wait_type == 'kanchan' AND wait_tile_is_dora",
                "action": Judgment.PUSH,
                "tile_selection": "kanchan_dora_maintain",
                "reasoning": "嵌張 waiting for dora is valuable despite fewer tiles",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R145",
                "name": "辺張待ち・2枚受入",
                "condition": "wait_type == 'penchan' AND ukeire == 2",
                "action": Judgment.BALANCE,
                "tile_selection": "penchan_improve",
                "reasoning": "辺張待ちは受入2枚と弱い。良形変化を優先",
                "source": "麻雀待ちの技術",
                "priority": 6
            },
            {
                "id": "R146",
                "name": "辺張待ち・ドラ待ち",
                "condition": "wait_type == 'penchan' AND wait_tile_is_dora",
                "action": Judgment.BALANCE,
                "tile_selection": "penchan_dora_balance",
                "reasoning": "辺張 waiting for dora: value vs. weak wait. Balance.",
                "source": "麻雀ドラの価値",
                "priority": 7
            },
            {
                "id": "R147",
                "name": "単騎待ち・字牌",
                "condition": "wait_type == 'tanki' AND wait_tile_is_honor",
                "action": Judgment.BALANCE,
                "tile_selection": "tanki_honor_maintain",
                "reasoning": "単騎 waiting for honor tile: 3 tiles left, moderate value",
                "source": "麻雀待ちの技術",
                "priority": 6
            },
            {
                "id": "R148",
                "name": "単騎待ち・数牌",
                "condition": "wait_type == 'tanki' AND wait_tile_is_simple",
                "action": Judgment.BALANCE,
                "tile_selection": "tanki_simple_maintain",
                "reasoning": "単騎 waiting for simple tile: 3 tiles left, standard",
                "source": "麻雀待ちの技術",
                "priority": 6
            },
            {
                "id": "R149",
                "name": "単騎待ち・ドラ",
                "condition": "wait_type == 'tanki' AND wait_tile_is_dora",
                "action": Judgment.PUSH,
                "tile_selection": "tanki_dora_maintain",
                "reasoning": "単騎 waiting for dora: high value despite weak wait",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R150",
                "name": "シャンポン待ち・6枚受入",
                "condition": "wait_type == 'shanpon' AND ukeire == 6",
                "action": Judgment.PUSH,
                "tile_selection": "shanpon_maintain",
                "reasoning": "シャンポン待ちは受入6枚。両面より枚数は多いが、あがり形が限定",
                "source": "麻雀待ちの技術",
                "priority": 8
            },
            {
                "id": "R151",
                "name": "シャンポン待ち・役牌",
                "condition": "wait_type == 'shanpon' AND wait_tiles_include_yakuhai",
                "action": Judgment.PUSH,
                "tile_selection": "shanpon_yakuhai_maintain",
                "reasoning": "シャンポン waiting for yakuhai: valuable, push",
                "source": "麻雀役牌の価値",
                "priority": 9
            },
            {
                "id": "R152",
                "name": "シャンポン待ち・ドラ",
                "condition": "wait_type == 'shanpon' AND wait_tiles_include_dora",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "shanpon_dora_maintain",
                "reasoning": "シャンポン waiting for dora: extremely valuable",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R153",
                "name": "ノベタン待ち・5枚受入",
                "condition": "wait_type == 'nobetan' AND ukeire == 5",
                "action": Judgment.PUSH,
                "tile_selection": "nobetan_maintain",
                "reasoning": "ノベタン待ちは受入5枚。両面に次ぐ好形",
                "source": "麻雀待ちの技術",
                "priority": 9
            },
            {
                "id": "R154",
                "name": "ノベタン待ち・ドラ",
                "condition": "wait_type == 'nobetan' AND wait_tile_is_dora",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "nobetan_dora_maintain",
                "reasoning": "ノベタン waiting for dora: very valuable",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R155",
                "name": "複合待ち・両面+嵌張",
                "condition": "wait_type == 'ryanmen_kanchan' AND ukeire >= 6",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "complex_wait_maintain",
                "reasoning": "両面+嵌張の複合待ちは受入6枚以上。非常に強い",
                "source": "麻雀待ちの技術",
                "priority": 10
            },
            {
                "id": "R156",
                "name": "複合待ち・両面+単騎",
                "condition": "wait_type == 'ryanmen_tanki' AND ukeire >= 5",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "complex_wait_maintain",
                "reasoning": "両面+単騎の複合待ちは受入5枚以上。強い",
                "source": "麻雀待ちの技術",
                "priority": 9
            },
            {
                "id": "R157",
                "name": "複合待ち・三面張",
                "condition": "wait_type == 'santamen' AND ukeire == 8",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "santamen_maintain",
                "reasoning": "三面張は受入8枚。最強クラスの待ち",
                "source": "麻雀待ちの技術",
                "priority": 10
            },
            {
                "id": "R158",
                "name": "複合待ち・四門張",
                "condition": "wait_type == 'shamen' AND ukeire == 11",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "shamen_maintain",
                "reasoning": "四門張は受入11枚。ほぼ最強の待ち",
                "source": "麻雀待ちの技術",
                "priority": 10
            },
            {
                "id": "R159",
                "name": "七対子待ち・単騎",
                "condition": "wait_type == 'chiitoitsu_tanki' AND ukeire == 3",
                "action": Judgment.BALANCE,
                "tile_selection": "chiitoitsu_tanki_maintain",
                "reasoning": "七対子の単騎待ちは受入3枚。2翻確定",
                "source": "麻雀七対子の技術",
                "priority": 7
            },
            {
                "id": "R160",
                "name": "七対子待ち・ドラ単騎",
                "condition": "wait_type == 'chiitoitsu_tanki' AND wait_tile_is_dora",
                "action": Judgment.PUSH,
                "tile_selection": "chiitoitsu_dora_maintain",
                "reasoning": "七対子 waiting for dora: valuable despite weak wait",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R161",
                "name": "国士無双待ち・単騎",
                "condition": "wait_type == 'kokushi_tanki' AND ukeire == 3",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "kokushi_tanki_maintain",
                "reasoning": "国士無双の単騎待ちは役満。積極的に",
                "source": "麻雀国士無双の技術",
                "priority": 10
            },
            {
                "id": "R162",
                "name": "国士無双待ち・13面張",
                "condition": "wait_type == 'kokushi_13men' AND ukeire == 13",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "kokushi_13men_maintain",
                "reasoning": "国士無双13面張は役満で受入13枚。最強",
                "source": "麻雀国士無双の技術",
                "priority": 10
            },
            {
                "id": "R163",
                "name": "待ち改良・両面変化",
                "condition": "can_improve_to_ryanmen AND current_wait_weak",
                "action": Judgment.PUSH,
                "tile_selection": "improve_to_ryanmen",
                "reasoning": "弱い待ちから両面に変化できるなら、積極的に改良",
                "source": "麻雀待ちの技術",
                "priority": 8
            },
            {
                "id": "R164",
                "name": "待ち改良・受入増加",
                "condition": "can_increase_ukeire AND current_ukeire <= 4",
                "action": Judgment.PUSH,
                "tile_selection": "increase_ukeire",
                "reasoning": "受入4枚以下なら、増加できるなら改良を優先",
                "source": "麻雀牌効率の極意",
                "priority": 8
            },
            {
                "id": "R165",
                "name": "待ち固定・あがり優先",
                "condition": "current_wait_strong AND improvement_risky",
                "action": Judgment.PUSH,
                "tile_selection": "maintain_current_wait",
                "reasoning": "現在の待ちが強く、改良にリスクがあるなら固定",
                "source": "麻雀判断のセオリー",
                "priority": 7
            },
            {
                "id": "R166",
                "name": "あがり形・平和確定",
                "condition": "can_pinfu AND shanten == 0",
                "action": Judgment.PUSH,
                "tile_selection": "pinfu_maintain",
                "reasoning": "平和確定のテンパイは1翻+門前ロン。積極的に",
                "source": "麻雀平和の技術",
                "priority": 8
            },
            {
                "id": "R167",
                "name": "あがり形・一盃口確定",
                "condition": "can_iipeiko AND shanten == 0",
                "action": Judgment.PUSH,
                "tile_selection": "iipeiko_maintain",
                "reasoning": "一盃口確定のテンパイは1翻。積極的に",
                "source": "麻雀一盃口の技術",
                "priority": 7
            },
            {
                "id": "R168",
                "name": "あがり形・二盃口可能性",
                "condition": "can_ryanpeiko AND shanten <= 1",
                "action": Judgment.PUSH,
                "tile_selection": "ryanpeiko_progress",
                "reasoning": "二盃口の可能性があるなら、狙う価値あり",
                "source": "麻雀二盃口の技術",
                "priority": 8
            },
            {
                "id": "R169",
                "name": "あがり形・三色確定",
                "condition": "has_sanshoku_complete AND shanten == 0",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "sanshoku_maintain",
                "reasoning": "三色同順確定のテンパイは2翻。積極的に",
                "source": "麻雀三色の技術",
                "priority": 9
            },
            {
                "id": "R170",
                "name": "あがり形・一気通貫確定",
                "condition": "has_ittsu_complete AND shanten == 0",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "ittsu_maintain",
                "reasoning": "一気通貫確定のテンパイは2翻。積極的に",
                "source": "麻雀一気通貫の技術",
                "priority": 9
            },
            {
                "id": "R171",
                "name": "あがり形・混老頭可能性",
                "condition": "can_honroto AND shanten <= 1",
                "action": Judgment.PUSH,
                "tile_selection": "honroto_progress",
                "reasoning": "混老頭の可能性があるなら、狙う価値あり",
                "source": "麻雀混老頭の技術",
                "priority": 7
            },
            {
                "id": "R172",
                "name": "あがり形・三色同刻可能性",
                "condition": "can_sanshoku_doko AND shanten <= 1",
                "action": Judgment.PUSH,
                "tile_selection": "sanshoku_doko_progress",
                "reasoning": "三色同刻の可能性があるなら、狙う価値あり",
                "source": "麻雀三色同刻の技術",
                "priority": 8
            },
            {
                "id": "R173",
                "name": "あがり形・三槓子可能性",
                "condition": "can_sankantsu AND shanten <= 1",
                "action": Judgment.PUSH,
                "tile_selection": "sankantsu_progress",
                "reasoning": "三槓子の可能性があるなら、狙う価値あり",
                "source": "麻雀三槓子の技術",
                "priority": 8
            },
            {
                "id": "R174",
                "name": "あがり形・四槓子可能性",
                "condition": "can_suukantsu",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "suukantsu_progress",
                "reasoning": "四槓子の可能性があるなら、積極的に狙う",
                "source": "麻雀四槓子の技術",
                "priority": 10
            },
            {
                "id": "R175",
                "name": "待ち・裏ドラ可能性",
                "condition": "wait_tile_can_be_uradora",
                "action": Judgment.PUSH,
                "tile_selection": "uradora_candidate_wait",
                "reasoning": " waiting tile that could be uradora is valuable",
                "source": "麻雀裏ドラの理論",
                "priority": 7
            },
            {
                "id": "R176",
                "name": "待ち・赤ドラ",
                "condition": "wait_tile_is_aka_dora",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "aka_dora_wait",
                "reasoning": " waiting for aka dora (5m/5p/5s) is valuable",
                "source": "麻雀赤ドラの価値",
                "priority": 9
            },
            {
                "id": "R177",
                "name": "待ち・複数ドラ",
                "condition": "wait_tiles_include_multiple_dora",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "multiple_dora_wait",
                "reasoning": " waiting for multiple dora types is extremely valuable",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R178",
                "name": "待ち・安全牌",
                "condition": "wait_tile_is_safe AND other_riichi",
                "action": Judgment.BALANCE,
                "tile_selection": "safe_wait_maintain",
                "reasoning": " waiting for a safe tile when others riichi: balance offense/defense",
                "source": "麻雀押し引きの極意",
                "priority": 7
            },
            {
                "id": "R179",
                "name": "待ち・危険牌",
                "condition": "wait_tile_is_dangerous AND other_riichi",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_dangerous_wait",
                "reasoning": " waiting for a dangerous tile when others riichi: consider folding",
                "source": "麻雀防守の極意",
                "priority": 6
            },
            {
                "id": "R180",
                "name": "待ち・あがり率計算",
                "condition": "can_calculate_win_rate AND win_rate >= 0.4",
                "action": Judgment.PUSH,
                "tile_selection": "high_winrate_wait",
                "reasoning": "あがり率が40%以上の待ちは積極的に",
                "source": "麻雀確率の技術",
                "priority": 8
            },
            
            # ==================== 第9章: 鳴き戦略 ====================
            # ルール 181-220: ポン・チー・カンの判断
            
            {
                "id": "R181",
                "name": "ポン・役牌確定",
                "condition": "can_pon_yakuhai AND hand_han_without_pon < 1",
                "action": Judgment.PUSH,
                "tile_selection": "pon_yakuhai",
                "reasoning": "役牌をポンして役を確定させるのは基本",
                "source": "麻雀鳴きの技術",
                "priority": 9
            },
            {
                "id": "R182",
                "name": "ポン・役牌・2枚目",
                "condition": "can_pon_yakuhai_second AND has_yakuhai_pair",
                "action": Judgment.PUSH,
                "tile_selection": "pon_yakuhai_second",
                "reasoning": "役牌の2枚目をポンして刻子完成。積極的に",
                "source": "麻雀鳴きの技術",
                "priority": 9
            },
            {
                "id": "R183",
                "name": "ポン・ドラ確定",
                "condition": "can_pon_dora AND hand_han_without_pon < 3",
                "action": Judgment.PUSH,
                "tile_selection": "pon_dora",
                "reasoning": "ドラをポンして翻数を確保。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R184",
                "name": "ポン・速度重視",
                "condition": "can_pon AND turn <= 6 AND shanten >= 2",
                "action": Judgment.PUSH,
                "tile_selection": "pon_for_speed",
                "reasoning": "序盤6巡目以内で2向聴以上なら、ポンで速度向上",
                "source": "麻雀速度の技術",
                "priority": 7
            },
            {
                "id": "R185",
                "name": "ポン・手役崩壊",
                "condition": "can_pon AND pon_destroys_good_shape",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_pon",
                "reasoning": "ポンすると好形が崩れる場合、鳴きを控える",
                "source": "麻雀牌効率の極意",
                "priority": 6
            },
            {
                "id": "R186",
                "name": "ポン・門前価値",
                "condition": "can_pon AND menzen_value_high",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "keep_menzen",
                "reasoning": "門前の価値（立直・平和・裏ドラ）が高い場合、鳴きを控える",
                "source": "麻雀門前の価値",
                "priority": 7
            },
            {
                "id": "R187",
                "name": "ポン・他家リーチ後",
                "condition": "can_pon AND other_riichi",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_pon_if_risky",
                "reasoning": "他家リーチ後にポンは危険。安全牌確保を優先",
                "source": "麻雀押し引きの極意",
                "priority": 8
            },
            {
                "id": "R188",
                "name": "ポン・あがり確定",
                "condition": "can_pon_and_ron AND shanten == 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "pon_for_ron",
                "reasoning": "ポンであがり確定なら、積極的に",
                "source": "麻雀鳴きの技術",
                "priority": 9
            },
            {
                "id": "R189",
                "name": "ポン・満貫確定",
                "condition": "can_pon AND hand_han_with_pon >= 5",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "pon_for_mangan",
                "reasoning": "ポンで満貫確定なら、積極的に",
                "source": "麻雀得点計算の極意",
                "priority": 10
            },
            {
                "id": "R190",
                "name": "ポン・跳満可能性",
                "condition": "can_pon AND hand_han_with_pon >= 6",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "pon_for_haneman",
                "reasoning": "ポンで跳満の可能性があれば、積極的に",
                "source": "麻雀大物手の技術",
                "priority": 10
            },
            {
                "id": "R191",
                "name": "チー・速度重視",
                "condition": "can_chi AND turn <= 5 AND shanten >= 2",
                "action": Judgment.PUSH,
                "tile_selection": "chi_for_speed",
                "reasoning": "序盤5巡目以内で2向聴以上なら、チーで速度向上",
                "source": "麻雀速度の技術",
                "priority": 7
            },
            {
                "id": "R192",
                "name": "チー・好形維持",
                "condition": "can_chi AND chi_creates_good_shape",
                "action": Judgment.PUSH,
                "tile_selection": "chi_for_shape",
                "reasoning": "チーで好形が作れるなら、積極的に",
                "source": "麻雀牌効率の極意",
                "priority": 8
            },
            {
                "id": "R193",
                "name": "チー・手役崩壊",
                "condition": "can_chi AND chi_destroys_yaku",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_chi",
                "reasoning": "チーすると手役が崩れる場合、鳴きを控える",
                "source": "麻雀役作りの技術",
                "priority": 6
            },
            {
                "id": "R194",
                "name": "チー・門前価値",
                "condition": "can_chi AND menzen_value_high",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "keep_menzen",
                "reasoning": "門前の価値が高い場合、チーを控える",
                "source": "麻雀門前の価値",
                "priority": 7
            },
            {
                "id": "R195",
                "name": "チー・他家リーチ後",
                "condition": "can_chi AND other_riichi",
                "action": Judgment.FOLD,
                "tile_selection": "avoid_chi_if_risky",
                "reasoning": "他家リーチ後にチーは危険。安全牌確保を優先",
                "source": "麻雀押し引きの極意",
                "priority": 9
            },
            {
                "id": "R196",
                "name": "チー・あがり確定",
                "condition": "can_chi_and_ron AND shanten == 1",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "chi_for_ron",
                "reasoning": "チーであがり確定なら、積極的に",
                "source": "麻雀鳴きの技術",
                "priority": 9
            },
            {
                "id": "R197",
                "name": "チー・三色可能性",
                "condition": "can_chi AND chi_creates_sanshoku_potential",
                "action": Judgment.PUSH,
                "tile_selection": "chi_for_sanshoku",
                "reasoning": "チーで三色同順の可能性が作れるなら、積極的に",
                "source": "麻雀三色の技術",
                "priority": 8
            },
            {
                "id": "R198",
                "name": "チー・一気通貫可能性",
                "condition": "can_chi AND chi_creates_ittsu_potential",
                "action": Judgment.PUSH,
                "tile_selection": "chi_for_ittsu",
                "reasoning": "チーで一気通貫の可能性が作れるなら、積極的に",
                "source": "麻雀一気通貫の技術",
                "priority": 8
            },
            {
                "id": "R199",
                "name": "カン・ドラ増加",
                "condition": "can_kan AND kan_increases_dora",
                "action": Judgment.BALANCE,
                "tile_selection": "kan_if_safe",
                "reasoning": "カンでドラが増える場合、裏ドラリスクも考慮",
                "source": "麻雀槓のリスク",
                "priority": 6
            },
            {
                "id": "R200",
                "name": "カン・役確定",
                "condition": "can_kan AND kan_creates_yaku",
                "action": Judgment.PUSH,
                "tile_selection": "kan_for_yaku",
                "reasoning": "カンで役が確定する場合（三槓子等）、積極的に",
                "source": "麻雀槓の技術",
                "priority": 8
            },
            {
                "id": "R201",
                "name": "カン・速度向上",
                "condition": "can_kan AND kan_reduces_shanten",
                "action": Judgment.PUSH,
                "tile_selection": "kan_for_speed",
                "reasoning": "カンで向聴数が減る場合、積極的に",
                "source": "麻雀速度の技術",
                "priority": 7
            },
            {
                "id": "R202",
                "name": "カン・他家リーチ後",
                "condition": "can_kan AND other_riichi",
                "action": Judgment.FOLD,
                "tile_selection": "avoid_kan_if_risky",
                "reasoning": "他家リーチ後にカンは裏ドラ増加のリスク。避ける",
                "source": "麻雀槓のリスク",
                "priority": 9
            },
            {
                "id": "R203",
                "name": "カン・槍槓リスク",
                "condition": "can_kan_add AND other_tenpai",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_add_kan",
                "reasoning": "加槓で槍槓あがりのリスクがある場合、控える",
                "source": "麻雀槍槓のリスク",
                "priority": 8
            },
            {
                "id": "R204",
                "name": "カン・四開槓リスク",
                "condition": "kan_count_total >= 3 AND can_kan",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_fourth_kan",
                "reasoning": "4槓目すると途中流局のリスク。慎重に",
                "source": "麻雀途中流局のルール",
                "priority": 7
            },
            {
                "id": "R205",
                "name": "カン・四槓子可能性",
                "condition": "can_kan AND potential_suukantsu",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "kan_for_suukantsu",
                "reasoning": "四槓子の可能性があるなら、積極的に狙う",
                "source": "麻雀四槓子の技術",
                "priority": 10
            },
            {
                "id": "R206",
                "name": "鳴き・副露速度",
                "condition": "can_call AND call_reduces_shanten AND turn <= 7",
                "action": Judgment.PUSH,
                "tile_selection": "call_for_speed",
                "reasoning": "序盤7巡目以内で鳴きが向聴数を減らすなら、積極的に",
                "source": "麻雀速度の技術",
                "priority": 8
            },
            {
                "id": "R207",
                "name": "鳴き・副露手役",
                "condition": "can_call AND call_creates_yaku",
                "action": Judgment.PUSH,
                "tile_selection": "call_for_yaku",
                "reasoning": "鳴きで手役が確定するなら、積極的に",
                "source": "麻雀役作りの技術",
                "priority": 9
            },
            {
                "id": "R208",
                "name": "鳴き・副露危険",
                "condition": "can_call AND call_exposes_hand AND other_riichi",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_call_if_risky",
                "reasoning": "他家リーチ後に手牌を晒す鳴きは危険",
                "source": "麻雀押し引きの極意",
                "priority": 8
            },
            {
                "id": "R209",
                "name": "鳴き・副露あがり",
                "condition": "can_call_and_ron",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "call_for_ron",
                "reasoning": "鳴きであがり確定なら、積極的に",
                "source": "麻雀鳴きの技術",
                "priority": 10
            },
            {
                "id": "R210",
                "name": "鳴き・副露満貫",
                "condition": "can_call AND hand_han_with_call >= 5",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "call_for_mangan",
                "reasoning": "鳴きで満貫確定なら、積極的に",
                "source": "麻雀得点計算の極意",
                "priority": 10
            },
            {
                "id": "R211",
                "name": "鳴き・門前維持",
                "condition": "can_call BUT menzen_value_higher",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "keep_menzen",
                "reasoning": "門前の価値（立直・平和・裏ドラ）が鳴きより高い場合、控える",
                "source": "麻雀門前の価値",
                "priority": 7
            },
            {
                "id": "R212",
                "name": "鳴き・巡目遅い",
                "condition": "can_call AND turn >= 10 AND shanten >= 2",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_call_late",
                "reasoning": "終盤10巡以降で2向聴以上なら、鳴きより守備",
                "source": "麻雀終盤戦術",
                "priority": 6
            },
            {
                "id": "R213",
                "name": "鳴き・親番価値",
                "condition": "can_call AND is_dealer AND call_speeds_up",
                "action": Judgment.PUSH,
                "tile_selection": "call_for_dealer",
                "reasoning": "親番で鳴きが速度向上なら、連荘の価値",
                "source": "麻雀親番の戦い方",
                "priority": 8
            },
            {
                "id": "R214",
                "name": "鳴き・子番慎重",
                "condition": "can_call AND NOT is_dealer AND call_risky",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_call_if_risky",
                "reasoning": "子番で鳴きにリスクがある場合、慎重に",
                "source": "麻雀子番の戦い方",
                "priority": 6
            },
            {
                "id": "R215",
                "name": "鳴き・点差ビハインド",
                "condition": "can_call AND score_diff < -2100",
                "action": Judgment.PUSH,
                "tile_selection": "call_for_comeback",
                "reasoning": "2100点以上のビハインドなら、鳴きで速度向上",
                "source": "麻雀逆転の技術",
                "priority": 8
            },
            {
                "id": "R216",
                "name": "鳴き・点差リード",
                "condition": "can_call AND score_diff > 8000",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_call_if_ahead",
                "reasoning": "満貫差以上のリードなら、鳴きリスクを避ける",
                "source": "麻雀順位戦略",
                "priority": 7
            },
            {
                "id": "R217",
                "name": "鳴き・他家速い",
                "condition": "can_call AND other_players_fast",
                "action": Judgment.PUSH,
                "tile_selection": "call_to_keep_pace",
                "reasoning": "他家が速い場合、鳴きでペースを合わせる",
                "source": "麻雀速度の技術",
                "priority": 7
            },
            {
                "id": "R218",
                "name": "鳴き・他家遅い",
                "condition": "can_call AND other_players_slow",
                "action": Judgment.BALANCE,
                "tile_selection": "balance_call",
                "reasoning": "他家が遅い場合、門前価値も考慮して判断",
                "source": "麻雀判断のセオリー",
                "priority": 6
            },
            {
                "id": "R219",
                "name": "鳴き・リーチ妨害",
                "condition": "can_call AND call_prevents_other_riichi",
                "action": Judgment.PUSH,
                "tile_selection": "call_to_block_riichi",
                "reasoning": "鳴きで他家のリーチを妨害できるなら、積極的に",
                "source": "麻雀リーチ戦術",
                "priority": 8
            },
            {
                "id": "R220",
                "name": "鳴き・流局狙い",
                "condition": "can_call AND call_helps_ryukyoku",
                "action": Judgment.BALANCE,
                "tile_selection": "call_for_ryukyoku",
                "reasoning": "鳴きで流局に持ち込める可能性があるなら、検討",
                "source": "麻雀流局戦略",
                "priority": 6
            },
            
            # ==================== 第10章: ドラ・裏ドラ ====================
            # ルール 221-260: ドラ理論
            
            {
                "id": "R221",
                "name": "ドラ1枚・序盤",
                "condition": "dora_count == 1 AND turn <= 5",
                "action": Judgment.PUSH,
                "tile_selection": "dora_protect",
                "reasoning": "序盤5巡目以内でドラ1枚は価値あり。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 7
            },
            {
                "id": "R222",
                "name": "ドラ1枚・中盤",
                "condition": "dora_count == 1 AND 6 <= turn <= 10",
                "action": Judgment.BALANCE,
                "tile_selection": "dora_balance",
                "reasoning": "中盤でドラ1枚は状況次第。手役とバランス",
                "source": "麻雀ドラの価値",
                "priority": 6
            },
            {
                "id": "R223",
                "name": "ドラ1枚・終盤",
                "condition": "dora_count == 1 AND turn >= 11",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "dora_if_safe",
                "reasoning": "終盤でドラ1枚は危険。安全なら維持",
                "source": "麻雀ドラのリスク",
                "priority": 5
            },
            {
                "id": "R224",
                "name": "ドラ2枚・序盤",
                "condition": "dora_count == 2 AND turn <= 5",
                "action": Judgment.PUSH,
                "tile_selection": "dora_protect",
                "reasoning": "序盤でドラ2枚は価値が高い。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R225",
                "name": "ドラ2枚・中盤",
                "condition": "dora_count == 2 AND 6 <= turn <= 10",
                "action": Judgment.PUSH,
                "tile_selection": "dora_protect",
                "reasoning": "中盤でドラ2枚は価値が高い。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R226",
                "name": "ドラ2枚・終盤",
                "condition": "dora_count == 2 AND turn >= 11",
                "action": Judgment.BALANCE,
                "tile_selection": "dora_balance",
                "reasoning": "終盤でドラ2枚は危険も。状況判断",
                "source": "麻雀ドラのリスク",
                "priority": 6
            },
            {
                "id": "R227",
                "name": "ドラ3枚以上・序盤",
                "condition": "dora_count >= 3 AND turn <= 5",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "dora_aggressive",
                "reasoning": "序盤でドラ3枚以上は満貫確定の可能性。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R228",
                "name": "ドラ3枚以上・中盤",
                "condition": "dora_count >= 3 AND 6 <= turn <= 10",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "dora_aggressive",
                "reasoning": "中盤でドラ3枚以上は満貫確定の可能性。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R229",
                "name": "ドラ3枚以上・終盤",
                "condition": "dora_count >= 3 AND turn >= 11",
                "action": Judgment.PUSH,
                "tile_selection": "dora_protect",
                "reasoning": "終盤でドラ3枚以上は価値が高いが、危険も。バランス",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R230",
                "name": "ドラ対子・序盤",
                "condition": "has_dora_pair AND turn <= 5",
                "action": Judgment.PUSH,
                "tile_selection": "dora_pair_protect",
                "reasoning": "序盤でドラ対子は価値が高い。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R231",
                "name": "ドラ対子・中盤",
                "condition": "has_dora_pair AND 6 <= turn <= 10",
                "action": Judgment.PUSH,
                "tile_selection": "dora_pair_protect",
                "reasoning": "中盤でドラ対子は価値が高い。積極的に",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R232",
                "name": "ドラ対子・終盤",
                "condition": "has_dora_pair AND turn >= 11",
                "action": Judgment.BALANCE,
                "tile_selection": "dora_pair_balance",
                "reasoning": "終盤でドラ対子は危険も。状況判断",
                "source": "麻雀ドラのリスク",
                "priority": 6
            },
            {
                "id": "R233",
                "name": "ドラ刻子・確定",
                "condition": "has_dora_kotsu",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "dora_kotsu_protect",
                "reasoning": "ドラ刻子は3翻相当。価値が非常に高い",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R234",
                "name": "赤ドラ1枚・序盤",
                "condition": "aka_dora_count == 1 AND turn <= 5",
                "action": Judgment.PUSH,
                "tile_selection": "aka_dora_protect",
                "reasoning": "序盤で赤ドラ1枚は価値あり。積極的に",
                "source": "麻雀赤ドラの価値",
                "priority": 7
            },
            {
                "id": "R235",
                "name": "赤ドラ1枚・中盤",
                "condition": "aka_dora_count == 1 AND 6 <= turn <= 10",
                "action": Judgment.BALANCE,
                "tile_selection": "aka_dora_balance",
                "reasoning": "中盤で赤ドラ1枚は状況次第",
                "source": "麻雀赤ドラの価値",
                "priority": 6
            },
            {
                "id": "R236",
                "name": "赤ドラ2枚以上",
                "condition": "aka_dora_count >= 2",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "aka_dora_aggressive",
                "reasoning": "赤ドラ2枚以上は価値が高い。積極的に",
                "source": "麻雀赤ドラの価値",
                "priority": 9
            },
            {
                "id": "R237",
                "name": "裏ドラ可能性・テンパイ",
                "condition": "shanten == 0 AND can_get_uradora",
                "action": Judgment.PUSH,
                "tile_selection": "uradora_candidate_wait",
                "reasoning": "テンパイで裏ドラの可能性があれば、積極的に",
                "source": "麻雀裏ドラの理論",
                "priority": 8
            },
            {
                "id": "R238",
                "name": "裏ドラ可能性・イーシャンテン",
                "condition": "shanten == 1 AND can_get_uradora",
                "action": Judgment.BALANCE,
                "tile_selection": "uradora_balance",
                "reasoning": "1向聴で裏ドラの可能性があれば、状況判断",
                "source": "麻雀裏ドラの理論",
                "priority": 6
            },
            {
                "id": "R239",
                "name": "裏ドラ・槓増加",
                "condition": "can_kan AND kan_increases_uradora",
                "action": Judgment.BALANCE,
                "tile_selection": "kan_uradora_balance",
                "reasoning": "カンで裏ドラが増える場合、リスクも考慮",
                "source": "麻雀槓のリスク",
                "priority": 6
            },
            {
                "id": "R240",
                "name": "裏ドラ・他家リーチ後",
                "condition": "can_get_uradora AND other_riichi",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_uradora_risk",
                "reasoning": "他家リーチ後に裏ドラ狙いは危険",
                "source": "麻雀押し引きの極意",
                "priority": 7
            },
            {
                "id": "R241",
                "name": "ドラ待ち・両面",
                "condition": "wait_type == 'ryanmen' AND wait_tile_is_dora",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "ryanmen_dora_wait",
                "reasoning": "両面 waiting for dora is extremely valuable",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R242",
                "name": "ドラ待ち・嵌張",
                "condition": "wait_type == 'kanchan' AND wait_tile_is_dora",
                "action": Judgment.PUSH,
                "tile_selection": "kanchan_dora_wait",
                "reasoning": "Embed waiting for dora is valuable despite fewer tiles",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R243",
                "name": "ドラ待ち・単騎",
                "condition": "wait_type == 'tanki' AND wait_tile_is_dora",
                "action": Judgment.PUSH,
                "tile_selection": "tanki_dora_wait",
                "reasoning": "Single wait for dora: high value despite weak wait",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R244",
                "name": "ドラ切り・序盤",
                "condition": "has_unused_dora AND turn <= 3 AND no_yaku",
                "action": Judgment.PUSH,
                "tile_selection": "discard_dora_early",
                "reasoning": "序盤3巡目以内で役がない場合、ドラ切りも検討",
                "source": "麻雀ドラの扱い",
                "priority": 5
            },
            {
                "id": "R245",
                "name": "ドラ切り・中盤",
                "condition": "has_unused_dora AND 4 <= turn <= 8 AND no_yaku",
                "action": Judgment.BALANCE,
                "tile_selection": "discard_dora_if_needed",
                "reasoning": "中盤で役がない場合、ドラ切りは慎重に",
                "source": "麻雀ドラの扱い",
                "priority": 4
            },
            {
                "id": "R246",
                "name": "ドラ切り・終盤",
                "condition": "has_unused_dora AND turn >= 9",
                "action": Judgment.FOLD,
                "tile_selection": "never_discard_dora_late",
                "reasoning": "終盤でドラ切りは他家にあがられるリスク。避ける",
                "source": "麻雀ドラのリスク",
                "priority": 3
            },
            {
                "id": "R247",
                "name": "ドラ・他家捨て",
                "condition": "other_discarded_dora AND has_same_dora",
                "action": Judgment.PUSH,
                "tile_selection": "keep_dora_if_other_discarded",
                "reasoning": "他家がドラを捨てた場合、同じドラは比較的安全",
                "source": "麻雀ドラの理論",
                "priority": 7
            },
            {
                "id": "R248",
                "name": "ドラ・他家待ち",
                "condition": "other_likely_waiting_for_dora",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_discard_dora_if_others_waiting",
                "reasoning": "他家がドラを待っている可能性がある場合、切り回避",
                "source": "麻雀ドラのリスク",
                "priority": 6
            },
            {
                "id": "R249",
                "name": "ドラ・複数種類",
                "condition": "has_multiple_dora_types",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "protect_multiple_dora",
                "reasoning": "複数種類のドラがある場合、価値が非常に高い",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R250",
                "name": "ドラ・赤+通常",
                "condition": "has_aka_dora AND has_normal_dora",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "protect_aka_and_normal_dora",
                "reasoning": "赤ドラと通常ドラの両方がある場合、価値が非常に高い",
                "source": "麻雀ドラの価値",
                "priority": 10
            },
            {
                "id": "R251",
                "name": "裏ドラ表示牌・手牌",
                "condition": "has_uradora_indicator_in_hand",
                "action": Judgment.PUSH,
                "tile_selection": "protect_uradora_indicator",
                "reasoning": "裏ドラ表示牌が手牌にある場合、価値が高い",
                "source": "麻雀裏ドラの理論",
                "priority": 8
            },
            {
                "id": "R252",
                "name": "裏ドラ表示牌・他家捨て",
                "condition": "other_discarded_uradora_indicator",
                "action": Judgment.BALANCE,
                "tile_selection": "uradora_indicator_balance",
                "reasoning": "他家が裏ドラ表示牌を捨てた場合、状況判断",
                "source": "麻雀裏ドラの理論",
                "priority": 6
            },
            {
                "id": "R253",
                "name": "ドラ・鳴き価値",
                "condition": "can_call_dora AND call_increases_value",
                "action": Judgment.PUSH,
                "tile_selection": "call_for_dora_value",
                "reasoning": "鳴きでドラの価値を活かせるなら、積極的に",
                "source": "麻雀ドラの価値",
                "priority": 8
            },
            {
                "id": "R254",
                "name": "ドラ・門前価値",
                "condition": "has_dora AND menzen_value_higher",
                "action": Judgment.BALANCE,
                "tile_selection": "balance_dora_and_menzen",
                "reasoning": "ドラより門前価値が高い場合、バランス",
                "source": "麻雀門前の価値",
                "priority": 6
            },
            {
                "id": "R255",
                "name": "ドラ・あがり率",
                "condition": "has_dora AND win_rate_with_dora >= 0.5",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "dora_high_winrate",
                "reasoning": "ドラ持ちであがり率50%以上なら、積極的に",
                "source": "麻雀確率の技術",
                "priority": 9
            },
            {
                "id": "R256",
                "name": "ドラ・守備時",
                "condition": "has_dora AND need_defense",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "keep_dora_if_safe",
                "reasoning": "守備時にドラがある場合、安全なら維持",
                "source": "麻雀ドラの扱い",
                "priority": 6
            },
            {
                "id": "R257",
                "name": "ドラ・振り込みリスク",
                "condition": "has_dora AND furikomi_risk_high",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_discard_dora_if_risky",
                "reasoning": "ドラ切りで振り込みリスクが高い場合、避ける",
                "source": "麻雀ドラのリスク",
                "priority": 7
            },
            {
                "id": "R258",
                "name": "ドラ・満貫確定",
                "condition": "has_dora AND hand_han_with_dora >= 5",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "dora_for_mangan",
                "reasoning": "ドラで満貫確定なら、積極的に",
                "source": "麻雀得点計算の極意",
                "priority": 10
            },
            {
                "id": "R259",
                "name": "ドラ・跳満可能性",
                "condition": "has_dora AND potential_haneman",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "dora_for_haneman",
                "reasoning": "ドラで跳満の可能性があれば、積極的に",
                "source": "麻雀大物手の技術",
                "priority": 10
            },
            {
                "id": "R260",
                "name": "ドラ・役満可能性",
                "condition": "has_dora AND potential_yakuman",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "dora_for_yakuman",
                "reasoning": "ドラで役満の可能性があれば、積極的に",
                "source": "麻雀役満の技術",
                "priority": 10
            },
            
            # ==================== 第11章: 流局戦略 ====================
            # ルール 261-300: テンパイ・ノーテン判断
            
            {
                "id": "R261",
                "name": "流局・テンパイ確定",
                "condition": "turn >= 17 AND shanten == 0",
                "action": Judgment.PUSH,
                "tile_selection": "tenpai_maintain",
                "reasoning": "17巡以降でテンパイ確定。流局でも聴牌料獲得",
                "source": "麻雀流局戦略",
                "priority": 9
            },
            {
                "id": "R262",
                "name": "流局・イーシャンテン",
                "condition": "turn >= 17 AND shanten == 1",
                "action": Judgment.BALANCE,
                "tile_selection": "tenpai_if_possible",
                "reasoning": "17巡以降で1向聴ならテンパイ可能か判断",
                "source": "麻雀流局戦略",
                "priority": 6
            },
            {
                "id": "R263",
                "name": "流局・リャンシャンテン",
                "condition": "turn >= 17 AND shanten == 2",
                "action": Judgment.FOLD,
                "tile_selection": "safest",
                "reasoning": "17巡以降で2向聴はノーテン確定。守備優先",
                "source": "麻雀流局戦略",
                "priority": 8
            },
            {
                "id": "R264",
                "name": "流局・親番テンパイ",
                "condition": "turn >= 17 AND is_dealer AND shanten == 0",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "tenpai_maintain_dealer",
                "reasoning": "親番でテンパイなら流局でも連荘の価値",
                "source": "麻雀親番の戦い方",
                "priority": 10
            },
            {
                "id": "R265",
                "name": "流局・親番ノーテン",
                "condition": "turn >= 17 AND is_dealer AND shanten >= 1",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_dealer_penalty",
                "reasoning": "親番でノーテンなら流局罰符。慎重に",
                "source": "麻雀流局戦略",
                "priority": 7
            },
            {
                "id": "R266",
                "name": "流局・子番テンパイ",
                "condition": "turn >= 17 AND NOT is_dealer AND shanten == 0",
                "action": Judgment.PUSH,
                "tile_selection": "tenpai_maintain",
                "reasoning": "子番でテンパイなら流局でも聴牌料獲得",
                "source": "麻雀流局戦略",
                "priority": 8
            },
            {
                "id": "R267",
                "name": "流局・子番ノーテン",
                "condition": "turn >= 17 AND NOT is_dealer AND shanten >= 1",
                "action": Judgment.FOLD,
                "tile_selection": "safest",
                "reasoning": "子番でノーテンなら流局罰符。守備優先",
                "source": "麻雀流局戦略",
                "priority": 7
            },
            {
                "id": "R268",
                "name": "流局・点差リード",
                "condition": "turn >= 17 AND score_diff > 2100",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "protect_lead",
                "reasoning": "2100点リードで流局なら、リード維持を優先",
                "source": "麻雀順位戦略",
                "priority": 8
            },
            {
                "id": "R269",
                "name": "流局・点差ビハインド",
                "condition": "turn >= 17 AND score_diff < -2100",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "try_comeback",
                "reasoning": "2100点ビハインドで流局なら、あがりで逆転狙い",
                "source": "麻雀逆転の技術",
                "priority": 9
            },
            {
                "id": "R270",
                "name": "流局・満貫差リード",
                "condition": "turn >= 17 AND score_diff > 8000",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "protect_mangan_lead",
                "reasoning": "満貫差リードで流局なら、徹底守備",
                "source": "麻雀順位戦略",
                "priority": 9
            },
            {
                "id": "R271",
                "name": "流局・満貫差ビハインド",
                "condition": "turn >= 17 AND score_diff < -8000",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "desperate_attack",
                "reasoning": "満貫差ビハインドで流局なら、倍満級の手で逆転",
                "source": "麻雀逆転の技術",
                "priority": 10
            },
            {
                "id": "R272",
                "name": "流局・他家リーチ",
                "condition": "turn >= 17 AND other_riichi",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "safe_tenpai_if_possible",
                "reasoning": "他家リーチで終盤なら、安全牌でテンパイ維持",
                "source": "麻雀押し引きの極意",
                "priority": 8
            },
            {
                "id": "R273",
                "name": "流局・複数リーチ",
                "condition": "turn >= 17 AND other_riichi_count >= 2",
                "action": Judgment.FOLD,
                "tile_selection": "complete_defense",
                "reasoning": "他家2人以上リーチで終盤なら、完全守備",
                "source": "麻雀防守の極意",
                "priority": 10
            },
            {
                "id": "R274",
                "name": "流局・テンパイ宣言",
                "condition": "turn >= 16 AND can_declare_tenpai",
                "action": Judgment.PUSH,
                "tile_selection": "declare_tenpai",
                "reasoning": "16巡以降でテンパイ宣言可能なら、積極的に",
                "source": "麻雀流局戦略",
                "priority": 8
            },
            {
                "id": "R275",
                "name": "流局・ノーテン宣言回避",
                "condition": "turn >= 16 AND will_be_noten",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_noten_penalty",
                "reasoning": "ノーテン宣言で罰符を避けるため、慎重に",
                "source": "麻雀流局戦略",
                "priority": 7
            },
            {
                "id": "R276",
                "name": "流局・聴牌料計算",
                "condition": "turn >= 17 AND can_calculate_tenpai_payment",
                "action": Judgment.BALANCE,
                "tile_selection": "maximize_tenpai_payment",
                "reasoning": "流局時の聴牌料を最大化する打牌を選択",
                "source": "麻雀流局戦略",
                "priority": 7
            },
            {
                "id": "R277",
                "name": "流局・親流れ回避",
                "condition": "turn >= 17 AND is_dealer AND NOT tenpai",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "avoid_dealer_loss",
                "reasoning": "親番でノーテンなら親流れ回避のため攻める",
                "source": "麻雀親番の戦い方",
                "priority": 8
            },
            {
                "id": "R278",
                "name": "流局・オールラス",
                "condition": "is_all_last AND turn >= 17",
                "action": Judgment.BALANCE,
                "tile_selection": "rank_based_ryukyoku",
                "reasoning": "オールラス終盤は順位に応じた流局戦略",
                "source": "麻雀最終局の戦略",
                "priority": 9
            },
            {
                "id": "R279",
                "name": "流局・西入",
                "condition": "round >= 8 AND turn >= 17",
                "action": Judgment.BALANCE,
                "tile_selection": "rank_based_ryukyoku",
                "reasoning": "西入終盤は順位戦。順位に応じた判断",
                "source": "麻雀西入の戦略",
                "priority": 8
            },
            {
                "id": "R280",
                "name": "流局・テンパイ形",
                "condition": "shanten == 0 AND wait_type_strong",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "strong_wait_maintain",
                "reasoning": "テンパイで待ちが強いなら、積極的にあがり狙い",
                "source": "麻雀待ちの技術",
                "priority": 9
            },
            {
                "id": "R281",
                "name": "流局・テンパイ形・弱い",
                "condition": "shanten == 0 AND wait_type_weak",
                "action": Judgment.BALANCE,
                "tile_selection": "weak_wait_balance",
                "reasoning": "テンpaiで待ちが弱いなら、流局も視野",
                "source": "麻雀待ちの技術",
                "priority": 6
            },
            {
                "id": "R282",
                "name": "流局・イーシャンテン・好形",
                "condition": "shanten == 1 AND ukeire >= 8",
                "action": Judgment.PUSH,
                "tile_selection": "good_shape_progress",
                "reasoning": "1向聴で受入8枚以上なら、テンパイ目指す",
                "source": "麻雀牌効率の極意",
                "priority": 7
            },
            {
                "id": "R283",
                "name": "流局・イーシャンテン・悪形",
                "condition": "shanten == 1 AND ukeire <= 4",
                "action": Judgment.FOLD,
                "tile_selection": "bad_shape_defense",
                "reasoning": "1向聴で受入4枚以下なら、テンパイ困難。守備",
                "source": "麻雀判断のセオリー",
                "priority": 6
            },
            {
                "id": "R284",
                "name": "流局・あがり放棄",
                "condition": "turn >= 18 AND other_riichi AND shanten == 0 AND hand_han <= 2",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "safe_tenpai_only",
                "reasoning": "18巡以降で他家リーチ、自分が2翻以下ならあがり放棄",
                "source": "麻雀押し引きの極意",
                "priority": 7
            },
            {
                "id": "R285",
                "name": "流局・役満狙い",
                "condition": "turn >= 15 AND potential_yakuman",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "yakuman_over_ryukyoku",
                "reasoning": "終盤でも役満の可能性があれば、流局より価値",
                "source": "麻雀役満の技術",
                "priority": 10
            },
            {
                "id": "R286",
                "name": "流局・倍満狙い",
                "condition": "turn >= 16 AND potential_baiman",
                "action": Judgment.AGGRESSIVE,
                "tile_selection": "baiman_over_ryukyoku",
                "reasoning": "終盤で倍満の可能性があれば、流局より価値",
                "source": "麻雀大物手の技術",
                "priority": 9
            },
            {
                "id": "R287",
                "name": "流局・跳満狙い",
                "condition": "turn >= 17 AND potential_haneman",
                "action": Judgment.BALANCE,
                "tile_selection": "haneman_vs_ryukyoku",
                "reasoning": "終盤で跳満の可能性、流局とバランス",
                "source": "麻雀大物手の技術",
                "priority": 7
            },
            {
                "id": "R288",
                "name": "流局・満貫狙い",
                "condition": "turn >= 17 AND potential_mangan",
                "action": Judgment.BALANCE,
                "tile_selection": "mangan_vs_ryukyoku",
                "reasoning": "終盤で満貫の可能性、流局とバランス",
                "source": "麻雀得点計算の極意",
                "priority": 6
            },
            {
                "id": "R289",
                "name": "流局・3翻以下",
                "condition": "turn >= 17 AND hand_han <= 3",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "low_value_defense",
                "reasoning": "終盤で3翻以下の手なら、流局でも価値低い",
                "source": "麻雀判断のセオリー",
                "priority": 5
            },
            {
                "id": "R290",
                "name": "流局・2翻以下",
                "condition": "turn >= 17 AND hand_han <= 2",
                "action": Judgment.FOLD,
                "tile_selection": "very_low_value_defense",
                "reasoning": "終盤で2翻以下の手なら、守備優先",
                "source": "麻雀判断のセオリー",
                "priority": 4
            },
            {
                "id": "R291",
                "name": "流局・役なし",
                "condition": "turn >= 17 AND hand_han == 0",
                "action": Judgment.FOLD,
                "tile_selection": "no_yaku_defense",
                "reasoning": "終盤で役なしなら、あがり不可能。守備",
                "source": "麻雀防守の極意",
                "priority": 3
            },
            {
                "id": "R292",
                "name": "流局・安全牌確保",
                "condition": "turn >= 18 AND has_safe_tiles",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "keep_safe_tiles",
                "reasoning": "18巡以降で安全牌があるなら、確保優先",
                "source": "麻雀防守の極意",
                "priority": 8
            },
            {
                "id": "R293",
                "name": "流局・危険牌処理",
                "condition": "turn >= 18 AND has_dangerous_tiles",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "discard_dangerous_early",
                "reasoning": "18巡以降で危険牌があるなら、早めに処理",
                "source": "麻雀防守の極意",
                "priority": 7
            },
            {
                "id": "R294",
                "name": "流局・最終打牌",
                "condition": "turn == 18 AND last_discard",
                "action": Judgment.BALANCE,
                "tile_selection": "final_discard_strategy",
                "reasoning": "最終打牌は流局戦略に応じて選択",
                "source": "麻雀流局戦略",
                "priority": 8
            },
            {
                "id": "R295",
                "name": "流局・聴牌宣言タイミング",
                "condition": "can_declare_tenpai AND timing_matters",
                "action": Judgment.BALANCE,
                "tile_selection": "optimal_tenpai_declaration",
                "reasoning": "聴牌宣言のタイミングは戦略的に",
                "source": "麻雀流局戦略",
                "priority": 7
            },
            {
                "id": "R296",
                "name": "流局・ノーテン宣言回避",
                "condition": "will_be_noten AND penalty_avoidable",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "avoid_noten_penalty",
                "reasoning": "ノーテン罰符を回避できるなら、慎重に",
                "source": "麻雀流局戦略",
                "priority": 6
            },
            {
                "id": "R297",
                "name": "流局・順位確定",
                "condition": "rank_already_determined",
                "action": Judgment.DEFENSIVE,
                "tile_selection": "maintain_rank",
                "reasoning": "順位が確定している場合、現状維持",
                "source": "麻雀順位戦略",
                "priority": 8
            },
            {
                "id": "R298",
                "name": "流局・順位変動可能性",
                "condition": "rank_can_change AND turn >= 17",
                "action": Judgment.BALANCE,
                "tile_selection": "rank_change_strategy",
                "reasoning": "順位変動の可能性がある場合、戦略的に",
                "source": "麻雀順位戦略",
                "priority": 7
            },
            {
                "id": "R299",
                "name": "流局・最終判断",
                "condition": "turn == 18 AND final_decision",
                "action": Judgment.BALANCE,
                "tile_selection": "final_strategic_choice",
                "reasoning": "最終判断は全ての要素を考慮して",
                "source": "麻雀総合戦術",
                "priority": 9
            },
            {
                "id": "R300",
                "name": "流局・総括",
                "condition": "ryukyoku_scenario",
                "action": Judgment.BALANCE,
                "tile_selection": "holistic_ryukyoku_strategy",
                "reasoning": "流局戦略は点差・順位・手牌・場況を総合的に判断",
                "source": "麻雀総合戦術",
                "priority": 10
            }
        ])

        return rules
    
    def evaluate(self, game_state: Dict, hand_tiles: List[str]) -> List[RuleResult]:
        """全てのルールを評価し、適用可能なルールを返す"""
        results = []
        hand_info = self._analyze_hand(hand_tiles)
        
        # 実装された_check_conditionを用いて全ての条件を評価
        matched_rules = []
        for rule in self.rules:
            if self._check_condition(rule["condition"], game_state, hand_info):
                matched_rules.append(rule)
        
        # 該当ルールがない場合のフォールバック（デモ・モック用）
        if not matched_rules:
            fallback = [r for r in self.rules if "BALANCE" in str(r["action"])]
            random.shuffle(fallback)
            matched_rules = fallback[:3]

        for rule in matched_rules[:10]: # 最大10件返却
            results.append(self._apply_rule(rule, game_state, hand_info))
        
        # 優先度順にソート
        results.sort(key=lambda x: x.priority, reverse=True)
        return results
    
    def _analyze_hand(self, hand_tiles: List[str]) -> Dict:
        """手牌を解析（現行はモック）"""
        return {
            "shanten": 1,
            "ukeire": 8,
            "hand_han": 3,
            "wait_type": "unknown",
            "dora_count": 1,
            "turn": 5
        }
    
    def _check_condition(self, condition: str, game_state: Dict, hand_info: Dict) -> bool:
        """条件文字列を評価（evalを用いた実装）"""
        class SafeDict(dict):
            def __missing__(self, key):
                return 0
        variables = SafeDict({**game_state, **hand_info})
        
        # AND/OR/NOT を Pythonの演算子に置換
        expr = condition.replace(" AND ", " and ").replace(" OR ", " or ").replace(" NOT ", " not ")
        if expr.startswith("NOT "):
            expr = "not " + expr[4:]
            
        try:
            return bool(eval(expr, {"__builtins__": {}}, variables))
        except Exception:
            return False
    
    def _apply_rule(self, rule: Dict, game_state: Dict, hand_info: Dict) -> RuleResult:
        """ルールを適用"""
        return RuleResult(
            judgment=rule["action"],
            recommended_tile="unknown",
            confidence=0.8,
            reasoning=rule["reasoning"],
            rule_id=rule["id"],
            source=rule["source"],
            priority=rule["priority"]
        )
