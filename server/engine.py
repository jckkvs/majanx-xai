"""
ゲームエンジン: 麻雀の対局進行を管理する
Implements: F-002 | ゲーム状態管理・進行ロジック

mjai プロトコルに準拠したイベント駆動型設計。
役判定・点数計算は Python mahjong ライブラリに委譲。
"""
from __future__ import annotations

import random
from typing import Optional, Callable

from .models import (
    Tile, TileSuit, Wind, GameState, GamePhase, PlayerState,
    Meld, MeldType, ActionType, GameAction,
    create_full_tileset, tile_from_str, _next_tile,
)


class GameEngine:
    """
    四人打ちリーチ麻雀ゲームエンジン。
    - 山の生成・配牌・ツモ・打牌・鳴き・リーチ・和了・流局を管理
    - mjai互換イベントを発行
    """

    def __init__(self, use_red_dora: bool = True, seed: Optional[int] = None):
        self.use_red_dora = use_red_dora
        self.seed = seed
        self.rng = random.Random(seed)
        self.state = GameState()
        self.event_log: list[dict] = []
        self._on_event: Optional[Callable[[dict], None]] = None

    def set_event_handler(self, handler: Callable[[dict], None]):
        """イベントハンドラを設定"""
        self._on_event = handler

    def _emit(self, event: dict):
        """イベントを発行"""
        self.event_log.append(event)
        if self._on_event:
            self._on_event(event)

    # ============================================================
    # ゲーム開始
    # ============================================================

    def start_game(self):
        """対局を開始"""
        self.state = GameState()
        self.state.players = [
            PlayerState(seat=i, score=25000) for i in range(4)
        ]
        self.state.round_wind = Wind.EAST
        self.state.round_number = 0
        self.state.dealer = 0
        self.state.honba = 0
        self.state.riichi_sticks = 0
        self._emit({
            "type": "start_game",
            "players": [{"seat": i, "score": 25000} for i in range(4)]
        })
        self.start_round()

    # ============================================================
    # 局開始
    # ============================================================

    def start_round(self):
        """局を開始（配牌）"""
        st = self.state

        # プレイヤー手牌・捨て牌リセット
        for p in st.players:
            p.hand = []
            p.discards = []
            p.melds = []
            p.is_riichi = False
            p.is_ippatsu = False
            p.is_double_riichi = False
            p.riichi_turn = -1
            p.is_menzen = True

        # 山を生成・シャッフル
        all_tiles = create_full_tileset(self.use_red_dora)
        self.rng.shuffle(all_tiles)

        # 王牌 (14枚: 末尾から)
        st.dead_wall = all_tiles[-14:]
        st.wall = all_tiles[:-14]
        st.wall_pointer = 0
        st.kan_count = 0

        # ドラ表示牌 (王牌の3番目)
        st.dora_indicators = [st.dead_wall[4]]

        # 配牌 (親から4枚×3回 + 1枚)
        for _ in range(3):
            for seat in range(4):
                idx = (st.dealer + seat) % 4
                for __ in range(4):
                    st.players[idx].add_tile(self._draw_tile())
        # 最後の1枚ずつ
        for seat in range(4):
            idx = (st.dealer + seat) % 4
            st.players[idx].add_tile(self._draw_tile())

        # 手牌ソート
        for p in st.players:
            p.sort_hand()

        st.current_player = st.dealer
        st.phase = GamePhase.PLAYER_TURN
        st.turn_count = 0
        st.last_discard = None
        st.last_discard_player = -1

        self._emit({
            "type": "start_kyoku",
            "bakaze": st.round_wind.name.lower(),
            "kyoku": st.round_number + 1,
            "honba": st.honba,
            "kyotaku": st.riichi_sticks,
            "oya": st.dealer,
            "dora_marker": st.dora_indicators[0].id,
            "tehais": [[t.id for t in p.hand] for p in st.players],
            "scores": [p.score for p in st.players],
        })

    def _draw_tile(self) -> Tile:
        """山から1枚引く"""
        tile = self.state.wall[self.state.wall_pointer]
        self.state.wall_pointer += 1
        return tile

    def _draw_from_dead_wall(self) -> Tile:
        """王牌からツモ（カン後）"""
        # 嶺上牌は王牌の先頭から
        idx = self.state.kan_count
        return self.state.dead_wall[idx]

    # ============================================================
    # ツモフェーズ
    # ============================================================

    def do_tsumo(self) -> Optional[Tile]:
        """現在のプレイヤーがツモる"""
        st = self.state
        if st.tiles_remaining <= 0:
            self._handle_ryukyoku()
            return None

        tile = self._draw_tile()
        player = st.players[st.current_player]
        player.add_tile(tile)
        st.turn_count += 1

        self._emit({
            "type": "tsumo",
            "actor": st.current_player,
            "pai": tile.id,
        })
        return tile

    # ============================================================
    # 打牌
    # ============================================================

    def do_dahai(self, player_seat: int, tile: Tile, is_tsumogiri: bool = False) -> bool:
        """打牌を実行"""
        st = self.state
        player = st.players[player_seat]

        # 手牌から除去
        discarded = player.remove_tile(tile)
        player.discards.append(discarded)
        player.sort_hand()

        # 一発の権利消失（他家の打牌時）
        for p in st.players:
            if p.seat != player_seat:
                p.is_ippatsu = False

        st.last_discard = discarded
        st.last_discard_player = player_seat
        st.phase = GamePhase.CALLING

        self._emit({
            "type": "dahai",
            "actor": player_seat,
            "pai": discarded.id,
            "tsumogiri": is_tsumogiri,
        })
        return True

    # ============================================================
    # リーチ宣言
    # ============================================================

    def do_riichi(self, player_seat: int, tile: Tile) -> bool:
        """リーチ宣言 + 打牌"""
        st = self.state
        player = st.players[player_seat]

        if not player.is_menzen:
            return False
        if player.score < 1000:
            return False

        player.is_riichi = True
        player.riichi_turn = st.turn_count
        player.is_ippatsu = True
        player.score -= 1000
        st.riichi_sticks += 1

        # ダブルリーチ判定（最初の巡目）
        if st.turn_count <= 4:
            player.is_double_riichi = True

        self._emit({
            "type": "reach",
            "actor": player_seat,
        })

        # 打牌
        self.do_dahai(player_seat, tile)
        return True

    # ============================================================
    # 鳴き（チー/ポン/カン）
    # ============================================================

    def do_chi(self, player_seat: int, consumed: list[Tile]) -> bool:
        """チーを実行"""
        st = self.state
        player = st.players[player_seat]
        called_tile = st.last_discard

        if called_tile is None:
            return False

        # 上家（左隣）からのみ
        if (st.last_discard_player + 1) % 4 != player_seat:
            return False

        meld = Meld(
            meld_type=MeldType.CHI,
            tiles=sorted(consumed + [called_tile], key=lambda t: t.sort_key),
            called_tile=called_tile,
            from_player=st.last_discard_player,
        )

        for t in consumed:
            player.remove_tile(t)
        player.melds.append(meld)
        player.is_menzen = False

        st.current_player = player_seat
        st.phase = GamePhase.PLAYER_TURN

        self._emit({
            "type": "chi",
            "actor": player_seat,
            "target": st.last_discard_player,
            "pai": called_tile.id,
            "consumed": [t.id for t in consumed],
        })
        return True

    def do_pon(self, player_seat: int, consumed: list[Tile]) -> bool:
        """ポンを実行"""
        st = self.state
        player = st.players[player_seat]
        called_tile = st.last_discard

        if called_tile is None:
            return False

        meld = Meld(
            meld_type=MeldType.PON,
            tiles=consumed + [called_tile],
            called_tile=called_tile,
            from_player=st.last_discard_player,
        )

        for t in consumed:
            player.remove_tile(t)
        player.melds.append(meld)
        player.is_menzen = False

        st.current_player = player_seat
        st.phase = GamePhase.PLAYER_TURN

        self._emit({
            "type": "pon",
            "actor": player_seat,
            "target": st.last_discard_player,
            "pai": called_tile.id,
            "consumed": [t.id for t in consumed],
        })
        return True

    def do_ankan(self, player_seat: int, tile: Tile) -> bool:
        """暗槓を実行"""
        st = self.state
        player = st.players[player_seat]

        # 手牌から同種4枚を探す
        same = [t for t in player.hand
                if t.suit == tile.suit and t.number == tile.number]
        if len(same) < 4:
            return False

        consumed = same[:4]
        for t in consumed:
            player.remove_tile(t)

        meld = Meld(
            meld_type=MeldType.ANKAN,
            tiles=consumed,
        )
        player.melds.append(meld)
        st.kan_count += 1

        # 新ドラ表示
        if st.kan_count <= 4:
            st.dora_indicators.append(st.dead_wall[4 + st.kan_count])

        # 嶺上ツモ
        rinshan = self._draw_from_dead_wall()
        player.add_tile(rinshan)

        self._emit({
            "type": "ankan",
            "actor": player_seat,
            "consumed": [t.id for t in consumed],
        })
        return True

    def do_daiminkan(self, player_seat: int, consumed: list[Tile]) -> bool:
        """大明槓を実行"""
        st = self.state
        player = st.players[player_seat]
        called_tile = st.last_discard

        if called_tile is None:
            return False

        for t in consumed:
            player.remove_tile(t)

        meld = Meld(
            meld_type=MeldType.DAIMINKAN,
            tiles=consumed + [called_tile],
            called_tile=called_tile,
            from_player=st.last_discard_player,
        )
        player.melds.append(meld)
        player.is_menzen = False
        st.kan_count += 1

        if st.kan_count <= 4:
            st.dora_indicators.append(st.dead_wall[4 + st.kan_count])

        rinshan = self._draw_from_dead_wall()
        player.add_tile(rinshan)

        st.current_player = player_seat
        st.phase = GamePhase.PLAYER_TURN

        self._emit({
            "type": "daiminkan",
            "actor": player_seat,
            "target": st.last_discard_player,
            "pai": called_tile.id,
            "consumed": [t.id for t in consumed],
        })
        return True

    # ============================================================
    # 鳴き判定
    # ============================================================

    def get_call_options(self, player_seat: int) -> list[GameAction]:
        """打牌に対する鳴きの選択肢を返す"""
        st = self.state
        options: list[GameAction] = []
        player = st.players[player_seat]
        tile = st.last_discard

        if tile is None or player.is_riichi:
            return options

        hand = player.hand
        discard_player = st.last_discard_player

        # ロン判定
        if self._can_ron(player_seat, tile):
            options.append(GameAction(
                action_type=ActionType.HORA,
                player=player_seat,
                tile=tile,
            ))

        # ポン判定
        same = [t for t in hand
                if t.suit == tile.suit and t.number == tile.number]
        if len(same) >= 2:
            options.append(GameAction(
                action_type=ActionType.PON,
                player=player_seat,
                tile=tile,
                consumed=same[:2],
            ))

        # 大明槓判定
        if len(same) >= 3:
            options.append(GameAction(
                action_type=ActionType.DAIMINKAN,
                player=player_seat,
                tile=tile,
                consumed=same[:3],
            ))

        # チー判定（上家からのみ）
        if (discard_player + 1) % 4 == player_seat and tile.suit != TileSuit.WIND:
            num = tile.number
            suit = tile.suit
            hand_nums = [t.number for t in hand if t.suit == suit]

            # tile=中 で左2枚 (num-2, num-1)
            if num >= 3 and (num - 2) in hand_nums and (num - 1) in hand_nums:
                c = [
                    next(t for t in hand if t.suit == suit and t.number == num - 2),
                    next(t for t in hand if t.suit == suit and t.number == num - 1),
                ]
                options.append(GameAction(
                    action_type=ActionType.CHI,
                    player=player_seat,
                    tile=tile,
                    consumed=c,
                ))
            # tile=中 で左右 (num-1, num+1)
            if 2 <= num <= 8 and (num - 1) in hand_nums and (num + 1) in hand_nums:
                c = [
                    next(t for t in hand if t.suit == suit and t.number == num - 1),
                    next(t for t in hand if t.suit == suit and t.number == num + 1),
                ]
                options.append(GameAction(
                    action_type=ActionType.CHI,
                    player=player_seat,
                    tile=tile,
                    consumed=c,
                ))
            # tile=中 で右2枚 (num+1, num+2)
            if num <= 7 and (num + 1) in hand_nums and (num + 2) in hand_nums:
                c = [
                    next(t for t in hand if t.suit == suit and t.number == num + 1),
                    next(t for t in hand if t.suit == suit and t.number == num + 2),
                ]
                options.append(GameAction(
                    action_type=ActionType.CHI,
                    player=player_seat,
                    tile=tile,
                    consumed=c,
                ))

        return options

    def get_tsumo_actions(self, player_seat: int) -> list[GameAction]:
        """ツモ後の選択肢（ツモ和了、暗槓、加槓、リーチ）"""
        st = self.state
        player = st.players[player_seat]
        options: list[GameAction] = []

        # ツモ和了判定
        if self._can_tsumo(player_seat):
            options.append(GameAction(
                action_type=ActionType.HORA,
                player=player_seat,
                tile=player.hand[-1] if player.hand else None,
            ))

        if not player.is_riichi:
            # 暗槓判定
            from collections import Counter
            tile_keys = [(t.suit, t.number) for t in player.hand]
            cnt = Counter(tile_keys)
            for (suit, num), count in cnt.items():
                if count == 4:
                    options.append(GameAction(
                        action_type=ActionType.ANKAN,
                        player=player_seat,
                        tile=Tile(suit=suit, number=num),
                    ))

            # リーチ判定
            if player.is_menzen and player.score >= 1000 and st.tiles_remaining >= 4:
                riichi_tiles = self._get_riichi_tiles(player_seat)
                for t in riichi_tiles:
                    options.append(GameAction(
                        action_type=ActionType.RIICHI,
                        player=player_seat,
                        tile=t,
                    ))

        return options

    # ============================================================
    # 和了判定
    # ============================================================

    def _can_tsumo(self, player_seat: int) -> bool:
        """ツモ和了可能か"""
        player = self.state.players[player_seat]
        return self._is_agari(player.hand)

    def _can_ron(self, player_seat: int, tile: Tile) -> bool:
        """ロン和了可能か"""
        player = self.state.players[player_seat]
        test_hand = player.hand + [tile]
        return self._is_agari(test_hand)

    def _is_agari(self, hand: list[Tile]) -> bool:
        """和了形かチェック（簡易版：mahjongライブラリに委譲）"""
        from mahjong.shanten import Shanten
        shanten = Shanten()
        tiles_34 = self._hand_to_34(hand)
        return shanten.calculate_shanten(tiles_34) == -1

    def _get_riichi_tiles(self, player_seat: int) -> list[Tile]:
        """リーチ可能な牌のリストを返す"""
        player = self.state.players[player_seat]
        riichi_tiles: list[Tile] = []
        seen = set()

        for tile in player.hand:
            key = (tile.suit, tile.number)
            if key in seen:
                continue
            seen.add(key)

            test_hand = list(player.hand)
            for i, t in enumerate(test_hand):
                if t.suit == tile.suit and t.number == tile.number:
                    test_hand.pop(i)
                    break
            tiles_34 = self._hand_to_34(test_hand)

            from mahjong.shanten import Shanten
            shanten = Shanten()
            if shanten.calculate_shanten(tiles_34) == 0:
                riichi_tiles.append(tile)

        return riichi_tiles

    # ============================================================
    # 次のターンへ
    # ============================================================

    def advance_turn(self):
        """打牌後に鳴きがなければ次のプレイヤーへ"""
        st = self.state
        st.current_player = (st.current_player + 1) % 4
        st.phase = GamePhase.PLAYER_TURN

    # ============================================================
    # 流局
    # ============================================================

    def _handle_ryukyoku(self):
        """荒牌流局の処理"""
        st = self.state
        st.phase = GamePhase.ROUND_END

        # テンパイ判定
        tenpai = []
        noten = []
        for p in st.players:
            tiles_34 = self._hand_to_34(p.hand)
            from mahjong.shanten import Shanten
            shanten = Shanten()
            if shanten.calculate_shanten(tiles_34) == 0:
                tenpai.append(p.seat)
            else:
                noten.append(p.seat)

        # ノーテン罰符
        tenpai_info = []
        score_changes = []
        
        for i in range(4):
            tenpai_info.append({"seat": i, "tenpai": False, "delta": 0})
            
        if 0 < len(tenpai) < 4:
            penalty_total = 3000
            pay_each = penalty_total // len(noten)
            get_each = penalty_total // len(tenpai)
            for seat in noten:
                st.players[seat].score -= pay_each
                tenpai_info[seat]["delta"] = -pay_each
                score_changes.append({"player": seat, "delta": -pay_each})
            for seat in tenpai:
                st.players[seat].score += get_each
                tenpai_info[seat]["delta"] = get_each
                score_changes.append({"player": seat, "delta": get_each})
                
        for seat in tenpai:
            tenpai_info[seat]["tenpai"] = True

        self._emit({
            "type": "ryukyoku",
            "tenpai": tenpai,
            "tenpai_info": tenpai_info,
            "score_changes": score_changes,
            "hands": [[t.id for t in p.hand] for p in st.players],
            "scores": [p.score for p in st.players],
            "round": st.round_name_ja,
        })

        # 次局へ
        self._advance_round(tenpai_seats=tenpai)

    # ============================================================
    # 和了処理
    # ============================================================

    def handle_hora(self, winner_seat: int, from_seat: int,
                    is_tsumo: bool) -> dict:
        """和了を処理し、点数を計算"""
        st = self.state
        winner = st.players[winner_seat]
        win_tile = winner.hand[-1] if is_tsumo else st.last_discard

        # mahjong ライブラリで点数計算
        result = self._calculate_score(winner_seat, win_tile, is_tsumo)

        # 点数移動
        if is_tsumo:
            for p in st.players:
                if p.seat != winner_seat:
                    if p.seat == st.dealer or winner_seat == st.dealer:
                        p.score -= result["ko_payment"]
                    else:
                        p.score -= result["ko_payment"]
            winner.score += result["total_points"]
        else:
            st.players[from_seat].score -= result["total_points"]
            winner.score += result["total_points"]

        # リーチ棒回収
        winner.score += st.riichi_sticks * 1000
        st.riichi_sticks = 0

        # 本場加算
        winner.score += st.honba * 300

        st.phase = GamePhase.ROUND_END

        hora_event = {
            "type": "hora",
            "actor": winner_seat,
            "target": from_seat if not is_tsumo else winner_seat,
            "pai": win_tile.id if win_tile else "unknown",
            "is_tsumo": is_tsumo,
            "yakus": result.get("yakus", []),
            "han": result.get("han", 0),
            "fu": result.get("fu", 0),
            "points": result.get("total_points", 0),
            "scores": [p.score for p in st.players],
        }
        self._emit(hora_event)

        # 次局へ
        is_dealer_win = winner_seat == st.dealer
        if is_dealer_win:
            self._advance_round(dealer_win=True)
        else:
            self._advance_round(dealer_win=False)

        return hora_event

    def _calculate_score(self, winner_seat: int, win_tile: Optional[Tile],
                         is_tsumo: bool) -> dict:
        """mahjong ライブラリで点数計算"""
        from mahjong.hand_calculating.hand import HandCalculator
        from mahjong.hand_calculating.hand_config import HandConfig
        from mahjong.tile import TilesConverter
        from mahjong.meld import Meld as MjMeld
        from mahjong.hand_calculating.hand_config import OptionalRules

        st = self.state
        winner = st.players[winner_seat]
        calculator = HandCalculator()

        # 手牌を136形式に変換
        man = ""
        pin = ""
        sou = ""
        honors = ""
        for t in winner.hand:
            if t == win_tile and not is_tsumo:
                continue  # ロン牌は別途指定
            if t.suit == TileSuit.MAN:
                man += str(t.number)
            elif t.suit == TileSuit.PIN:
                pin += str(t.number)
            elif t.suit == TileSuit.SOU:
                sou += str(t.number)
            elif t.suit == TileSuit.WIND:
                honors += str(t.number)

        try:
            tiles = TilesConverter.string_to_136_array(
                man=man, pin=pin, sou=sou, honors=honors
            )

            # 和了牌
            wt_man = str(win_tile.number) if win_tile and win_tile.suit == TileSuit.MAN else ""
            wt_pin = str(win_tile.number) if win_tile and win_tile.suit == TileSuit.PIN else ""
            wt_sou = str(win_tile.number) if win_tile and win_tile.suit == TileSuit.SOU else ""
            wt_hon = str(win_tile.number) if win_tile and win_tile.suit == TileSuit.WIND else ""

            win_tile_136 = TilesConverter.string_to_136_array(
                man=wt_man, pin=wt_pin, sou=wt_sou, honors=wt_hon
            )[0]

            # 副露
            melds_mj = []
            for m in winner.melds:
                m_man = ""
                m_pin = ""
                m_sou = ""
                m_hon = ""
                for t in m.tiles:
                    if t.suit == TileSuit.MAN:
                        m_man += str(t.number)
                    elif t.suit == TileSuit.PIN:
                        m_pin += str(t.number)
                    elif t.suit == TileSuit.SOU:
                        m_sou += str(t.number)
                    elif t.suit == TileSuit.WIND:
                        m_hon += str(t.number)

                meld_tiles = TilesConverter.string_to_136_array(
                    man=m_man, pin=m_pin, sou=m_sou, honors=m_hon
                )
                opened = m.meld_type != MeldType.ANKAN
                meld_type_str = "chi" if m.meld_type == MeldType.CHI else "pon"
                if m.meld_type in (MeldType.ANKAN, MeldType.DAIMINKAN, MeldType.KAKAN):
                    meld_type_str = "kan"
                melds_mj.append(MjMeld(
                    meld_type=meld_type_str,
                    tiles=meld_tiles,
                    opened=opened,
                ))

            # 場風・自風
            round_wind_map = {
                Wind.EAST: 27, Wind.SOUTH: 28,
                Wind.WEST: 29, Wind.NORTH: 30,
            }
            player_wind_map = {
                0: 27, 1: 28, 2: 29, 3: 30,
            }
            # 席を場の中で計算
            relative_seat = (winner_seat - st.dealer) % 4

            config = HandConfig(
                is_tsumo=is_tsumo,
                is_riichi=winner.is_riichi,
                is_ippatsu=winner.is_ippatsu,
                is_daburu_riichi=winner.is_double_riichi,
                player_wind=TilesConverter.string_to_136_array(
                    honors=str(relative_seat + 1)
                )[0] if True else None,
                round_wind=TilesConverter.string_to_136_array(
                    honors=str(st.round_wind.value + 1)
                )[0] if True else None,
                options=OptionalRules(
                    has_aka_dora=self.use_red_dora,
                ),
            )

            result = calculator.estimate_hand_value(
                tiles=tiles + [win_tile_136],
                win_tile=win_tile_136,
                melds=melds_mj if melds_mj else None,
                config=config,
                dora_indicators=TilesConverter.string_to_136_array(
                    man="".join(str(t.number) for t in st.dora_indicators if t.suit == TileSuit.MAN),
                    pin="".join(str(t.number) for t in st.dora_indicators if t.suit == TileSuit.PIN),
                    sou="".join(str(t.number) for t in st.dora_indicators if t.suit == TileSuit.SOU),
                    honors="".join(str(t.number) for t in st.dora_indicators if t.suit == TileSuit.WIND),
                ) if st.dora_indicators else None,
            )

            if result.error is None:
                yakus = []
                for yaku in result.yaku:
                    yakus.append({
                        "name": yaku.name,
                        "han": yaku.han_closed if winner.is_menzen else yaku.han_open,
                    })

                is_dealer = winner_seat == st.dealer
                if is_tsumo:
                    if is_dealer:
                        ko_pay = result.cost["main"]
                        total = ko_pay * 3
                    else:
                        ko_pay = result.cost["additional"]
                        oya_pay = result.cost["main"]
                        total = ko_pay * 2 + oya_pay
                else:
                    total = result.cost["main"]
                    ko_pay = 0

                return {
                    "yakus": yakus,
                    "han": result.han,
                    "fu": result.fu,
                    "total_points": total,
                    "ko_payment": ko_pay,
                    "cost": result.cost,
                }
        except Exception as e:
            print(f"点数計算エラー: {e}")

        # フォールバック：エラー時は基本点
        return {
            "yakus": [{"name": "不明", "han": 1}],
            "han": 1,
            "fu": 30,
            "total_points": 1000,
            "ko_payment": 500,
        }

    # ============================================================
    # 局の進行
    # ============================================================

    def _advance_round(self, dealer_win: bool = False,
                       tenpai_seats: Optional[list[int]] = None):
        """次の局へ進む"""
        st = self.state

        if dealer_win or (tenpai_seats and st.dealer in tenpai_seats):
            # 連荘
            st.honba += 1
        else:
            # 親移動
            st.dealer = (st.dealer + 1) % 4
            st.round_number += 1
            st.honba = 0 if not (tenpai_seats and st.dealer in (tenpai_seats or [])) else st.honba + 1

            # 南場→終了判定
            if st.round_wind == Wind.EAST and st.round_number >= 4:
                st.round_wind = Wind.SOUTH
                st.round_number = 0
            elif st.round_wind == Wind.SOUTH and st.round_number >= 4:
                self._handle_game_end()
                return

        # 終了条件：誰かが0点以下
        for p in st.players:
            if p.score < 0:
                self._handle_game_end()
                return

    def _handle_game_end(self):
        """対局終了"""
        st = self.state
        st.phase = GamePhase.GAME_END
        self._emit({
            "type": "end_game",
            "scores": [p.score for p in st.players],
        })

    # ============================================================
    # ユーティリティ
    # ============================================================

    def _hand_to_34(self, hand: list[Tile]) -> list[int]:
        """手牌を34種形式に変換（mahjongライブラリ用）"""
        tiles_34 = [0] * 34
        for t in hand:
            idx = self._tile_to_34_index(t)
            tiles_34[idx] += 1
        return tiles_34

    @staticmethod
    def _tile_to_34_index(tile: Tile) -> int:
        """牌を34種インデックスに変換"""
        if tile.suit == TileSuit.MAN:
            return tile.number - 1          # 0-8
        elif tile.suit == TileSuit.PIN:
            return 9 + tile.number - 1      # 9-17
        elif tile.suit == TileSuit.SOU:
            return 18 + tile.number - 1     # 18-26
        else:  # WIND
            return 27 + tile.number - 1     # 27-33

    def get_shanten(self, player_seat: int) -> int:
        """プレイヤーの向聴数を取得"""
        from mahjong.shanten import Shanten
        player = self.state.players[player_seat]
        tiles_34 = self._hand_to_34(player.hand)
        shanten = Shanten()
        return shanten.calculate_shanten(tiles_34)

    def get_waiting_tiles(self, player_seat: int) -> list[Tile]:
        """テンパイ時の待ち牌リスト"""
        player = self.state.players[player_seat]
        if self.get_shanten(player_seat) != 0:
            return []

        waiting: list[Tile] = []
        for suit in [TileSuit.MAN, TileSuit.PIN, TileSuit.SOU]:
            for num in range(1, 10):
                test_tile = Tile(suit=suit, number=num)
                test_hand = player.hand + [test_tile]
                if self._is_agari(test_hand):
                    waiting.append(test_tile)
        for num in range(1, 8):
            test_tile = Tile(suit=TileSuit.WIND, number=num)
            test_hand = player.hand + [test_tile]
            if self._is_agari(test_hand):
                waiting.append(test_tile)

        return waiting

    def to_state_dict(self, for_player: Optional[int] = None) -> dict:
        """ゲーム状態をJSON互換のdictにシリアライズ。
        for_player が指定された場合、他家の手牌は隠す。"""
        st = self.state
        players_data = []
        for p in st.players:
            pd = {
                "seat": p.seat,
                "score": p.score,
                "discards": [t.id for t in p.discards],
                "melds": [
                    {
                        "type": m.meld_type.value,
                        "tiles": [t.id for t in m.tiles],
                        "from": m.from_player,
                    }
                    for m in p.melds
                ],
                "is_riichi": p.is_riichi,
                "hand_count": len(p.hand),
            }
            if for_player is None or p.seat == for_player:
                # ツモ番で手牌が14(11,8..)枚の場合、引いた牌(末尾)はソートせずに右端へ
                is_tsumo_phase = st.phase == GamePhase.PLAYER_TURN and st.current_player == p.seat and len(p.hand) % 3 == 2
                if is_tsumo_phase:
                    sorted_base = sorted(p.hand[:-1], key=lambda x: x.sort_key)
                    pd["hand"] = [t.id for t in sorted_base] + [p.hand[-1].id]
                else:
                    pd["hand"] = [t.id for t in sorted(p.hand, key=lambda x: x.sort_key)]
            else:
                pd["hand"] = None  # 非公開
            players_data.append(pd)

        # Phase 2: 向聴数・待ち牌をクライアントに送信
        shanten_value = None
        waiting_tile_ids = None
        if for_player is not None:
            try:
                from mahjong.shanten import Shanten
                player_hand = st.players[for_player].hand
                if player_hand and len(player_hand) >= 1:
                    tiles_34 = self._hand_to_34(player_hand)
                    shanten_calc = Shanten()
                    shanten_value = shanten_calc.calculate_shanten(tiles_34)
                    # テンパイ時は待ち牌も計算
                    if shanten_value == 0 and len(player_hand) % 3 == 1:
                        waiting = self.get_waiting_tiles(for_player)
                        waiting_tile_ids = [t.id for t in waiting]
            except Exception:
                pass

        result = {
            "round_wind": st.round_wind.name.lower(),
            "round_number": st.round_number + 1,
            "round_name": st.round_name_ja,
            "honba": st.honba,
            "riichi_sticks": st.riichi_sticks,
            "dealer": st.dealer,
            "current_player": st.current_player,
            "phase": st.phase.value,
            "tiles_remaining": st.tiles_remaining,
            "dora_indicators": [t.id for t in st.dora_indicators],
            "players": players_data,
            "turn_count": st.turn_count,
        }

        if shanten_value is not None:
            result["shanten"] = shanten_value
        if waiting_tile_ids is not None:
            result["waiting_tiles"] = waiting_tile_ids

        return result
