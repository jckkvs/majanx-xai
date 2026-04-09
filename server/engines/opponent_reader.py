"""
server/engines/opponent_reader.py
方向性4: 他家読み・待ち推定エンジン

他家の捨て牌パターン・副露構造・リーチ宣言牌を分析し、
待ち候補集合・危険度階層・Confidence を出力する。

出力は方向性2の Phase2 打牌スコアリングに
danger_override として直接フィードバックされる。

=== 実装済み高度読みアルゴリズム ===
1. 裏スジ (Ura-suji): カンチャン→リャンメン変化の痕跡検出
2. またぎスジ (Matagi-suji): 捨て牌を跨ぐリャンメン待ちの危険度
3. 間四軒 (Aida-yonken): 裏スジ複合による致死的危険領域
4. 安全度ランク (S/A/B/C/D): 多層絶対安全度スコアリング
5. 5切りリーチの両スジ罠: モロヒッカケ検知
6. 安全牌切りリーチの好形推測
7. 壁理論 (No Chance / One Chance)
8. 副露構造からの色手推測
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════
# 危険度階層定数
# ════════════════════════════════════════════
DANGER_S_RANK = 0.02   # S: 絶対安全（4枚見え字牌、現物）
DANGER_A_RANK = 0.10   # A: かなり安全（壁スジ、スジ1/9）
DANGER_B_RANK = 0.25   # B: 相対的安全（中スジ、壁外側）
DANGER_C_RANK = 0.45   # C: やや危険（通常スジ）
DANGER_D_RANK = 0.65   # D: 危険（スジ3/7、無スジ1/9）
DANGER_HIGH   = 0.75   # 高危険（またぎスジ、裏スジ）
DANGER_CRITICAL = 0.90 # 致命的（間四軒、モロヒッカケ）

# ════════════════════════════════════════════
# スジ関連マッピング
# ════════════════════════════════════════════

# 表スジ (1-4-7, 2-5-8, 3-6-9)
SUJI_MAP = {
    1: [4, 7], 2: [5, 8], 3: [6, 9],
    4: [1, 7], 5: [2, 8], 6: [3, 9],
    7: [1, 4], 8: [2, 5], 9: [3, 6],
}

# またぎスジ: 捨て牌Nを跨ぐリャンメン待ちの候補
# 例: 4切り → 2-5待ち(23持ち), 3-6待ち(56持ち) がマタギ
MATAGI_MAP = {
    1: [2, 3],
    2: [1, 3, 4, 5],
    3: [1, 2, 4, 5, 6],
    4: [2, 3, 5, 6, 7],
    5: [3, 4, 6, 7, 8],
    6: [4, 5, 7, 8, 9],
    7: [5, 6, 8, 9],
    8: [6, 7, 9],
    9: [7, 8],
}

# 裏スジ: カンチャン→リャンメン変化の痕跡
# 例: 1切り → 13持ち→1切り→3残し→2-5が裏スジ
URA_SUJI_MAP = {
    1: [(2, 5)],          # 1切り: 13→1切り→2-5が危険
    2: [(3, 6), (1, 4)],  # 2切り: 24→2切り→3-6, 12→2切り→1-4
    3: [(4, 7), (2, 5)],  # 3切り
    4: [(5, 8), (3, 6)],
    5: [(6, 9), (4, 7)],
    6: [(7, 4), (5, 8)],  # note: 7-4 adjusted for canonical order
    7: [(8, 5), (6, 9)],
    8: [(9, 6), (7, 4)],
    9: [(8, 5)],
}

# 間四軒 (あいだよんけん): 2つの裏スジが完全に一致する致命的パターン
# 河に A と A+5 がある場合、裏スジの交点が間四軒
AIDA_YONKEN_PAIRS = [
    (1, 6, 2, 5),  # 1切り&6切り → 2-5ラインが間四軒
    (2, 7, 3, 6),  # 2切り&7切り → 3-6ラインが間四軒
    (3, 8, 4, 7),  # 3切り&8切り → 4-7ラインが間四軒
    (4, 9, 5, 8),  # 4切り&9切り → 5-8ラインが間四軒
]


@dataclass
class WaitCandidate:
    """待ち候補の単位"""
    tile_id: str
    probability: float  # 0.0-1.0
    danger_level: str   # S / A / B / C / D / HIGH / CRITICAL
    reason: str = ""    # 人間向け解説の根拠キー

    def to_dict(self) -> Dict:
        return {
            "tile": self.tile_id,
            "prob": round(self.probability, 3),
            "danger": self.danger_level,
            "reason": self.reason,
        }


@dataclass
class SafetyRank:
    """安全度ランクの単位（仕様書6.2準拠）"""
    tile_id: str
    rank: str       # S / A / B / C / D
    score: float    # 0.0(安全) ~ 1.0(危険)
    reason: str

    def to_dict(self) -> Dict:
        return {
            "tile": self.tile_id,
            "rank": self.rank,
            "score": round(self.score, 3),
            "reason": self.reason,
        }


@dataclass
class ReadingResult:
    """読みエンジンの構造化出力"""
    reader_type: str = "opponent_read_v2"
    target_seat: int = -1
    triggered_rules: List[str] = field(default_factory=list)
    wait_candidates: List[WaitCandidate] = field(default_factory=list)
    safety_rankings: List[SafetyRank] = field(default_factory=list)
    hand_estimate: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    danger_map: Dict[str, float] = field(default_factory=dict)
    override_flags: List[str] = field(default_factory=list)
    xai_explanations: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "reader_type": self.reader_type,
            "target_seat": self.target_seat,
            "rules": self.triggered_rules,
            "wait_candidates": [w.to_dict() for w in self.wait_candidates[:8]],
            "safety_rankings": [s.to_dict() for s in self.safety_rankings[:5]],
            "hand_estimate": self.hand_estimate,
            "confidence": round(self.confidence, 2),
            "danger_overrides": len(self.danger_map),
            "override_flags": self.override_flags,
            "xai_explanations": self.xai_explanations[:3],
        }


class OpponentReader:
    """
    他家読みエンジン（v2: 仕様書6.2-6.4対応版）

    入力: GameState + 対象席
    出力: ReadingResult (待ち候補 + 安全度ランク + 危険度マップ)

    処理フロー:
      1. リーチ者の特定と宣言牌分析
      2. 裏スジ・またぎスジ・間四軒の検出
      3. 壁理論 (No Chance / One Chance) の計算
      4. 安全度ランク (S/A/B/C/D) の付与
      5. 副露構造分析（混一色/清一色検知）
      6. 終盤テンパイ気配検知
      7. XAI解説テンプレートの生成
    """

    def __init__(self, catalog_path: str = "server/rules/reading_catalog.json"):
        self.catalog = self._load_catalog(catalog_path)

    def _load_catalog(self, path: str) -> List[Dict]:
        if not os.path.exists(path):
            logger.warning(f"Reading catalog not found: {path}")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def read(self, gs: Any, seat: int) -> ReadingResult:
        """全他家に対する読みを統合して出力"""
        result = ReadingResult()
        result.target_seat = -1

        visible_34 = self._count_visible(gs, seat)

        for p in gs.players:
            if p.seat == seat:
                continue

            if p.is_riichi:
                self._analyze_riichi_player(p, gs, seat, visible_34, result)
                self._analyze_ura_suji(p, gs, seat, result)
                self._analyze_aida_yonken(p, gs, seat, result)
            elif len(p.melds) > 0:
                self._analyze_meld_player(p, gs, seat, visible_34, result)

            if gs.turn_count >= 12:
                self._analyze_late_tenpai(p, gs, seat, visible_34, result)

        # 壁安全度 → 安全度ランク計算の前に実行
        self._calculate_wall_safety(gs, seat, visible_34, result)

        # スジ安全度
        self._calculate_suji_safety(gs, seat, visible_34, result)

        # ★ 安全度ランク(S/A/B/C/D)の計算（仕様書6.2）
        self._calculate_safety_rankings(gs, seat, visible_34, result)

        # Confidence統合
        if result.triggered_rules:
            conf_sum = sum(
                r.get("confidence", 0.5)
                for r in self.catalog
                if r["id"] in result.triggered_rules
            )
            result.confidence = min(conf_sum / len(result.triggered_rules), 0.98)
        else:
            result.confidence = 0.3

        return result

    # ═══════════════════════════════════════════════
    # リーチ者分析
    # ═══════════════════════════════════════════════

    def _analyze_riichi_player(self, player, gs, seat: int,
                                visible_34: List[int], result: ReadingResult):
        """リーチ宣言牌・捨て牌パターンからの読み"""
        discards = player.discards
        if not discards:
            return

        result.target_seat = player.seat
        riichi_tile = discards[-1]
        turn = gs.turn_count

        # ── 5切りリーチの両スジ罠（モロヒッカケ）──
        if (riichi_tile.suit.value != 'z' and
            riichi_tile.number == 5 and turn >= 6):
            suit = riichi_tile.suit.value
            for n in [2, 8]:
                tid = f"{n}{suit}"
                result.danger_map[tid] = max(
                    result.danger_map.get(tid, 0), DANGER_CRITICAL
                )
            result.wait_candidates.append(
                WaitCandidate(f"2{suit}", 0.42, "CRITICAL",
                              "5切りリーチのモロヒッカケ(135リャンカン外し)")
            )
            result.wait_candidates.append(
                WaitCandidate(f"8{suit}", 0.38, "CRITICAL",
                              "5切りリーチのモロヒッカケ(579リャンカン外し)")
            )
            result.triggered_rules.append("READ_SUJI_RYAN_SUGI_5")
            result.override_flags.append(f"SUJI_CONFIDENCE_SCALE:0.4:{suit}")
            result.xai_explanations.append({
                "rule": "READ_SUJI_RYAN_SUGI_5",
                "text": f"5{suit}切りリーチは135/579リャンカン外しの可能性が高く、"
                        f"2{suit}・8{suit}がモロヒッカケ(直接当たり牌)です。"
                        f"スジ信頼度を0.4に引き下げて危険度を上昇させています。"
            })

        # ── 安全牌切りリーチの好形推測（仕様書6.4）──
        elif riichi_tile.suit.value == 'z':
            result.triggered_rules.append("READ_SAFE_TILE_RIICHI_KOUKEI")
            result.hand_estimate["wait_type"] = "ryanmen_or_better"
            result.hand_estimate["tenpai_prob"] = 0.95
            # 字牌を抱えていられた→好形一向聴からのリーチ→全無スジが高危険に
            for s in ['m', 'p', 's']:
                for n in range(1, 10):
                    tid = f"{n}{s}"
                    if tid not in result.danger_map:
                        # 無スジの危険度を通常時より上昇
                        result.danger_map[tid] = max(
                            result.danger_map.get(tid, 0), DANGER_D_RANK
                        )
            result.xai_explanations.append({
                "rule": "READ_SAFE_TILE_RIICHI_KOUKEI",
                "text": f"安全牌の{riichi_tile.id}を手出ししてリーチしました。"
                        f"安全牌を抱える余裕があった完全一向聴からの好形(リャンメン)リーチ"
                        f"と読み、すべての無スジに対する防御スコアを上昇させています。"
            })

        # ── 端牌宣言（1/9切り）→ ペンチャン/単騎推測 ──
        elif riichi_tile.number in (1, 9):
            result.triggered_rules.append("READ_RIICHI_DECL_TERM")
            result.hand_estimate["wait_type"] = "tanki_or_penchan"
            result.hand_estimate["tenpai_prob"] = 0.90

        # ── 中張宣言牌（3-7）→ マタギスジ危険 ──
        elif (riichi_tile.suit.value != 'z' and
              3 <= riichi_tile.number <= 7):
            suit = riichi_tile.suit.value
            num = riichi_tile.number
            matagi_targets = MATAGI_MAP.get(num, [])
            for mn in matagi_targets:
                tid = f"{mn}{suit}"
                result.danger_map[tid] = max(
                    result.danger_map.get(tid, 0), DANGER_HIGH
                )
            result.triggered_rules.append("READ_MATAGI_SUJI")
            result.xai_explanations.append({
                "rule": "READ_MATAGI_SUJI",
                "text": f"{riichi_tile.id}切りリーチのまたぎスジ"
                        f"({','.join(str(m) + suit for m in matagi_targets)})を"
                        f"高危険域としてマークしています。"
            })

        # ── 3/7切りの逆スジ ──
        if (riichi_tile.suit.value != 'z' and
            riichi_tile.number in (3, 7) and turn >= 8):
            suit = riichi_tile.suit.value
            num = riichi_tile.number
            reverse_suji = {3: [6, 9], 7: [1, 4]}.get(num, [])
            for rn in reverse_suji:
                tid = f"{rn}{suit}"
                result.danger_map[tid] = max(
                    result.danger_map.get(tid, 0), DANGER_HIGH
                )
            result.triggered_rules.append("READ_SUJI_GYAKU_SUGI")

        # ── スジ3・7の危険度警告（仕様書6.2 Dランク）──
        # スジであっても3/7はカンチャン・シャボ等4パターンに当たるリスク
        for d in discards:
            if d.suit.value == 'z':
                continue
            suit = d.suit.value
            for sn in SUJI_MAP.get(d.number, []):
                if sn in (3, 7):
                    tid = f"{sn}{suit}"
                    if tid not in result.danger_map:
                        result.danger_map[tid] = DANGER_D_RANK
                    if "READ_SUJI_37_WARNING" not in result.triggered_rules:
                        result.triggered_rules.append("READ_SUJI_37_WARNING")

        # ── 中張連続切り検知 ──
        mid_cut_count = sum(
            1 for d in discards[:-1]
            if d.suit.value != 'z' and 3 <= d.number <= 7
        )
        if mid_cut_count >= 2 and turn >= 5:
            result.triggered_rules.append("READ_MIDZANG_COMP")
            result.hand_estimate["tenpai_prob"] = min(
                result.hand_estimate.get("tenpai_prob", 0) + 0.35, 0.95
            )

    # ═══════════════════════════════════════════════
    # 裏スジ分析（仕様書6.3-1）
    # ═══════════════════════════════════════════════

    def _analyze_ura_suji(self, player, gs, seat: int, result: ReadingResult):
        """
        裏スジ（ウラスジ）: カンチャン待ち→リャンメン待ちへの変化の痕跡。

        例: 河に1が切られている場合、13持ち→1切り→3残し→2-5待ちが裏スジ。
        序盤に切られた牌ほど、ターツ整理の痕跡として危険度が高い。
        """
        discards = player.discards
        if not discards:
            return

        suit_discards = {}
        for i, d in enumerate(discards):
            if d.suit.value == 'z':
                continue
            key = d.suit.value
            if key not in suit_discards:
                suit_discards[key] = []
            suit_discards[key].append((d.number, i))  # (牌番号, 巡目インデックス)

        for suit, tile_list in suit_discards.items():
            for num, turn_idx in tile_list:
                ura_pairs = URA_SUJI_MAP.get(num, [])
                for pair in ura_pairs:
                    # 裏スジの両端を危険牌としてマーク
                    for target_num in pair:
                        if 1 <= target_num <= 9:
                            tid = f"{target_num}{suit}"
                            # 序盤の切り出しほど裏スジの信頼度が高い
                            if turn_idx <= 3:  # 序盤（1-4巡目）
                                danger = DANGER_HIGH
                            elif turn_idx <= 7:  # 中盤
                                danger = DANGER_D_RANK
                            else:  # 終盤
                                danger = DANGER_C_RANK

                            result.danger_map[tid] = max(
                                result.danger_map.get(tid, 0), danger
                            )

        if any(num in URA_SUJI_MAP for num, _ in
               [(d.number, 0) for d in discards if d.suit.value != 'z']):
            if "READ_URA_SUJI" not in result.triggered_rules:
                result.triggered_rules.append("READ_URA_SUJI")

    # ═══════════════════════════════════════════════
    # 間四軒分析（仕様書6.3-3）
    # ═══════════════════════════════════════════════

    def _analyze_aida_yonken(self, player, gs, seat: int, result: ReadingResult):
        """
        間四軒（あいだよんけん）: 2つの裏スジが完全に一致する致命的パターン。

        例: 河に1mと6mがある場合、
        1の裏スジ=2-5, 6の裏スジ=2-5 が一致 → 2m-5mは間四軒（致命的危険）
        放銃率を通常の2.5倍に引き上げる。
        """
        discards = player.discards
        if not discards:
            return

        # スート別に河の牌番号を収集
        suit_nums = {}
        for d in discards:
            if d.suit.value == 'z':
                continue
            s = d.suit.value
            if s not in suit_nums:
                suit_nums[s] = set()
            suit_nums[s].add(d.number)

        for suit, nums in suit_nums.items():
            for a, b, t1, t2 in AIDA_YONKEN_PAIRS:
                if a in nums and b in nums:
                    # 間四軒成立！
                    for target in [t1, t2]:
                        tid = f"{target}{suit}"
                        result.danger_map[tid] = max(
                            result.danger_map.get(tid, 0), DANGER_CRITICAL
                        )
                        result.wait_candidates.append(
                            WaitCandidate(
                                tid, 0.55, "CRITICAL",
                                f"間四軒({a}{suit}&{b}{suit}の裏スジ複合)"
                            )
                        )

                    if "READ_AIDA_YONKEN" not in result.triggered_rules:
                        result.triggered_rules.append("READ_AIDA_YONKEN")
                        result.xai_explanations.append({
                            "rule": "READ_AIDA_YONKEN",
                            "text": f"河に{a}{suit}と{b}{suit}が捨てられているため、"
                                    f"{t1}{suit}-{t2}{suit}のラインを『間四軒』と認識。"
                                    f"2つの裏スジが完全に複合したシグナルであり、"
                                    f"放銃率が劇的に跳ね上がるポイントです。"
                        })

    # ═══════════════════════════════════════════════
    # 副露者分析
    # ═══════════════════════════════════════════════

    def _analyze_meld_player(self, player, gs, seat: int,
                              visible_34: List[int], result: ReadingResult):
        """副露構造からの読み（混一色/清一色推測）"""
        melds = player.melds
        if not melds:
            return

        meld_suits = {}
        for m in melds:
            for t in m.tiles:
                s = t.suit.value
                meld_suits[s] = meld_suits.get(s, 0) + 1

        if meld_suits:
            dominant_suit = max(meld_suits, key=meld_suits.get)
            total = sum(meld_suits.values())
            concentration = meld_suits[dominant_suit] / total

            if concentration >= 0.8 and dominant_suit != 'z':
                result.triggered_rules.append("READ_FURO_HONITSU")
                for n in range(2, 9):
                    tid = f"{n}{dominant_suit}"
                    result.danger_map[tid] = max(
                        result.danger_map.get(tid, 0), DANGER_HIGH
                    )
                for s in ['m', 'p', 's']:
                    if s != dominant_suit:
                        for n in range(1, 10):
                            tid = f"{n}{s}"
                            if tid not in result.danger_map:
                                result.danger_map[tid] = DANGER_S_RANK
                result.override_flags.append(f"HONITSU_SUIT:{dominant_suit}")
                result.xai_explanations.append({
                    "rule": "READ_FURO_HONITSU",
                    "text": f"副露が{dominant_suit}スートに集中(80%以上)しています。"
                            f"混一色/清一色の可能性が高く、{dominant_suit}スートの"
                            f"中張牌は高危険、他スートは安全度が上昇しています。"
                })

    # ═══════════════════════════════════════════════
    # 終盤テンパイ気配
    # ═══════════════════════════════════════════════

    def _analyze_late_tenpai(self, player, gs, seat: int,
                              visible_34: List[int], result: ReadingResult):
        """終盤の安全牌切り出し→テンパイ気配検知"""
        if player.seat == seat:
            return

        discards = player.discards
        if len(discards) < 3:
            return

        recent = discards[-3:]
        safe_count = 0
        for d in recent:
            if d.suit.value == 'z':
                safe_count += 1
            elif d.number in (1, 9):
                safe_count += 1

        if safe_count >= 2 and not player.is_riichi:
            result.triggered_rules.append("READ_LATE_TENPAI")
            result.hand_estimate["tenpai_prob"] = max(
                result.hand_estimate.get("tenpai_prob", 0), 0.85
            )

    # ═══════════════════════════════════════════════
    # スジ安全度計算
    # ═══════════════════════════════════════════════

    def _calculate_suji_safety(self, gs, seat: int,
                                visible_34: List[int], result: ReadingResult):
        """リーチ者の捨て牌からスジ安全度を計算"""
        for p in gs.players:
            if p.seat == seat or not p.is_riichi:
                continue

            for d in p.discards:
                if d.suit.value == 'z':
                    continue
                suit = d.suit.value
                num = d.number

                for sn in SUJI_MAP.get(num, []):
                    tid = f"{sn}{suit}"
                    if tid not in result.danger_map:
                        # スジ3/7はDランク、1/9はAランク、その他はCランク
                        if sn in (3, 7):
                            suji_danger = DANGER_D_RANK
                        elif sn in (1, 9):
                            suji_danger = DANGER_A_RANK
                        else:
                            suji_danger = DANGER_C_RANK
                        result.danger_map[tid] = min(
                            result.danger_map.get(tid, 1.0), suji_danger
                        )

    # ═══════════════════════════════════════════════
    # 壁安全度計算（仕様書6.2 壁理論）
    # ═══════════════════════════════════════════════

    def _calculate_wall_safety(self, gs, seat: int,
                                visible_34: List[int], result: ReadingResult):
        """
        壁理論 (No Chance / One Chance)

        4枚見え → ノーチャンス: その牌を使った両面待ち構築は物理的に不可能
          例: 2の壁成立時、1に対する1-4待ちは不可能 → 1は壁スジ(Sランク)
          例: 3の壁成立時、1と2が安全(壁外スジ)
        3枚見え → ワンチャンス: 片側のみ安全度上昇(Bランク)
        """
        suits = ['m', 'p', 's']
        offsets = {'m': 0, 'p': 9, 's': 18}

        for suit in suits:
            off = offsets[suit]
            for num in range(1, 10):
                idx = off + num - 1
                vis = visible_34[idx]
                tid = f"{num}{suit}"

                if vis >= 4:
                    # ノーチャンス → 自身は0.0、隣接は壁スジ(Sランク)
                    result.danger_map[tid] = 0.0
                    for adj in [num - 1, num + 1]:
                        if 1 <= adj <= 9:
                            adj_tid = f"{adj}{suit}"
                            result.danger_map[adj_tid] = min(
                                result.danger_map.get(adj_tid, 1.0),
                                DANGER_S_RANK
                            )
                    # さらに壁の外側も安全度上昇
                    # 例: 3の壁 → 1, 2 が壁外スジ
                    if num >= 3:
                        for outer in range(1, num - 1):
                            outer_tid = f"{outer}{suit}"
                            result.danger_map[outer_tid] = min(
                                result.danger_map.get(outer_tid, 1.0),
                                DANGER_A_RANK
                            )
                    if num <= 7:
                        for outer in range(num + 2, 10):
                            outer_tid = f"{outer}{suit}"
                            result.danger_map[outer_tid] = min(
                                result.danger_map.get(outer_tid, 1.0),
                                DANGER_A_RANK
                            )

                    if "READ_KABE_NOCHANCE" not in result.triggered_rules:
                        result.triggered_rules.append("READ_KABE_NOCHANCE")

                elif vis >= 3:
                    # ワンチャンス → Bランク
                    result.danger_map[tid] = min(
                        result.danger_map.get(tid, 1.0), DANGER_B_RANK
                    )
                    if "READ_ONE_CHANCE" not in result.triggered_rules:
                        result.triggered_rules.append("READ_ONE_CHANCE")

    # ═══════════════════════════════════════════════
    # 安全度ランク計算（仕様書6.2完全準拠）
    # ═══════════════════════════════════════════════

    def _calculate_safety_rankings(self, gs, seat: int,
                                    visible_34: List[int],
                                    result: ReadingResult):
        """
        全牌に対して安全度ランク(S/A/B/C/D)を付与。

        S: 4枚見え字牌、現物、壁スジ → 国士以外絶対不当たり
        A: 3枚見え字牌、スジ1/9、壁外側 → 単騎/シャボのみ
        B: 中スジ、ワンチャンス外側 → 限定的なパターンのみ
        C: 通常スジ(4/5/6) → 愚形のみ当たるがリスクは中程度
        D: 無スジ1/9、スジ3/7 → カンチャン・ペンチャン・シャボ全パターン危険
        """
        hand = gs.players[seat].hand
        riichi_count = sum(1 for p in gs.players
                          if p.is_riichi and p.seat != seat)

        if riichi_count == 0:
            return  # リーチ者がいなければランク計算は不要

        for tile in hand:
            tid = tile.id
            danger = result.danger_map.get(tid, 0.5)

            # ランク判定
            if danger <= DANGER_S_RANK:
                rank, reason = "S", "現物/4枚見え壁スジ(絶対安全)"
            elif danger <= DANGER_A_RANK:
                rank, reason = "A", "壁外スジ/3枚見え字牌/スジ1・9"
            elif danger <= DANGER_B_RANK:
                rank, reason = "B", "ワンチャンス/中スジ(限定パターン)"
            elif danger <= DANGER_C_RANK:
                rank, reason = "C", "通常スジ(愚形のみ当たり)"
            else:
                rank, reason = "D", "無スジ/スジ3・7/裏スジ/間四軒"

            result.safety_rankings.append(
                SafetyRank(tid, rank, danger, reason)
            )

        # ランク順にソート（Sが先頭）
        rank_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
        result.safety_rankings.sort(key=lambda sr: rank_order.get(sr.rank, 5))

    # ═══════════════════════════════════════════════
    # 可視牌カウント
    # ═══════════════════════════════════════════════

    def _count_visible(self, gs, seat: int) -> List[int]:
        """場に見えている牌を34要素でカウント"""
        vis = [0] * 34
        suit_off = {'m': 0, 'p': 9, 's': 18, 'z': 27}

        for p in gs.players:
            for d in p.discards:
                idx = suit_off[d.suit.value] + d.number - 1
                if 0 <= idx < 34:
                    vis[idx] += 1
            for meld in p.melds:
                for t in meld.tiles:
                    idx = suit_off[t.suit.value] + t.number - 1
                    if 0 <= idx < 34:
                        vis[idx] += 1

        for t in gs.players[seat].hand:
            idx = suit_off[t.suit.value] + t.number - 1
            if 0 <= idx < 34:
                vis[idx] += 1

        for di in gs.dora_indicators:
            idx = suit_off[di.suit.value] + di.number - 1
            if 0 <= idx < 34:
                vis[idx] += 1

        return vis
