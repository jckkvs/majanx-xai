"""
麻雀ゲームのルールエンジン
基本的な役判定、点数計算、状態管理を行う
"""
import random
from typing import List, Dict, Optional, Tuple, Set
from collections import Counter

from shared.models import (
    Tile, TileSuit, Wind, GamePhase, PlayerSeat,
    GameState, DoraIndicator, CallType
)


class TileManager:
    """牌の管理"""

    ALL_TILES = {
        # 萬子 (1-9) x 4枚
        (TileSuit.MANZU, 1): 4, (TileSuit.MANZU, 2): 4, (TileSuit.MANZU, 3): 4,
        (TileSuit.MANZU, 4): 4, (TileSuit.MANZU, 5): 4, (TileSuit.MANZU, 6): 4,
        (TileSuit.MANZU, 7): 4, (TileSuit.MANZU, 8): 4, (TileSuit.MANZU, 9): 4,
        # 筒子 (1-9) x 4枚
        (TileSuit.PINZU, 1): 4, (TileSuit.PINZU, 2): 4, (TileSuit.PINZU, 3): 4,
        (TileSuit.PINZU, 4): 4, (TileSuit.PINZU, 5): 4, (TileSuit.PINZU, 6): 4,
        (TileSuit.PINZU, 7): 4, (TileSuit.PINZU, 8): 4, (TileSuit.PINZU, 9): 4,
        # 索子 (1-9) x 4枚
        (TileSuit.SOUZU, 1): 4, (TileSuit.SOUZU, 2): 4, (TileSuit.SOUZU, 3): 4,
        (TileSuit.SOUZU, 4): 4, (TileSuit.SOUZU, 5): 4, (TileSuit.SOUZU, 6): 4,
        (TileSuit.SOUZU, 7): 4, (TileSuit.SOUZU, 8): 4, (TileSuit.SOUZU, 9): 4,
        # 字牌 (東西南北白發中) x 4枚
        (TileSuit.JIHAI, 1): 4, (TileSuit.JIHAI, 2): 4, (TileSuit.JIHAI, 3): 4,
        (TileSuit.JIHAI, 4): 4, (TileSuit.JIHAI, 5): 4, (TileSuit.JIHAI, 6): 4,
        (TileSuit.JIHAI, 7): 4,
    }

    JIHAI_NAMES = {
        1: "E", 2: "S", 3: "W", 4: "N", 5: "P", 6: "F", 7: "C"
    }

    def __init__(self):
        self.tiles: List[Tile] = []
        self.remaining: Dict[Tuple[TileSuit, int], int] = {}
        self._initialize()

    def _initialize(self):
        """牌山の初期化"""
        self.tiles = []
        self.remaining = dict(self.ALL_TILES)

        for (suit, number), count in self.ALL_TILES.items():
            name = self._get_tile_name(suit, number)
            for _ in range(count):
                tile = Tile(suit=suit, number=number, name=name)
                self.tiles.append(tile)

        self.shuffle()

    def _get_tile_name(self, suit: TileSuit, number: Optional[int]) -> str:
        """牌の名前を取得"""
        if suit == TileSuit.MANZU:
            return f"{number}m"
        elif suit == TileSuit.PINZU:
            return f"{number}p"
        elif suit == TileSuit.SOUZU:
            return f"{number}s"
        elif suit == TileSuit.JIHAI:
            return self.JIHAI_NAMES.get(number, "?")
        return "?"

    def shuffle(self):
        """牌山をシャッフル"""
        random.shuffle(self.tiles)

    def draw(self) -> Optional[Tile]:
        """牌を引く"""
        if self.tiles:
            tile = self.tiles.pop()
            key = (tile.suit, tile.number)
            if key in self.remaining:
                self.remaining[key] -= 1
            return tile
        return None

    def get_remaining_count(self, suit: TileSuit, number: Optional[int]) -> int:
        """特定の牌の残り枚数を取得"""
        return self.remaining.get((suit, number), 0)


class YakuChecker:
    """役判定"""

    @staticmethod
    def check_yaku(hand: List[Tile], is_menzen: bool, dora_count: int = 0,
                   bakaze: Wind = Wind.EAST, jikaze: Wind = Wind.EAST,
                   is_riichi: bool = False, is_ippatsu: bool = False,
                   is_tsumo: bool = False, is_haitei: bool = False,
                   is_houtei: bool = False, is_rinshan: bool = False,
                   is_chankan: bool = False) -> List[Tuple[str, int]]:
        """
        役を判定
        戻り値：[(役名，翻数), ...]
        """
        yaku_list = []

        # 手牌のカウント
        tile_counts = Counter(tile.name for tile in hand)

        # 面子と対子のチェック
        sets, pairs = YakuChecker._analyze_hand_structure(hand)

        if not sets and not pairs:
            return []

        # タンヤオ
        if YakuChecker._is_tanyao(hand):
            yaku_list.append(("タンヤオ", 1))

        # 役牌
        yakuhai_yaku = YakuChecker._check_yakuhai(hand, bakaze, jikaze)
        yaku_list.extend(yakuhai_yaku)

        # リーチ
        if is_riichi and is_menzen:
            yaku_list.append(("立直", 1))

        # 一発
        if is_ippatsu and is_riichi:
            yaku_list.append(("一発", 1))

        # 門前清自摸和
        if is_tsumo and is_menzen:
            yaku_list.append(("門前清自摸和", 1))

        # 海底撈月
        if is_haitei:
            yaku_list.append(("海底撈月", 1))

        # 河底撈魚
        if is_houtei:
            yaku_list.append(("河底撈魚", 1))

        # 嶺上開花
        if is_rinshan:
            yaku_list.append(("嶺上開花", 1))

        # 槍槓
        if is_chankan:
            yaku_list.append(("槍槓", 1))

        # ドラ
        if dora_count > 0:
            yaku_list.append((f"ドラ×{dora_count}", dora_count))

        return yaku_list

    @staticmethod
    def _analyze_hand_structure(hand: List[Tile]) -> Tuple[List, List]:
        """手牌を分析して面子と対子を抽出"""
        # 簡易実装：完全なアルゴリズムは複雑なため省略
        # 実際には递归的に面子を抽出する必要がある
        tile_counts = Counter(tile.name for tile in hand)

        sets = []
        pairs = []

        # 対子の抽出
        for name, count in tile_counts.items():
            if count >= 2:
                pairs.append(name)

        # 面子の簡易チェック
        # TODO: 完全な実装

        return sets, pairs

    @staticmethod
    def _is_tanyao(hand: List[Tile]) -> bool:
        """タンヤオの判定"""
        for tile in hand:
            if tile.suit == TileSuit.JIHAI:
                return False
            if tile.number == 1 or tile.number == 9:
                return False
        return True

    @staticmethod
    def _check_yakuhai(hand: List[Tile], bakaze: Wind, jikaze: Wind) -> List[Tuple[str, int]]:
        """役牌の判定"""
        yaku_list = []

        jikaze_map = {Wind.EAST: 1, Wind.SOUTH: 2, Wind.WEST: 3, Wind.NORTH: 4}
        bakaze_map = {Wind.EAST: 1, Wind.SOUTH: 2, Wind.WEST: 3, Wind.NORTH: 4}

        jikaze_tile = jikaze_map.get(jikaze)
        bakaze_tile = bakaze_map.get(bakaze)

        tile_counts = Counter(tile.name for tile in hand)

        # 自風
        if jikaze_tile:
            jikaze_name = TileManager.JIHAI_NAMES.get(jikaze_tile)
            if tile_counts.get(jikaze_name, 0) >= 3:
                yaku_list.append((f"役牌：{jikaze}", 1))

        # 場風
        if bakaze_tile and bakaze_tile != jikaze_tile:
            bakaze_name = TileManager.JIHAI_NAMES.get(bakaze_tile)
            if tile_counts.get(bakaze_name, 0) >= 3:
                yaku_list.append((f"役牌：場風", 1))

        # 白發中
        for ji_name, ji_num in [("P", 5), ("F", 6), ("C", 7)]:
            if tile_counts.get(ji_name, 0) >= 3:
                yaku_list.append((f"役牌：{ji_name}", 1))

        return yaku_list


class ScoreCalculator:
    """点数計算"""

    @staticmethod
    def calculate_fu(hand: List[Tile], is_menzen: bool, is_tsumo: bool,
                     has_yakuhai: bool = False, has_ryanmen: bool = False,
                     has_kanchan: bool = False, has_penchan: bool = False,
                     has_toitoi: bool = False) -> int:
        """符計算"""
        fu = 20  # 副底

        # 門前加符
        if is_menzen and not is_tsumo:
            fu += 10

        # 自摸加符
        if is_tsumo:
            fu += 2

        # 簡易実装：実際の符計算はより複雑

        # 切り上げ
        if fu % 10 != 0:
            fu = ((fu // 10) + 1) * 10

        return min(fu, 110)

    @staticmethod
    def calculate_score(fu: int, han: int, is_dealer: bool = False) -> Dict[str, int]:
        """得点計算"""
        if han >= 13:
            # 役満
            return {"ron": 48000 if is_dealer else 32000, "tsumo": "yakuman"}
        elif han >= 11:
            base = 6000
        elif han >= 8:
            base = 4000
        elif han >= 6:
            base = 3000
        elif han >= 5:
            base = 2000
        else:
            base = fu * (2 ** (2 + han))

        base = min(base, 2000)

        if is_dealer:
            ron = base * 6
            tsumo_per_player = base * 2
        else:
            ron = base * 4
            tsumo_dealer = base * 2
            tsumo_non_dealer = base * 1

        return {
            "ron": ron,
            "tsumo_dealer": tsumo_per_player if is_dealer else tsumo_dealer,
            "tsumo_non_dealer": tsumo_per_player if is_dealer else tsumo_non_dealer
        }


class MahjongEngine:
    """麻雀ゲームエンジン"""

    def __init__(self):
        self.tile_manager = TileManager()
        self.state: Optional[GameState] = None
        self.players = ["jikaze", "kamicha", "shimocha", "toimen"]

    def init_game(self, round_name: str = "E1", bakaze: Wind = Wind.EAST,
                  jikaze: Wind = Wind.EAST):
        """ゲーム初期化"""
        self.tile_manager = TileManager()

        self.state = GameState(
            round_name=round_name,
            bakaze=bakaze,
            jikaze=jikaze,
            phase=GamePhase.DEALING
        )

        self._deal_tiles()
        self._init_dora()

        self.state.phase = GamePhase.DRAWING

    def _deal_tiles(self):
        """配牌"""
        if not self.state:
            return

        # 各プレイヤーに 13 枚配牌
        for player in self.players:
            tiles = []
            for _ in range(13):
                tile = self.tile_manager.draw()
                if tile:
                    tiles.append(tile)

            if player == "jikaze":
                self.state.jikaze_tiles = tiles

        # 親に 14 枚目
        if self.state.jikaze == Wind.EAST:
            tile = self.tile_manager.draw()
            if tile:
                self.state.tsumo_tile = tile
                self.state.jikaze_tiles.append(tile)

        self.state.wall_remaining = len(self.tile_manager.tiles)

    def _init_dora(self):
        """ドラ表示牌を初期化"""
        if not self.state:
            return

        # 最初のドラ表示牌
        tile = self.tile_manager.draw()
        if tile:
            self.state.dora_indicators.append(DoraIndicator(tile=tile))

    def draw_tile(self) -> Optional[Tile]:
        """ツモ"""
        if not self.state:
            return None

        tile = self.tile_manager.draw()
        if tile:
            self.state.tsumo_tile = tile
            self.state.wall_remaining = len(self.tile_manager.tiles)
            self.state.phase = GamePhase.DISCARDING

            # ハテハイチェック
            if self.state.wall_remaining <= 0:
                self.state.phase = GamePhase.GAME_END

        return tile

    def discard_tile(self, tile_index: int) -> bool:
        """打牌"""
        if not self.state or not self.state.tsumo_tile:
            return False

        # 手牌から除外
        if 0 <= tile_index < len(self.state.jikaze_tiles):
            discarded = self.state.jikaze_tiles.pop(tile_index)
            self.state.jikaze_discards.append(discarded)
            self.state.last_discard = discarded
            self.state.tsumo_tile = None

            # 次のプレイヤーへ
            self._next_player()
            return True

        return False

    def _next_player(self):
        """次のプレイヤーへ"""
        if not self.state:
            return

        # シンプルに自家のみ実装
        self.state.phase = GamePhase.DRAWING

    def get_state(self) -> Optional[GameState]:
        """現在のゲーム状態を取得"""
        return self.state

    def check_agari(self, hand: List[Tile]) -> bool:
        """和了判定"""
        # TODO: 完全な実装
        return False

    def check_ryukyoku(self) -> bool:
        """流局判定"""
        if not self.state:
            return False

        return self.state.wall_remaining <= 0

    def declare_riichi(self) -> bool:
        """リーチ宣言"""
        if not self.state or not self.state.tsumo_tile:
            return False

        # リーチの条件チェック
        # 1. 門前であること
        if not self._is_menzen():
            return False

        # 2. 残り 4000 点以上あること
        if self.state.scores.get("jikaze", 0) < 4000:
            return False

        # 3. まだリーチしていないこと
        if self.state.riichi_declarations.get("jikaze", False):
            return False

        # 4. 聴牌していること（簡易チェック：あと 1 枚で和了る状態）
        # TODO: 完全な聴牌判定実装

        # リーチ宣言
        self.state.riichi_declarations["jikaze"] = True
        self.state.kyoutaku += 1  # 供託
        self.state.scores["jikaze"] -= 1000  # リーチ棒

        # フェーズ更新
        self.state.phase = GamePhase.DISCARDING

        return True

    def _is_menzen(self) -> bool:
        """門前かどうかを判定"""
        # シンプル実装：鳴きがなければ門前
        calls = self.state.calls.get("jikaze", [])
        return len(calls) == 0
