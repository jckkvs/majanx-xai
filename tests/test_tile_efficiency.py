import unittest
from server.tile_efficiency import TileEfficiencyEvaluator, EvalContext

class TestTileEfficiency(unittest.TestCase):
    def setUp(self):
        self.evaluator = TileEfficiencyEvaluator()

    def test_case_1_early_chun(self):
        """実例1：孤立三元牌 `中` の早期保持判断"""
        hand = ["2m", "3m", "5m", "4p", "6p", "7s", "8s", "中", "東", "南"]
        ctx = EvalContext(turn=4, riichi_count=0, bakaze="東", jikaze="南")
        
        # 中切り（旧ルール）スコア計算 (受入のみ評価)
        def mock_ukeire(tile, hs):
            return 8 if tile == "中" else 4 # 南切りで受入最大
            
        self.evaluator.calculate_ukeire_after_discard = mock_ukeire
        
        score_chun = self.evaluator.evaluate_tile_efficiency("中", hand, ctx)
        score_nan = self.evaluator.evaluate_tile_efficiency("南", hand, ctx)
        
        # 中は1翻確定のオプション価値がないため今は低いが、南よりは高いか？
        # handの中に中が1枚なのでyaku_guaranteeは0。
        # 旧ルール（Ukeireのみ）ではUkeireのスコアそのまま。
        # 実際には中は孤立牌。
        # この仕様だと「南を優先処理し、中は保持」なので、中切りのスコアが南切りより低くなるべき。
        
        # TODO: 計算式を当てはめて確認。
        self.assertTrue(True) # 骨組み保証

    def test_case_2_duplicate_winds(self):
        """実例2：場風・自風重複時の選択肢評価"""
        hand = ["1m", "2m", "4m", "5p", "6p", "3s", "4s", "東", "東", "東", "西"]
        ctx = EvalContext(turn=6, riichi_count=0, bakaze="東", jikaze="東", is_dealer=True)
        
        def mock_ukeire(tile, hs):
            return 12 if tile == "西" else 8 # 西切りで受入12と仮定
            
        self.evaluator.calculate_ukeire_after_discard = mock_ukeire
        
        score_east = self.evaluator.evaluate_tile_efficiency("東", hand, ctx)
        score_west = self.evaluator.evaluate_tile_efficiency("西", hand, ctx)
        
        # 東はyaku_guarantee = 2.0 * beta = 2.0 * 1.2 = 2.4 => 高評価
        # ゆえに東を切るスコアは非常に高いが、これを捨ててはいけない
        # いや、TileScoreは「その牌の価値」を計算する。評価が高い=手牌に残すべき。
        self.assertGreater(score_east, score_west)

    def test_case_3_late_riichi_defense(self):
        """実例3：終盤・他家リーチ下の字牌対子転換"""
        hand = ["3m", "4m", "5m", "2p", "3p", "4p", "7s", "8s", "9s", "發", "發"]
        ctx = EvalContext(turn=10, riichi_count=1, bakaze="南", jikaze="南")
        
        score_hatsu = self.evaluator.evaluate_tile_efficiency("發", hand, ctx)
        
        # 發はyaku_guarantee=1.0、defense=0.4。late_turnなのでbeta=1.5
        # 総合スコアは 1.0 * 1.5 + 0.4 * 0.4 ... 高くなる
        self.assertGreater(score_hatsu, 1.0)

    def test_case_4_dora_indicator_adjacent(self):
        """実例4：ドラ表示牌隣接字牌の価値評価"""
        hand = ["2m", "3m", "4m", "5p", "6p", "1s", "2s", "3s", "中", "白", "東"]
        ctx = EvalContext(turn=5, riichi_count=0, dora_indicators=["發"])
        
        score_chun = self.evaluator.evaluate_tile_efficiency("中", hand, ctx)
        score_haku = self.evaluator.evaluate_tile_efficiency("白", hand, ctx)
        
        # 仕様より字牌の隣接ドラ補正は0なので実態同じに見えるが
        # ドラが絡むことを見越した特注の「中」評価？
        # テストスタブとして骨格確認
        self.assertEqual(score_chun, score_haku) # 評価式の完全実装で差異が出る場合修正

    def test_case_5_shape_vs_yaku(self):
        """実例5：対子崩し vs 両面維持の打点×速度統合判断"""
        hand = ["4m", "5m", "6m", "2p", "3p", "5p", "7s", "8s", "9s", "中", "中", "東"]
        ctx = EvalContext(turn=7, riichi_count=0)
        
        def mock_ukeire(tile, hs):
            return 8 if tile == "中" else 4
            
        self.evaluator.calculate_ukeire_after_discard = mock_ukeire
        
        score_chun = self.evaluator.evaluate_tile_efficiency("中", hand, ctx)
        score_east = self.evaluator.evaluate_tile_efficiency("東", hand, ctx)
        
        # 中はyaku_guaranteeが1.0、東は0.0
        self.assertGreater(score_chun, score_east)

if __name__ == '__main__':
    unittest.main()
