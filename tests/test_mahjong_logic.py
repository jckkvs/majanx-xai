"""
tests/test_mahjong_logic.py
mahjong_logic + 方向性2(Phase1+Phase2) + 方向性3 の実戦検証

テスト構成:
  1. 形状解析の正確性
  2. 翻数推定の妥当性
  3. 危険度計算の正確性
  4. build_full_context 統合テスト
  5. 方向性2: 戦略タグ判定(Phase1) + 具体的打牌選択(Phase2)
  6. 方向性3: 逆推論パターンマッチ
  7. 何切る問題: 実戦局面テスト
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.models import (
    Tile, TileSuit, Wind, GameState, PlayerState,
    tiles_from_str, tile_from_str
)
from server.utils.mahjong_logic import (
    analyze_shape, estimate_han, calculate_danger,
    has_yakuhai_pair_in_hand, find_genbutsu,
    estimate_ukeire, build_full_context, hand_to_34
)
from server.engines.strategy_judge import StrategyJudge
from server.engines.mortal_interpreter import MortalInterpreter
from server.engines.opponent_reader import OpponentReader


def _make_gs(hand_tiles, turn=5, dealer=0, honba=0,
             riichi_seats=None, scores=None, discards_map=None):
    """テスト用GameState生成ヘルパー"""
    players = []
    for i in range(4):
        h = hand_tiles if i == 0 else []
        sc = (scores or [25000]*4)[i]
        is_r = i in (riichi_seats or [])
        disc = (discards_map or {}).get(i, [])
        players.append(PlayerState(
            seat=i, hand=list(h), score=sc,
            is_riichi=is_r, discards=list(disc)
        ))
    return GameState(
        round_wind=Wind.EAST, round_number=0,
        honba=honba, dealer=dealer,
        players=players, current_player=0,
        turn_count=turn
    )


# ============================================================
# テスト1: 形状解析
# ============================================================

class TestShapeAnalysis(unittest.TestCase):

    def test_4_connected_form(self):
        hand = tiles_from_str("2345m678p11s")
        shape = analyze_shape(hand)
        self.assertTrue(shape["has_4_connected"])

    def test_no_4_connected(self):
        hand = tiles_from_str("13m579p11s")
        shape = analyze_shape(hand)
        self.assertFalse(shape["has_4_connected"])

    def test_nakabukure_detection(self):
        hand = tiles_from_str("2334m678p11s")
        shape = analyze_shape(hand)
        self.assertTrue(shape["has_nakabukure"])

    def test_ryanmen_count(self):
        hand = tiles_from_str("23m67p89s")
        shape = analyze_shape(hand)
        self.assertGreaterEqual(shape["ryanmen"], 3)

    def test_isolated_honor(self):
        hand = tiles_from_str("123m456p1z")
        shape = analyze_shape(hand)
        self.assertIn("1z", shape["isolated"])

    def test_dora_count(self):
        hand = [tile_from_str("5mr"), tile_from_str("5pr"),
                tile_from_str("1m"), tile_from_str("2m")]
        shape = analyze_shape(hand)
        self.assertEqual(shape["dora_count"], 2)


# ============================================================
# テスト2: 翻数推定
# ============================================================

class TestHanEstimation(unittest.TestCase):

    def test_tanyao_hand(self):
        hand = tiles_from_str("234m567p88s")
        gs = _make_gs(hand)
        current, potential = estimate_han(hand, gs, 0)
        self.assertGreaterEqual(current, 1)

    def test_dora_adds_han(self):
        hand = [tile_from_str("5mr"), tile_from_str("6m"),
                tile_from_str("7m"), tile_from_str("2p"),
                tile_from_str("3p"), tile_from_str("4p"),
                tile_from_str("8s"), tile_from_str("8s")]
        gs = _make_gs(hand)
        current, _ = estimate_han(hand, gs, 0)
        self.assertGreaterEqual(current, 1)

    def test_yakuhai_pair_potential(self):
        hand = tiles_from_str("123m456p77z")
        gs = _make_gs(hand)
        current, potential = estimate_han(hand, gs, 0)
        self.assertGreater(potential, current)


# ============================================================
# テスト3: 危険度計算
# ============================================================

class TestDangerCalculation(unittest.TestCase):

    def test_genbutsu_is_safe(self):
        hand = tiles_from_str("123m456p789s")
        target = tile_from_str("1m")
        gs = _make_gs(hand, riichi_seats=[1],
                      discards_map={1: [tile_from_str("1m")]})
        danger = calculate_danger(target, gs, 0)
        self.assertEqual(danger, 0.0)

    def test_wall_3_is_safe(self):
        hand = tiles_from_str("123m456p789s")
        target = tile_from_str("5m")
        gs = _make_gs(hand, discards_map={
            1: [tile_from_str("5m")],
            2: [tile_from_str("5m")],
            3: [tile_from_str("5m")],
        })
        danger = calculate_danger(target, gs, 0)
        self.assertLessEqual(danger, 0.1)

    def test_middle_tile_high_danger_under_riichi(self):
        hand = tiles_from_str("123m456p789s")
        target = tile_from_str("5p")
        gs = _make_gs(hand, riichi_seats=[1])
        danger = calculate_danger(target, gs, 0)
        self.assertGreaterEqual(danger, 0.7)


# ============================================================
# テスト4: build_full_context
# ============================================================

class TestBuildFullContext(unittest.TestCase):

    def test_context_has_all_keys(self):
        hand = tiles_from_str("2345m678p11s77z")
        gs = _make_gs(hand, turn=8)
        ctx = build_full_context(gs, 0)
        required_keys = [
            "turn", "dealer_status", "riichi", "score_diff",
            "rank", "honba", "danger",
            "current_han", "potential_han", "fu",
            "has_yakuhai_pair", "has_4_connected", "has_nakabukure",
            "is_genbutsu", "dora_count", "genbutsu_tiles",
            "hand_tiles", "isolated_tiles", "_gs", "_seat",
        ]
        for key in required_keys:
            self.assertIn(key, ctx, f"キー '{key}' が不足")

    def test_context_hand_tiles_populated(self):
        """hand_tilesに実際のTileオブジェクトが含まれる"""
        hand = tiles_from_str("2345m678p11s77z")
        gs = _make_gs(hand, turn=5)
        ctx = build_full_context(gs, 0)
        self.assertEqual(len(ctx["hand_tiles"]), len(hand))
        self.assertTrue(ctx["has_4_connected"])


# ============================================================
# テスト5: 方向性2 Phase1+Phase2
# ============================================================

class TestStrategyJudge(unittest.TestCase):

    def setUp(self):
        self.judge = StrategyJudge()

    def test_defense_under_double_riichi(self):
        """2本リーチ → DEFENSIVE_FOLD"""
        ctx = {
            "turn": 10, "dealer_status": False, "riichi": 2,
            "score_diff": 0, "rank": 2, "honba": 0, "danger": "high",
            "current_han": 1, "potential_han": 2, "fu": 30,
            "has_yakuhai_pair": False, "has_4_connected": False,
            "has_nakabukure": False, "is_genbutsu": True,
            "shanten": 2, "ryanmen_count": 1,
            "genbutsu_tiles": ["1m"], "hand_tiles": [],
            "isolated_tiles": [], "_gs": None, "_seat": 0,
        }
        result = self.judge.judge(ctx)
        self.assertEqual(result.strategy_type, "DEFENSIVE_FOLD")

    def _build_ctx_with_hand(self, hand, turn=5, riichi_seats=None, scores=None):
        """手牌からctxを生成するヘルパー"""
        gs = _make_gs(hand, turn=turn, riichi_seats=riichi_seats, scores=scores)
        return build_full_context(gs, 0)

    def test_concrete_tile_selection_defense(self):
        """DEFENSIVE_FOLD時に現物を具体的牌IDで選択"""
        hand = tiles_from_str("2345m678p11s77z")
        gs = _make_gs(hand, turn=10, riichi_seats=[1],
                      discards_map={1: [tile_from_str("1s")]})
        ctx = build_full_context(gs, 0)
        result = self.judge.judge(ctx)
        # 1sが現物なので、それが選択されるべき
        if result.strategy_type == "DEFENSIVE_FOLD":
            # 安全牌が選択されていること
            self.assertNotEqual(result.tile, "5m")  # デフォルトではない

    def test_value_push_with_yakuhai(self):
        """役牌対子+潜在3翻 → VALUE_PUSH"""
        ctx = {
            "turn": 5, "dealer_status": False, "riichi": 0,
            "score_diff": 0, "rank": 2, "honba": 0, "danger": "low",
            "current_han": 2, "potential_han": 5, "fu": 30,
            "has_yakuhai_pair": True, "has_4_connected": False,
            "has_nakabukure": False, "is_genbutsu": False,
            "shanten": 1, "ryanmen_count": 2,
            "genbutsu_tiles": [], "hand_tiles": [],
            "isolated_tiles": [], "_gs": None, "_seat": 0,
        }
        result = self.judge.judge(ctx)
        self.assertIn(result.strategy_type, ["VALUE_PUSH", "SPEED_PUSH"])
        self.assertTrue(result.han_evaluation.get("mangan_reachable", False))

    def test_tile_scores_populated(self):
        """Phase2で tile_scores が出力される"""
        hand = tiles_from_str("2345m678p19s14z")
        gs = _make_gs(hand, turn=5)
        ctx = build_full_context(gs, 0)
        result = self.judge.judge(ctx)
        self.assertGreater(len(result.tile_scores), 0,
                           "tile_scoresが空でない(Phase2が実行された)")
        # 選択された牌が手牌に含まれること
        hand_ids = [t.id for t in hand]
        self.assertIn(result.tile, hand_ids,
                      f"推奨牌 {result.tile} が手牌 {hand_ids} に含まれる")

    def test_isolated_honor_prioritized(self):
        """孤立字牌(客風)が優先的に切られる"""
        hand = tiles_from_str("2345m678p11s1z")
        gs = _make_gs(hand, turn=3)
        ctx = build_full_context(gs, 0)
        result = self.judge.judge(ctx)
        # 孤立字牌(1z=東の客風)が最優先で切られるべき
        self.assertEqual(result.tile, "1z",
                         "孤立字牌(客風)が最優先で切られる")

    def test_dora_not_discarded_in_value_push(self):
        """VALUE_PUSH時にドラは切られない"""
        hand = [
            tile_from_str("5mr"), tile_from_str("6m"), tile_from_str("7m"),
            tile_from_str("2p"), tile_from_str("3p"), tile_from_str("4p"),
            tile_from_str("7z"), tile_from_str("7z"),  # 中の対子
            tile_from_str("1s"), tile_from_str("9s"),
            tile_from_str("1z"), tile_from_str("2z"), tile_from_str("3z"),
        ]
        gs = _make_gs(hand, turn=5)
        ctx = build_full_context(gs, 0)
        result = self.judge.judge(ctx)
        self.assertNotEqual(result.tile, "5mr",
                            "ドラ(赤5m)は切られない")

    def test_confidence_range(self):
        ctx = {
            "turn": 12, "dealer_status": True, "riichi": 1,
            "score_diff": -5000, "rank": 3, "honba": 2, "danger": "med",
            "current_han": 1, "potential_han": 3, "fu": 30,
            "has_yakuhai_pair": False, "has_4_connected": False,
            "has_nakabukure": False, "is_genbutsu": True,
            "shanten": 1, "ryanmen_count": 2,
            "genbutsu_tiles": ["1m"], "hand_tiles": [],
            "isolated_tiles": [], "_gs": None, "_seat": 0,
        }
        result = self.judge.judge(ctx)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)


# ============================================================
# テスト6: 方向性3
# ============================================================

class TestMortalInterpreter(unittest.TestCase):

    def setUp(self):
        self.interp = MortalInterpreter()

    def test_defense_interpretation_under_riichi(self):
        ctx = {
            "turn": 10, "riichi": 1, "danger": "high",
            "current_han": 1, "potential_han": 2,
            "is_genbutsu": True, "has_yakuhai_pair": False,
            "has_4_connected": False, "has_nakabukure": False,
        }
        result = self.interp.interpret("1m", 0.7, ctx)
        self.assertEqual(result.category, "DEFENSE")
        self.assertGreater(result.confidence_score, 0.5)

    def test_4renkei_shape_trigger(self):
        """4連形がある局面でINT_4RENKEI_CUTがマッチ"""
        ctx = {
            "turn": 3, "riichi": 0, "danger": "low",
            "current_han": 0, "potential_han": 1,
            "is_genbutsu": False, "has_yakuhai_pair": False,
            "has_4_connected": True, "has_nakabukure": False,
        }
        result = self.interp.interpret("9s", 0.3, ctx)
        self.assertEqual(result.category, "EFFICIENCY")
        # INT_4RENKEI_CUTがマッチしているはず
        self.assertTrue(any("4RENKEI" in r for r in result.matched_rules),
                        f"4RENKEIパターンがマッチすべき: {result.matched_rules}")

    def test_nakabukure_shape_trigger(self):
        """中膨れ局面でINT_NAKA_FUKURE_KEEPがマッチ"""
        ctx = {
            "turn": 5, "riichi": 0, "danger": "low",
            "current_han": 0, "potential_han": 1,
            "is_genbutsu": False, "has_yakuhai_pair": False,
            "has_4_connected": False, "has_nakabukure": True,
        }
        result = self.interp.interpret("1z", 0.25, ctx)
        self.assertTrue(any("NAKA_FUKURE" in r for r in result.matched_rules),
                        f"NAKA_FUKUREパターンがマッチすべき: {result.matched_rules}")

    def test_interpretation_text_not_empty(self):
        ctx = {
            "turn": 8, "riichi": 0, "danger": "low",
            "current_han": 1, "potential_han": 2,
            "is_genbutsu": False, "has_yakuhai_pair": False,
            "has_4_connected": False, "has_nakabukure": False,
        }
        result = self.interp.interpret("5m", 0.5, ctx)
        self.assertTrue(len(result.text) > 0)
        self.assertIn("5m", result.text)

    def test_output_structure(self):
        ctx = {
            "turn": 6, "riichi": 0, "danger": "low",
            "current_han": 0, "potential_han": 0,
            "is_genbutsu": False, "has_yakuhai_pair": False,
            "has_4_connected": False, "has_nakabukure": False,
        }
        result = self.interp.interpret("7z", 0.2, ctx)
        for attr in ['tile', 'text', 'confidence', 'confidence_score',
                      'intents', 'matched_rules', 'category', 'han_context']:
            self.assertTrue(hasattr(result, attr), f"属性 {attr} が不在")


# ============================================================
# テスト7: 何切る問題（実戦局面テスト）
# ============================================================

class TestNaniKiru(unittest.TestCase):
    """
    実戦的な何切る問題でPhase1+Phase2の整合性を検証。
    「この手牌・この局面なら、この牌を切るべき」を検証する。
    """

    def setUp(self):
        self.judge = StrategyJudge()

    def test_tc01_4renkei_isolated_honor_cut(self):
        """TC01: 2345m678p11s + 孤立字牌 → 孤立字牌を切る（4連形維持）"""
        hand = tiles_from_str("2345m678p11s3z")
        gs = _make_gs(hand, turn=3)
        ctx = build_full_context(gs, 0)
        result = self.judge.judge(ctx)
        # 孤立字牌(3z=西)が切られるべき
        self.assertEqual(result.tile, "3z",
                         f"4連形維持のため孤立字牌3zが最優先: got {result.tile}")

    def test_tc02_riichi_genbutsu(self):
        """TC02: 他家リーチ + 手牌に現物あり → 現物を切る"""
        hand = tiles_from_str("2345m678p19s1z")
        riichi_discards = [tile_from_str("1s")]  # 1sが現物
        gs = _make_gs(hand, turn=10, riichi_seats=[1],
                      discards_map={1: riichi_discards})
        ctx = build_full_context(gs, 0)
        result = self.judge.judge(ctx)
        self.assertEqual(result.strategy_type, "DEFENSIVE_FOLD",
                         "他家リーチ下はDEFENSIVE_FOLD")
        self.assertEqual(result.tile, "1s",
                         f"現物(1s)が最優先で切られるべき: got {result.tile}")

    def test_tc03_dora_preservation(self):
        """TC03: ドラを含む手で孤立字牌を切る（ドラ保持）"""
        hand = [
            tile_from_str("5mr"), tile_from_str("6m"), tile_from_str("7m"),
            tile_from_str("2p"), tile_from_str("3p"), tile_from_str("4p"),
            tile_from_str("5s"), tile_from_str("6s"),
            tile_from_str("1z"), tile_from_str("3z"),
        ]
        gs = _make_gs(hand, turn=4)
        ctx = build_full_context(gs, 0)
        result = self.judge.judge(ctx)
        # ドラ(5mr)は切られない
        self.assertNotEqual(result.tile, "5mr",
                            "ドラは温存される")
        # 孤立字牌が切られるべき
        self.assertIn(result.tile, ["1z", "3z"],
                      f"孤立字牌が切られるべき: got {result.tile}")



# ============================================================
# テスト8: 方向性4（他家読み・待ち推定エンジン）
# ============================================================

class TestOpponentReader(unittest.TestCase):
    """
    方向性4エンジンの実戦検証。
    仕様書6.2-6.4の戦術ルールベースに基づくテスト。
    """

    def setUp(self):
        self.reader = OpponentReader()

    def test_5_cut_riichi_morohikkake(self):
        """5切りリーチ→モロヒッカケ(2,8が致命的危険)"""
        hand = tiles_from_str("2345m678p11s77z")
        discards_1 = [tile_from_str("3p"), tile_from_str("1z"),
                       tile_from_str("5m")]  # 5m切りリーチ
        gs = _make_gs(hand, turn=8, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        self.assertIn("READ_SUJI_RYAN_SUGI_5", result.triggered_rules)
        self.assertGreaterEqual(result.danger_map.get("2m", 0), 0.85,
                                "2mがモロヒッカケ危険牌")
        self.assertGreaterEqual(result.danger_map.get("8m", 0), 0.85,
                                "8mがモロヒッカケ危険牌")

    def test_safe_tile_riichi_koukei(self):
        """字牌切りリーチ→好形(リャンメン)推測→全無スジ危険度上昇"""
        hand = tiles_from_str("2345m678p11s")
        discards_1 = [tile_from_str("3p"), tile_from_str("1z")]  # 字牌切りリーチ
        gs = _make_gs(hand, turn=7, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        self.assertIn("READ_SAFE_TILE_RIICHI_KOUKEI", result.triggered_rules)
        self.assertEqual(result.hand_estimate.get("wait_type"),
                         "ryanmen_or_better")

    def test_ura_suji_detection(self):
        """裏スジ検出：序盤の1切り→2-5が裏スジとして高危険"""
        hand = tiles_from_str("2345m678p11s77z")
        # 序盤に1mを切っている → 13mのカンチャン→1m切り→2-5が裏スジ
        discards_1 = [tile_from_str("1m"), tile_from_str("9s"),
                       tile_from_str("4p")]  # 4p切りリーチ
        gs = _make_gs(hand, turn=8, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        self.assertIn("READ_URA_SUJI", result.triggered_rules)
        # 2mと5mが裏スジとして危険度上昇
        self.assertGreater(result.danger_map.get("2m", 0), 0.3,
                           "2mが裏スジとして危険度上昇")
        self.assertGreater(result.danger_map.get("5m", 0), 0.3,
                           "5mが裏スジとして危険度上昇")

    def test_aida_yonken_detection(self):
        """間四軒検出：河に1mと6mがある→2m-5mが致命的危険"""
        hand = tiles_from_str("2345m678p11s77z")
        discards_1 = [tile_from_str("1m"), tile_from_str("6m"),
                       tile_from_str("3p")]  # 3p切りリーチ
        gs = _make_gs(hand, turn=10, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        self.assertIn("READ_AIDA_YONKEN", result.triggered_rules)
        # 2mと5mが間四軒の致命的危険牌
        self.assertGreaterEqual(result.danger_map.get("2m", 0), 0.85,
                                "2mが間四軒で致命的危険")
        self.assertGreaterEqual(result.danger_map.get("5m", 0), 0.85,
                                "5mが間四軒で致命的危険")

    def test_wall_nochance_safety(self):
        """壁理論(ノーチャンス)：4枚見え→隣接牌がSランク安全"""
        hand = tiles_from_str("2345m678p11s77z")
        # 2mが4枚見え → 1mは壁スジで安全
        discards_all = {
            1: [tile_from_str("2m"), tile_from_str("2m")],
            2: [tile_from_str("2m")],
            3: [tile_from_str("2m")],
        }
        gs = _make_gs(hand, turn=8, riichi_seats=[1],
                      discards_map=discards_all)
        result = self.reader.read(gs, 0)
        self.assertIn("READ_KABE_NOCHANCE", result.triggered_rules)
        # 1mが壁スジで安全 (Sランクに近い値)
        self.assertLessEqual(result.danger_map.get("1m", 1.0), 0.10,
                             "1mが壁スジで安全")

    def test_one_chance_safety(self):
        """ワンチャンス(3枚見え)→Bランク安全"""
        hand = tiles_from_str("2345m678p11s77z")
        discards_all = {
            1: [tile_from_str("4p"), tile_from_str("4p")],
            2: [tile_from_str("4p")],
        }
        gs = _make_gs(hand, turn=8, riichi_seats=[1],
                      discards_map=discards_all)
        result = self.reader.read(gs, 0)
        self.assertIn("READ_ONE_CHANCE", result.triggered_rules)
        # 4pが3枚見えでBランク安全
        self.assertLessEqual(result.danger_map.get("4p", 1.0), 0.30,
                             "4pがワンチャンスでBランク")

    def test_safety_ranking_order(self):
        """安全度ランクがS→A→B→C→Dの順にソートされる"""
        hand = tiles_from_str("1234m5678p19s1z")
        discards_1 = [tile_from_str("1m")]  # 1mが現物
        gs = _make_gs(hand, turn=10, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        if result.safety_rankings:
            ranks = [sr.rank for sr in result.safety_rankings]
            rank_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
            orders = [rank_order[r] for r in ranks]
            self.assertEqual(orders, sorted(orders),
                             "安全度ランクがS→Dの順にソートされている")

    def test_suji_37_warning(self):
        """スジ3・7はDランク(カンチャン・シャボ等に当たるリスク)"""
        hand = tiles_from_str("1234m5678p19s1z")
        # 6mが河にある → 3mと9mがスジ。3mはDランク
        discards_1 = [tile_from_str("6m"), tile_from_str("2p")]
        gs = _make_gs(hand, turn=8, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        # 3mがスジ3としてDランク危険
        d3m = result.danger_map.get("3m", 0)
        d9m = result.danger_map.get("9m", 0)
        self.assertGreater(d3m, d9m,
                           "スジ3(3m)はスジ9(9m)より高危険")

    def test_furo_honitsu_detection(self):
        """副露が同一スート集中→混一色推測→他スート安全"""
        hand = tiles_from_str("2345m678p11s77z")
        gs = _make_gs(hand, turn=8)
        # player 1 に萬子の副露を設定
        from server.models import Meld, MeldType
        gs.players[1].melds = [
            Meld(meld_type=MeldType.CHI, tiles=[
                tile_from_str("1m"), tile_from_str("2m"), tile_from_str("3m")
            ]),
            Meld(meld_type=MeldType.PON, tiles=[
                tile_from_str("5m"), tile_from_str("5m"), tile_from_str("5m")
            ]),
        ]
        result = self.reader.read(gs, 0)
        self.assertIn("READ_FURO_HONITSU", result.triggered_rules)
        # 他スート(p, s)は安全
        self.assertLessEqual(result.danger_map.get("5p", 1.0), 0.10,
                             "他スートは安全")

    def test_xai_explanations_generated(self):
        """XAI解説テンプレートが生成される"""
        hand = tiles_from_str("2345m678p11s77z")
        discards_1 = [tile_from_str("3p"), tile_from_str("1z"),
                       tile_from_str("5m")]  # 5m切りリーチ
        gs = _make_gs(hand, turn=8, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        self.assertGreater(len(result.xai_explanations), 0,
                           "XAI解説が1件以上生成されている")
        self.assertIn("rule", result.xai_explanations[0])
        self.assertIn("text", result.xai_explanations[0])

    def test_reading_result_structure(self):
        """ReadingResult.to_dict()の構造が正しい"""
        hand = tiles_from_str("2345m678p11s77z")
        gs = _make_gs(hand, turn=5)
        result = self.reader.read(gs, 0)
        d = result.to_dict()
        required_keys = [
            "reader_type", "target_seat", "rules", "wait_candidates",
            "safety_rankings", "hand_estimate", "confidence",
            "danger_overrides", "override_flags", "xai_explanations",
        ]
        for key in required_keys:
            self.assertIn(key, d, f"ReadingResult.to_dict()にキー'{key}'が必要")

    def test_danger_map_fed_to_strategy(self):
        """読みのdanger_mapがctxに注入可能であることを確認"""
        hand = tiles_from_str("2345m678p11s77z")
        discards_1 = [tile_from_str("5m")]  # 5m切りリーチ
        gs = _make_gs(hand, turn=8, riichi_seats=[1],
                      discards_map={1: discards_1})
        result = self.reader.read(gs, 0)
        # danger_map が実際に辞書形式であること
        self.assertIsInstance(result.danger_map, dict)
        # 少なくとも1エントリが存在
        self.assertGreater(len(result.danger_map), 0,
                           "danger_mapに危険度データが存在")

    def test_late_tenpai_detection(self):
        """終盤のダマテン気配検知"""
        hand = tiles_from_str("2345m678p11s77z")
        # player 2が終盤に字牌/端牌を連続で切っている
        discards_2 = [
            tile_from_str("1z"), tile_from_str("2z"), tile_from_str("3z"),
            tile_from_str("9s"), tile_from_str("1s"), tile_from_str("4z"),
        ]
        gs = _make_gs(hand, turn=14, discards_map={2: discards_2})
        result = self.reader.read(gs, 0)
        self.assertIn("READ_LATE_TENPAI", result.triggered_rules)
        self.assertGreaterEqual(
            result.hand_estimate.get("tenpai_prob", 0), 0.8,
            "終盤のダマテン確率が80%以上"
        )

# ============================================================
# テスト8: パラダイムエンジン
# ============================================================

class TestParadigmEngine(unittest.TestCase):
    def setUp(self):
        from server.engines.paradigm_engine import ParadigmEngine
        self.engine = ParadigmEngine()

    def test_l1_double_riichi_forces_defense(self):
        """L1: 2本リーチ → 無条件PAR_DEF"""
        ctx = {"riichi": 2, "current_han": 3, "is_genbutsu": True,
               "turn": 8, "shanten": 1, "ryanmen_count": 2,
               "rank": 2, "score_diff": 0, "dealer_status": False,
               "potential_han": 5, "has_yakuhai_pair": False}
        result = self.engine.determine(ctx)
        self.assertEqual(result.primary, "PAR_DEF")
        self.assertEqual(result.constraint_level, "L1")

    def test_l1_single_riichi_low_han_defense(self):
        """L1: 1本リーチ+低打点+現物 → PAR_DEF"""
        ctx = {"riichi": 1, "current_han": 1, "is_genbutsu": True,
               "turn": 8, "shanten": 2, "ryanmen_count": 1,
               "rank": 3, "score_diff": -3000, "dealer_status": False,
               "potential_han": 2, "has_yakuhai_pair": False}
        result = self.engine.determine(ctx)
        self.assertEqual(result.primary, "PAR_DEF")

    def test_l2_early_speed(self):
        """L2: 序盤 → PAR_SPEED"""
        ctx = {"riichi": 0, "current_han": 0, "is_genbutsu": False,
               "turn": 3, "shanten": 3, "ryanmen_count": 2,
               "rank": 2, "score_diff": 0, "dealer_status": False,
               "potential_han": 1, "has_yakuhai_pair": False}
        result = self.engine.determine(ctx)
        self.assertEqual(result.primary, "PAR_SPEED")

    def test_l2_late_defense(self):
        """L2: 終盤 → PAR_DEF"""
        ctx = {"riichi": 0, "current_han": 0, "is_genbutsu": False,
               "turn": 14, "shanten": 2, "ryanmen_count": 1,
               "rank": 2, "score_diff": 0, "dealer_status": False,
               "potential_han": 1, "has_yakuhai_pair": False}
        result = self.engine.determine(ctx)
        self.assertEqual(result.primary, "PAR_DEF")

    def test_l3_top_position_pressure(self):
        """L3: トップ+大差 → PAR_POS"""
        ctx = {"riichi": 0, "current_han": 1, "is_genbutsu": False,
               "turn": 8, "shanten": 2, "ryanmen_count": 1,
               "rank": 1, "score_diff": 8000, "dealer_status": False,
               "potential_han": 2, "has_yakuhai_pair": False}
        result = self.engine.determine(ctx)
        # L3のPAR_POSかL2のどちらかが勝つ（L2が優先）
        self.assertIn(result.primary, ["PAR_POS", "PAR_SPEED", "PAR_VALUE"])

    def test_paradigm_result_has_all_fields(self):
        """ParadigmResultに必要なフィールドが全て存在"""
        ctx = {"riichi": 0, "current_han": 0, "is_genbutsu": False,
               "turn": 5, "shanten": 2, "ryanmen_count": 2,
               "rank": 2, "score_diff": 0, "dealer_status": False,
               "potential_han": 1, "has_yakuhai_pair": False}
        result = self.engine.determine(ctx)
        d = result.to_dict()
        for key in ["primary", "secondary", "constraint_level",
                     "heuristics", "memory_phrase", "triggers",
                     "core_principle", "meta_question", "name_ja"]:
            self.assertIn(key, d, f"Missing key: {key}")


# ============================================================
# テスト9: 境界条件検出エンジン
# ============================================================

class TestBoundaryDetector(unittest.TestCase):
    def setUp(self):
        from server.engines.boundary_detector import BoundaryDetector
        self.detector = BoundaryDetector()

    def test_turn_advance_boundary(self):
        """巡目進行の境界条件検出"""
        ctx = {"turn": 11, "riichi": 0, "_gs": None, "_seat": 0,
               "hand_tiles": [], "rank": 2, "score_diff": 0}
        bc = self.detector.detect(ctx, "3m", "PAR_SPEED")
        self.assertIsNotNone(bc)
        self.assertEqual(bc.change_axis, "巡目進行")

    def test_riichi_addition_boundary(self):
        """リーチ追加の境界条件検出"""
        ctx = {"turn": 8, "riichi": 0, "_gs": None, "_seat": 0,
               "hand_tiles": [], "rank": 2, "score_diff": 0}
        bc = self.detector.detect(ctx, "3m", "PAR_SPEED")
        self.assertIsNotNone(bc)
        # 巡目進行 or リーチ追加のいずれか
        self.assertIn(bc.change_axis, ["巡目進行", "他家状態"])

    def test_anko_suji_trap_detection(self):
        """暗刻スジ罠の検出"""
        hand = tiles_from_str("666m123p789s11z")
        ctx = {"turn": 8, "riichi": 1, "_gs": None, "_seat": 0,
               "hand_tiles": hand, "rank": 2, "score_diff": 0}
        bc = self.detector.detect(ctx, "3m", "PAR_DEF")
        # 暗刻スジ罠：6mを3枚持っており3mを切ろうとしている
        if bc and bc.boundary_id == "BOUNDARY_ANKO_SUJI_TRAP":
            self.assertEqual(bc.change_axis, "手牌構成")
            self.assertGreaterEqual(bc.sensitivity, 0.85)

    def test_no_boundary_defensive(self):
        """防御中はリーチ境界条件を出さない"""
        ctx = {"turn": 8, "riichi": 1, "_gs": None, "_seat": 0,
               "hand_tiles": [], "rank": 2, "score_diff": 0}
        bc = self.detector.detect(ctx, "1z", "PAR_DEF")
        # PAR_DEF中はリーチ追加の境界は出ない（既にリーチあり）
        if bc:
            self.assertNotEqual(bc.boundary_id, "BOUNDARY_RIICHI_ADD")

    def test_boundary_result_structure(self):
        """BoundaryConditionの出力構造チェック"""
        ctx = {"turn": 11, "riichi": 0, "_gs": None, "_seat": 0,
               "hand_tiles": [], "rank": 2, "score_diff": 0}
        bc = self.detector.detect(ctx, "3m", "PAR_SPEED")
        if bc:
            d = bc.to_dict()
            for key in ["id", "axis", "description", "check", "flip_to"]:
                self.assertIn(key, d, f"Missing key: {key}")


# ============================================================
# テスト10: 4層出力フォーマッター
# ============================================================

class TestOutputFormatter(unittest.TestCase):
    def setUp(self):
        from server.engines.output_formatter import OutputFormatter
        from server.engines.paradigm_engine import ParadigmResult
        self.formatter = OutputFormatter()
        self.mock_paradigm = ParadigmResult(
            primary="PAR_SPEED", secondary="PAR_DEF",
            constraint_level="L2",
            heuristics=["両面を崩すな", "孤立端牌優先切り"],
            memory_phrase="早く和了る手が最も期待値が高い",
            triggers=["5巡目", "受入最大化"],
            core_principle="受入を最大化し聴牌を早める",
            meta_question="両面維持が正しいか？",
            name_ja="速度軸"
        )

    def test_four_layer_output_structure(self):
        """4層出力に全層が存在"""
        result = self.formatter.format(
            tile="3m",
            paradigm_result=self.mock_paradigm,
            strategy_result=None,
            reading_result=None,
            boundary_result=None,
            ctx={"turn": 5, "shanten": 2, "ryanmen_count": 2,
                 "riichi": 0, "genbutsu_tiles": [],
                 "has_yakuhai_pair": False, "dora_count": 0,
                 "potential_han": 1, "current_han": 0,
                 "rank": 2, "score_diff": 0,
                 "reading_override_flags": [],
                 "reading_danger_map": {}}
        )
        d = result.to_dict()
        for layer in ["tile", "qualitative", "checklist",
                       "quantitative", "boundary"]:
            self.assertIn(layer, d, f"Missing layer: {layer}")

    def test_qualitative_layer_content(self):
        """定性フレームワークに必要情報が含まれる"""
        result = self.formatter.format(
            tile="3m", paradigm_result=self.mock_paradigm,
            strategy_result=None, reading_result=None,
            boundary_result=None,
            ctx={"turn": 5, "shanten": 2, "ryanmen_count": 2,
                 "riichi": 0, "genbutsu_tiles": [],
                 "has_yakuhai_pair": False, "dora_count": 0,
                 "potential_han": 1, "current_han": 0,
                 "rank": 2, "score_diff": 0,
                 "reading_override_flags": [],
                 "reading_danger_map": {}}
        )
        q = result.qualitative.to_dict()
        self.assertEqual(q["paradigm"], "PAR_SPEED")
        self.assertIn("meta_question", q)
        self.assertIn("memory_phrase", q)

    def test_checklist_max_3_items(self):
        """チェックリストが3項目以下"""
        result = self.formatter.format(
            tile="3m", paradigm_result=self.mock_paradigm,
            strategy_result=None, reading_result=None,
            boundary_result=None,
            ctx={"turn": 5, "shanten": 2, "ryanmen_count": 2,
                 "riichi": 0, "genbutsu_tiles": [],
                 "has_yakuhai_pair": False, "dora_count": 0,
                 "potential_han": 1, "current_han": 0,
                 "rank": 2, "score_diff": 0,
                 "reading_override_flags": [],
                 "reading_danger_map": {}}
        )
        items = result.checklist.to_dict()["items"]
        self.assertLessEqual(len(items), 3)

    def test_quantitative_placeholder(self):
        """定量データがプレースホルダー状態であること"""
        result = self.formatter.format(
            tile="3m", paradigm_result=self.mock_paradigm,
            strategy_result=None, reading_result=None,
            boundary_result=None,
            ctx={"turn": 5, "shanten": 2, "ryanmen_count": 2,
                 "riichi": 0, "genbutsu_tiles": [],
                 "has_yakuhai_pair": False, "dora_count": 0,
                 "potential_han": 1, "current_han": 0,
                 "rank": 2, "score_diff": 0,
                 "reading_override_flags": [],
                 "reading_danger_map": {}}
        )
        self.assertFalse(result.quantitative.available)


# ============================================================
# テスト11: 振聴判定エンジン
# ============================================================

class TestFuritenChecker(unittest.TestCase):
    def setUp(self):
        from server.utils.furiten_checker import FuritenChecker
        self.checker = FuritenChecker()

    def test_no_furiten_when_no_waits(self):
        """待ち牌なし → 振聴なし"""
        hand = tiles_from_str("123m456p789s11z")
        gs = _make_gs(hand, turn=10)
        result = self.checker.check(gs, 0)
        self.assertFalse(result.is_furiten)

    def test_type_a_furiten_detected(self):
        """TypeA振聴: 待ち牌が自分の捨て牌にある"""
        hand = tiles_from_str("123m456p789s11z")
        discards_0 = [tile_from_str("3m")]
        gs = _make_gs(hand, turn=10, discards_map={0: discards_0})
        result = self.checker.check(gs, 0, wait_tiles=["3m", "6m"])
        self.assertTrue(result.is_furiten)
        self.assertEqual(result.furiten_type, "TypeA")
        self.assertIn("3m", result.furiten_tiles)
        self.assertIn("6m", result.safe_waits)

    def test_full_furiten(self):
        """全振聴: 全ての待ちが振聴"""
        hand = tiles_from_str("123m456p789s11z")
        discards_0 = [tile_from_str("3m"), tile_from_str("6m")]
        gs = _make_gs(hand, turn=10, discards_map={0: discards_0})
        result = self.checker.check(gs, 0, wait_tiles=["3m", "6m"])
        self.assertTrue(result.is_full_furiten)

    def test_no_furiten(self):
        """振聴なし"""
        hand = tiles_from_str("123m456p789s11z")
        gs = _make_gs(hand, turn=10)
        result = self.checker.check(gs, 0, wait_tiles=["3m", "6m"])
        self.assertFalse(result.is_furiten)

    def test_furiten_safe_discards(self):
        """降り時の振聴安全牌列挙"""
        hand = tiles_from_str("123m456p789s11z")
        discards_0 = [tile_from_str("1m")]
        gs = _make_gs(hand, turn=10, discards_map={0: discards_0})
        safe = self.checker.find_furiten_safe_discards(gs, 0)
        # 手牌の1mが自分の捨て牌にある→振聴安全牌
        self.assertIn("1m", safe)


# ============================================================
# テスト12: 終局管理エンジン
# ============================================================

class TestEndgameAnalyzer(unittest.TestCase):
    def setUp(self):
        from server.utils.endgame_analyzer import EndgameAnalyzer
        self.analyzer = EndgameAnalyzer()

    def test_not_endgame_early(self):
        """序盤は終局判定なし"""
        hand = tiles_from_str("123m456p789s11z")
        gs = _make_gs(hand, turn=5)
        result = self.analyzer.analyze(gs, 0)
        self.assertFalse(result.is_endgame)

    def test_endgame_south_4(self):
        """南4局は終局判定あり"""
        hand = tiles_from_str("123m456p789s11z")
        gs = _make_gs(hand, turn=10)
        # round_wind=SOUTH, dealer=3 → 南4局（最終局）
        gs.round_wind = Wind.SOUTH
        gs.dealer = 3
        result = self.analyzer.analyze(gs, 0)
        self.assertTrue(result.is_endgame)
        self.assertEqual(result.remaining_rounds, 0)

    def test_required_points_top(self):
        """トップ目は必要打点なし"""
        hand = tiles_from_str("123m456p789s11z")
        gs = _make_gs(hand, turn=10, scores=[35000, 25000, 20000, 20000])
        gs.round_wind = Wind.SOUTH
        gs.dealer = 3
        result = self.analyzer.analyze(gs, 0)
        self.assertTrue(result.is_endgame)
        self.assertEqual(result.required_points.current_rank, 1)
        self.assertEqual(result.required_points.required_points, 0)

    def test_required_points_last(self):
        """ラス目は逆転必要打点を計算"""
        hand = tiles_from_str("123m456p789s11z")
        gs = _make_gs(hand, turn=10, scores=[15000, 30000, 25000, 30000])
        gs.round_wind = Wind.SOUTH
        gs.dealer = 3
        result = self.analyzer.analyze(gs, 0)
        self.assertGreater(result.required_points.required_points, 0)
        self.assertGreaterEqual(result.required_points.required_han, 1)

    def test_endgame_result_structure(self):
        """EndgameResultの出力構造チェック"""
        hand = tiles_from_str("123m456p789s11z")
        gs = _make_gs(hand, turn=10)
        gs.round_wind = Wind.SOUTH
        gs.dealer = 3
        result = self.analyzer.analyze(gs, 0)
        d = result.to_dict()
        self.assertIn("is_endgame", d)
        self.assertIn("remaining_rounds", d)


# ============================================================
# テスト13: 受入精密化
# ============================================================

class TestUkeirePrecise(unittest.TestCase):
    def test_nominal_matches_basic(self):
        """精密版の名目値が基本版と一致"""
        from server.utils.mahjong_logic import estimate_ukeire_precise
        hand = tiles_from_str("2345m678p11s77z")
        discard = tile_from_str("7z")
        basic = estimate_ukeire(hand, discard)
        precise = estimate_ukeire_precise(hand, discard)
        self.assertEqual(precise["nominal"], basic)

    def test_turn_adjusted_decreases(self):
        """巡目が進むと受入が減少"""
        from server.utils.mahjong_logic import estimate_ukeire_precise
        hand = tiles_from_str("2345m678p11s77z")
        discard = tile_from_str("7z")
        early = estimate_ukeire_precise(hand, discard, turn=3)
        late = estimate_ukeire_precise(hand, discard, turn=16)
        self.assertGreater(early["turn_adjusted"], late["turn_adjusted"])

    def test_quality_score_range(self):
        """質スコアが0-1の範囲"""
        from server.utils.mahjong_logic import estimate_ukeire_precise
        hand = tiles_from_str("2345m678p11s77z")
        discard = tile_from_str("7z")
        result = estimate_ukeire_precise(hand, discard)
        self.assertGreaterEqual(result["quality"], 0.0)
        self.assertLessEqual(result["quality"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
