"""
麻雀ゲームの型定義・データモデル
Implements: F-001 | 基本型定義

リーチ麻雀（四人打ち）の全データ構造を定義。
mjai プロトコルとの互換性を考慮した設計。
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 牌の定義
# ============================================================

class TileSuit(enum.Enum):
    """牌の種類"""
    MAN = "m"    # 萬子
    PIN = "p"    # 筒子
    SOU = "s"    # 索子
    WIND = "z"   # 字牌（風牌・三元牌）


class Wind(enum.Enum):
    """風（自風/場風）"""
    EAST = 0   # 東
    SOUTH = 1  # 南
    WEST = 2   # 西
    NORTH = 3  # 北


WIND_NAMES_JA = {
    Wind.EAST: "東",
    Wind.SOUTH: "南",
    Wind.WEST: "西",
    Wind.NORTH: "北",
}


@dataclass(frozen=True, order=True)
class Tile:
    """
    牌を表す。
    suit: 種類 (m/p/s/z)
    number: 数字 (1-9, 字牌は1-7: 東南西北白發中)
    is_red: 赤ドラか (赤五萬/赤五筒/赤五索)
    """
    suit: TileSuit
    number: int
    is_red: bool = False

    def __post_init__(self):
        if self.suit == TileSuit.WIND:
            if not (1 <= self.number <= 7):
                raise ValueError(f"字牌の番号は1-7: {self.number}")
        else:
            if not (1 <= self.number <= 9):
                raise ValueError(f"数牌の番号は1-9: {self.number}")
        if self.is_red and not (self.suit != TileSuit.WIND and self.number == 5):
            raise ValueError("赤ドラは数牌の5のみ")

    @property
    def id(self) -> str:
        """mjai互換の牌ID (例: '1m', '5pr', '7z')"""
        red = "r" if self.is_red else ""
        return f"{self.number}{self.suit.value}{red}"

    @property
    def sort_key(self) -> int:
        """ソート用キー"""
        suit_order = {"m": 0, "p": 100, "s": 200, "z": 300}
        base = suit_order[self.suit.value] + self.number * 10
        return base + (1 if self.is_red else 0)

    @property
    def name_ja(self) -> str:
        """日本語名"""
        suit_names = {
            TileSuit.MAN: "萬",
            TileSuit.PIN: "筒",
            TileSuit.SOU: "索",
        }
        if self.suit == TileSuit.WIND:
            wind_names = {1: "東", 2: "南", 3: "西", 4: "北",
                          5: "白", 6: "發", 7: "中"}
            return wind_names[self.number]
        red = "赤" if self.is_red else ""
        return f"{red}{self.number}{suit_names[self.suit]}"

    @property
    def is_terminal(self) -> bool:
        """老頭牌（1,9）か"""
        return self.suit != TileSuit.WIND and self.number in (1, 9)

    @property
    def is_honor(self) -> bool:
        """字牌か"""
        return self.suit == TileSuit.WIND

    @property
    def is_terminal_or_honor(self) -> bool:
        """么九牌（老頭牌 or 字牌）か"""
        return self.is_terminal or self.is_honor

    @property
    def is_dragon(self) -> bool:
        """三元牌か"""
        return self.suit == TileSuit.WIND and self.number >= 5

    @property
    def is_wind_tile(self) -> bool:
        """風牌か"""
        return self.suit == TileSuit.WIND and self.number <= 4

    def __repr__(self) -> str:
        return self.id


def tile_from_str(s: str) -> Tile:
    """文字列から牌を生成 (例: '1m', '5pr', '7z')"""
    is_red = s.endswith("r")
    if is_red:
        s = s[:-1]
    number = int(s[0])
    suit_map = {"m": TileSuit.MAN, "p": TileSuit.PIN,
                "s": TileSuit.SOU, "z": TileSuit.WIND}
    suit = suit_map[s[1]]
    return Tile(suit=suit, number=number, is_red=is_red)


def tiles_from_str(s: str) -> list[Tile]:
    """短縮形式から牌リストを生成 (例: '123m456p789s1z')"""
    tiles: list[Tile] = []
    numbers: list[str] = []
    for ch in s:
        if ch.isdigit():
            numbers.append(ch)
        elif ch in "mpsz":
            suit_map = {"m": TileSuit.MAN, "p": TileSuit.PIN,
                        "s": TileSuit.SOU, "z": TileSuit.WIND}
            suit = suit_map[ch]
            for n in numbers:
                tiles.append(Tile(suit=suit, number=int(n)))
            numbers = []
    return tiles


# ============================================================
# 全136枚の牌セット生成
# ============================================================

def create_full_tileset(use_red_dora: bool = True) -> list[Tile]:
    """136枚の牌セットを生成（赤ドラ含む）"""
    tiles: list[Tile] = []
    for suit in [TileSuit.MAN, TileSuit.PIN, TileSuit.SOU]:
        for num in range(1, 10):
            for i in range(4):
                if use_red_dora and num == 5 and i == 0:
                    tiles.append(Tile(suit=suit, number=5, is_red=True))
                else:
                    tiles.append(Tile(suit=suit, number=num))
    for num in range(1, 8):  # 東南西北白發中
        for _ in range(4):
            tiles.append(Tile(suit=TileSuit.WIND, number=num))
    return tiles


# ============================================================
# 鳴きの定義
# ============================================================

class MeldType(enum.Enum):
    """鳴きの種類"""
    CHI = "chi"        # チー（順子）
    PON = "pon"        # ポン（刻子）
    DAIMINKAN = "daiminkan"  # 大明槓
    KAKAN = "kakan"    # 加槓
    ANKAN = "ankan"    # 暗槓


@dataclass
class Meld:
    """鳴き（副露）"""
    meld_type: MeldType
    tiles: list[Tile]
    called_tile: Optional[Tile] = None   # 鳴いた牌
    from_player: Optional[int] = None     # 誰から鳴いたか (seat index)


# ============================================================
# プレイヤー状態
# ============================================================

@dataclass
class PlayerState:
    """各プレイヤーの状態"""
    seat: int                          # 席番号 (0=東, 1=南, 2=西, 3=北)
    hand: list[Tile] = field(default_factory=list)        # 手牌
    discards: list[Tile] = field(default_factory=list)    # 捨て牌
    melds: list[Meld] = field(default_factory=list)       # 副露
    score: int = 25000                 # 持ち点
    is_riichi: bool = False            # リーチ中か
    is_ippatsu: bool = False           # 一発の権利があるか
    is_double_riichi: bool = False     # ダブルリーチか
    riichi_turn: int = -1              # リーチした巡目
    is_menzen: bool = True             # 門前か

    def sort_hand(self):
        """手牌をソート"""
        self.hand.sort(key=lambda t: t.sort_key)

    @property
    def closed_tile_count(self) -> int:
        """門前の牌数"""
        return len(self.hand)

    def add_tile(self, tile: Tile):
        """手牌に牌を加える"""
        self.hand.append(tile)

    def remove_tile(self, tile: Tile) -> Tile:
        """手牌から牌を除く"""
        # 赤ドラの同一性を考慮
        for i, t in enumerate(self.hand):
            if t.suit == tile.suit and t.number == tile.number and t.is_red == tile.is_red:
                return self.hand.pop(i)
        # 赤ドラ区別なしで探す
        for i, t in enumerate(self.hand):
            if t.suit == tile.suit and t.number == tile.number:
                return self.hand.pop(i)
        raise ValueError(f"手牌に {tile} が見つかりません: {self.hand}")


# ============================================================
# ゲーム状態
# ============================================================

class GamePhase(enum.Enum):
    """ゲームの進行フェーズ"""
    WAITING = "waiting"
    DEALING = "dealing"          # 配牌中
    PLAYER_TURN = "player_turn"  # プレイヤーのツモ→打牌待ち
    CALLING = "calling"          # 鳴き判定待ち
    ROUND_END = "round_end"     # 局終了
    GAME_END = "game_end"       # 対局終了


@dataclass
class GameState:
    """ゲーム全体の状態"""
    # 局情報
    round_wind: Wind = Wind.EAST         # 場風
    round_number: int = 0                # 局数 (0=東1局, 1=東2局, ...)
    honba: int = 0                       # 本場（積み棒）
    riichi_sticks: int = 0               # リーチ棒の供託
    dealer: int = 0                      # 親の席番号

    # 山
    wall: list[Tile] = field(default_factory=list)
    wall_pointer: int = 0                # 次のツモ牌の位置
    dead_wall: list[Tile] = field(default_factory=list)  # 王牌
    dora_indicators: list[Tile] = field(default_factory=list)  # ドラ表示牌
    kan_count: int = 0                   # カンの回数

    # プレイヤー
    players: list[PlayerState] = field(default_factory=list)
    current_player: int = 0              # 現在のターンのプレイヤー

    # フェーズ
    phase: GamePhase = GamePhase.WAITING

    # ターン情報
    turn_count: int = 0                  # 全体の巡目
    last_discard: Optional[Tile] = None  # 最後に捨てられた牌
    last_discard_player: int = -1        # 最後に捨てたプレイヤー
    last_drawn_tile: Optional[Tile] = None # 最後にツモられた牌

    @property
    def tiles_remaining(self) -> int:
        """山の残り枚数"""
        return len(self.wall) - self.wall_pointer

    @property
    def round_name_ja(self) -> str:
        """局名（日本語）"""
        wind = WIND_NAMES_JA[self.round_wind]
        return f"{wind}{self.round_number + 1}局"

    @property
    def dora_tiles(self) -> list[Tile]:
        """ドラ牌リスト（表示牌からドラを算出）"""
        doras: list[Tile] = []
        for indicator in self.dora_indicators:
            doras.append(_next_tile(indicator))
        return doras

    def to_mjai_events(self) -> list[dict]:
        """ダミーイベント出力（特徴量抽出用途互換用）"""
        return [{"type": "start_game"}]

    def get_player_shanten(self, seat: int) -> int:
        """プレイヤーの手牌向聴数を計算"""
        if seat < 0 or seat >= len(self.players):
            return 6
        from mahjong.shanten import Shanten
        try:
            shanten_calc = Shanten()
            hand = self.players[seat].hand
            
            result = [0] * 34
            for t in hand:
                suit_to_idx = {"m": 0, "p": 1, "s": 2, "z": 3}
                suit_idx = suit_to_idx.get(t.suit.value, 3)
                if suit_idx < 3:
                    idx = suit_idx * 9 + t.number - 1
                else:
                    idx = 27 + t.number - 1
                if 0 <= idx < 34:
                    result[idx] += 1
                    
            return shanten_calc.calculate_shanten(result)
        except Exception:
            return 6
def _next_tile(tile: Tile) -> Tile:
    """ドラ表示牌の次の牌を返す"""
    if tile.suit == TileSuit.WIND:
        if tile.number <= 4:
            # 東→南→西→北→東
            next_num = (tile.number % 4) + 1
        else:
            # 白→發→中→白
            next_num = ((tile.number - 5) % 3) + 5
        return Tile(suit=TileSuit.WIND, number=next_num)
    else:
        next_num = (tile.number % 9) + 1
        return Tile(suit=tile.suit, number=next_num)


# ============================================================
# mjai連携用のアクション型
# ============================================================

class ActionType(enum.Enum):
    """アクション種別（mjai互換）"""
    NONE = "none"
    TSUMO = "tsumo"          # ツモ
    DAHAI = "dahai"          # 打牌
    CHI = "chi"              # チー
    PON = "pon"              # ポン
    DAIMINKAN = "daiminkan"  # 大明槓
    KAKAN = "kakan"          # 加槓
    ANKAN = "ankan"          # 暗槓
    RIICHI = "riichi"        # リーチ宣言
    HORA = "hora"            # 和了（ツモ/ロン）
    RYUKYOKU = "ryukyoku"    # 流局
    SKIP = "skip"            # スキップ（鳴きしない）


@dataclass
class GameAction:
    """ゲームアクション"""
    action_type: ActionType
    player: int                          # プレイヤー席番号
    tile: Optional[Tile] = None          # 対象牌
    consumed: Optional[list[Tile]] = None  # 鳴きで使った手牌
    is_tsumogiri: bool = False           # ツモ切りか
