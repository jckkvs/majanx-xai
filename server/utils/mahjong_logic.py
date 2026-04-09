"""
server/utils/mahjong_logic.py
戦略判定エンジンが参照する実計算ロジック

牌形状解析・翻数推定・危険度計算・受入枚数計算を提供。
server/models.py の Tile/GameState/PlayerState を直接操作する。
"""
from __future__ import annotations
from collections import Counter
from typing import Dict, List, Tuple, Optional
from server.models import Tile, TileSuit, GameState, PlayerState, Wind


# ============================================================
# 牌カウントユーティリティ
# ============================================================

def count_tiles(hand: List[Tile]) -> Counter:
    """手牌をID単位でカウント"""
    return Counter(t.id for t in hand)


def tile_to_34idx(t: Tile) -> int:
    """牌を0-33のインデックスへ変換"""
    suit_offset = {"m": 0, "p": 9, "s": 18, "z": 27}
    return suit_offset[t.suit.value] + t.number - 1


def hand_to_34(hand: List[Tile]) -> List[int]:
    """手牌を34要素の配列に変換"""
    arr = [0] * 34
    for t in hand:
        idx = tile_to_34idx(t)
        if 0 <= idx < 34:
            arr[idx] += 1
    return arr


# ============================================================
# 形状解析
# ============================================================

def analyze_shape(hand: List[Tile]) -> Dict:
    """
    手牌の形状を解析し、ターツ・対子・孤立牌を定量化する。
    
    Returns:
        dict: {
            "ryanmen": int,      # 両面ターツ数
            "kanchan": int,      # 嵌張ターツ数
            "pair": int,         # 対子数
            "isolated": list,    # 孤立牌ID一覧
            "dora_count": int,   # 赤ドラ数
            "has_4_connected": bool,  # 4連形の有無
            "has_nakabukure": bool,   # 中膨れの有無
            "suit_counts": dict,      # スート別枚数
        }
    """
    counts = count_tiles(hand)
    arr34 = hand_to_34(hand)
    
    shape_info = {
        "ryanmen": 0,
        "kanchan": 0,
        "pair": 0,
        "isolated": [],
        "dora_count": 0,
        "has_4_connected": False,
        "has_nakabukure": False,
        "suit_counts": {"m": 0, "p": 0, "s": 0, "z": 0},
    }
    
    # 赤ドラカウント
    shape_info["dora_count"] = sum(1 for t in hand if t.is_red)
    
    # スート別カウント
    for t in hand:
        shape_info["suit_counts"][t.suit.value] += 1
    
    # 数牌スート別の形状解析
    for suit_char, offset in [("m", 0), ("p", 9), ("s", 18)]:
        nums = arr34[offset:offset + 9]
        
        # 両面・嵌張検出
        for i in range(8):
            if nums[i] >= 1 and nums[i + 1] >= 1:
                shape_info["ryanmen"] += 1
        for i in range(7):
            if nums[i] >= 1 and nums[i + 1] == 0 and nums[i + 2] >= 1:
                shape_info["kanchan"] += 1
        
        # 4連形検出 (2345, 3456, 4567, 5678 等)
        for i in range(6):
            if all(nums[i + j] >= 1 for j in range(4)):
                shape_info["has_4_connected"] = True
                break
        
        # 中膨れ検出 (2334, 3445 等: AaBBc形)
        for i in range(7):
            if nums[i] >= 1 and nums[i + 1] >= 2 and i + 2 < 9 and nums[i + 2] >= 1:
                shape_info["has_nakabukure"] = True
                break
    
    # 対子・孤立字牌検出
    for idx in range(34):
        if arr34[idx] == 2:
            shape_info["pair"] += 1
        elif arr34[idx] == 1:
            # 数牌はターツの可能性があるので孤立判定を分離
            suit_idx = idx // 9 if idx < 27 else 3
            if suit_idx == 3:
                # 字牌の孤立
                suits = ["m", "p", "s", "z"]
                num = (idx - 27) + 1 if idx >= 27 else (idx % 9) + 1
                s = suits[suit_idx]
                shape_info["isolated"].append(f"{num}{s}")
            else:
                num = (idx % 9) + 1
                suits = ["m", "p", "s"]
                s = suits[suit_idx]
                # 隣接牌がなければ孤立
                has_neighbor = False
                pos = idx % 9
                if pos > 0 and arr34[idx - 1] >= 1:
                    has_neighbor = True
                if pos < 8 and arr34[idx + 1] >= 1:
                    has_neighbor = True
                if not has_neighbor:
                    shape_info["isolated"].append(f"{num}{s}")
    
    return shape_info


# ============================================================
# 翻数推定
# ============================================================

def is_yakuhai(tile: Tile, round_wind: Wind, seat_wind: Wind) -> bool:
    """役牌かどうか判定"""
    if tile.suit != TileSuit.WIND:
        return False
    # 三元牌（白=5, 發=6, 中=7）
    if tile.number >= 5:
        return True
    # 場風
    if tile.number == round_wind.value + 1:
        return True
    # 自風
    if tile.number == seat_wind.value + 1:
        return True
    return False


def estimate_han(hand: List[Tile], gs: GameState, seat: int) -> Tuple[int, int]:
    """
    確定翻数と潜在翻数を簡易推定する。
    
    Returns:
        (current_han, potential_han)
    """
    player = gs.players[seat]
    arr34 = hand_to_34(hand)
    
    current_han = 0
    potential_han = 0
    
    # ドラ枚数（赤ドラ + 表ドラ）
    dora_count = sum(1 for t in hand if t.is_red)
    for dora in gs.dora_tiles:
        dora_idx = tile_to_34idx(dora)
        dora_count += arr34[dora_idx]
    current_han += dora_count
    potential_han += dora_count
    
    # 役牌対子 → 潜在+1
    seat_wind_map = {0: Wind.EAST, 1: Wind.SOUTH, 2: Wind.WEST, 3: Wind.NORTH}
    seat_wind = seat_wind_map.get(seat, Wind.EAST)
    
    has_yakuhai_pair = False
    for idx in range(27, 34):
        if arr34[idx] >= 2:
            num = idx - 27 + 1
            test_tile = Tile(suit=TileSuit.WIND, number=num)
            if is_yakuhai(test_tile, gs.round_wind, seat_wind):
                potential_han += 1
                has_yakuhai_pair = True
    
    # リーチ可能なら +1
    if player.is_menzen and not player.is_riichi:
        potential_han += 1
    
    # 門前ツモ +1 (潜在)
    if player.is_menzen:
        potential_han += 1
    
    # タンヤオ簡易判定（全牌2-8の数牌）
    all_tanyao = all(
        t.suit != TileSuit.WIND and 2 <= t.number <= 8
        for t in hand
    )
    if all_tanyao:
        current_han += 1
        potential_han += 1
    
    # current は確定分のみ
    current_han = max(current_han, 0)
    potential_han = max(potential_han, current_han)
    
    return current_han, potential_han


def has_yakuhai_pair_in_hand(hand: List[Tile], gs: GameState, seat: int) -> bool:
    """手牌に役牌対子があるか"""
    arr34 = hand_to_34(hand)
    seat_wind_map = {0: Wind.EAST, 1: Wind.SOUTH, 2: Wind.WEST, 3: Wind.NORTH}
    seat_wind = seat_wind_map.get(seat, Wind.EAST)
    
    for idx in range(27, 34):
        if arr34[idx] >= 2:
            num = idx - 27 + 1
            test_tile = Tile(suit=TileSuit.WIND, number=num)
            if is_yakuhai(test_tile, gs.round_wind, seat_wind):
                return True
    return False


# ============================================================
# 危険度計算
# ============================================================

def calculate_danger(tile: Tile, gs: GameState, seat: int) -> float:
    """
    指定牌の危険度を計算 (0.0=安全, 1.0=危険)
    
    判定順序:
      1. 現物 → 0.0
      2. 壁(3枚見え) → 0.05
      3. 壁(2枚見え) → 0.25
      4. リーチ下の中張(3-7) → 0.75
      5. リーチ下の端牌/字牌 → 0.40
      6. 通常 → 0.20
    """
    # 場に見えている枚数を計算
    visible = 0
    for p in gs.players:
        for d in p.discards:
            if d.suit == tile.suit and d.number == tile.number:
                visible += 1
        # 副露も含む
        for meld in p.melds:
            for mt in meld.tiles:
                if mt.suit == tile.suit and mt.number == tile.number:
                    visible += 1
    
    # ドラ表示牌も見える
    for di in gs.dora_indicators:
        if di.suit == tile.suit and di.number == tile.number:
            visible += 1
    
    # 1. 現物判定（リーチ者の捨て牌にある）
    for p in gs.players:
        if p.is_riichi and p.seat != seat:
            for d in p.discards:
                if d.suit == tile.suit and d.number == tile.number:
                    return 0.0
    
    # 2. 壁
    if visible >= 3:
        return 0.05
    if visible == 2:
        return 0.25
    
    # 3. リーチ下判定
    riichi_count = sum(1 for p in gs.players if p.is_riichi and p.seat != seat)
    if riichi_count > 0:
        if tile.suit != TileSuit.WIND and 3 <= tile.number <= 7:
            return 0.75  # 中張高危険
        return 0.40  # 端牌/字牌は中危険
    
    return 0.20  # 通常


def find_genbutsu(hand: List[Tile], gs: GameState, seat: int) -> List[str]:
    """手牌内の現物（絶対安全牌）を列挙"""
    safe = []
    for t in hand:
        if calculate_danger(t, gs, seat) == 0.0:
            safe.append(t.id)
    return list(set(safe))

# ============================================================
# 受入枚数計算
# ============================================================

def estimate_ukeire(hand: List[Tile], discard: Tile) -> int:
    """
    打牌後の簡易受入枚数を計算。
    両面=8枚, 嵌張=4枚, 対子=2枚 の加算による概算。
    """
    sim_hand = [t for t in hand if not (t.suit == discard.suit and t.number == discard.number and t.is_red == discard.is_red)]
    # 1枚だけ除去（同一牌が複数ある場合）
    if len(sim_hand) == len(hand):
        # 赤ドラ区別なしで除去
        for i, t in enumerate(hand):
            if t.suit == discard.suit and t.number == discard.number:
                sim_hand = hand[:i] + hand[i+1:]
                break

    shape = analyze_shape(sim_hand)
    return (shape["ryanmen"] * 8) + (shape["kanchan"] * 4) + (shape["pair"] * 2)


def estimate_ukeire_precise(hand: List[Tile], discard: Tile,
                             gs: Optional[GameState] = None,
                             turn: int = 1) -> Dict:
    """
    精密版受入枚数計算。場見え補正+巡目補正+質スコアを含む。

    Returns:
        dict: {
            "nominal": int,       # 名目受入枚数
            "adjusted": int,      # 場見え補正後
            "turn_adjusted": float, # 巡目補正後
            "quality": float,     # 質スコア(0-1)
            "growth": float,      # 2段目受入の伸び
        }
    """
    nominal = estimate_ukeire(hand, discard)

    # 場見え補正（gsがあれば実施）
    adjusted = nominal
    if gs:
        # 簡易: 場に見えている牌数で全体を補正
        total_visible = sum(len(p.discards) for p in gs.players)
        total_visible += sum(
            len(m.tiles) for p in gs.players for m in p.melds
        )
        # 全136枚中の見え枚数比率で受入を補正
        visible_ratio = total_visible / 136.0
        adjusted = max(0, int(nominal * (1.0 - visible_ratio * 0.5)))

    # 巡目補正係数
    if turn <= 5:
        turn_coeff = 1.0
    elif turn <= 10:
        turn_coeff = 0.85
    elif turn <= 15:
        turn_coeff = 0.65
    else:
        turn_coeff = 0.40
    turn_adjusted = adjusted * turn_coeff

    # 質スコア: 両面比率が高いほど質が高い
    sim_hand = [t for t in hand if not (t.suit == discard.suit and t.number == discard.number)]
    if len(sim_hand) == len(hand):
        for i, t in enumerate(hand):
            if t.suit == discard.suit and t.number == discard.number:
                sim_hand = hand[:i] + hand[i+1:]
                break
    shape = analyze_shape(sim_hand)
    total_tatsu = shape["ryanmen"] + shape["kanchan"] + shape["pair"]
    quality = shape["ryanmen"] / max(total_tatsu, 1)

    # 2段目伸び: 4連形は伸びが高い
    growth = 0.0
    if shape["has_4_connected"]:
        growth = adjusted * 0.3 * 0.7  # 4連形なら伸びが大きい
    elif shape["ryanmen"] >= 2:
        growth = adjusted * 0.3 * 0.5
    else:
        growth = adjusted * 0.3 * 0.2

    return {
        "nominal": nominal,
        "adjusted": adjusted,
        "turn_adjusted": round(turn_adjusted, 1),
        "quality": round(quality, 2),
        "growth": round(growth, 1),
    }


# ============================================================
# 統合コンテキスト生成
# ============================================================

def build_full_context(gs: GameState, seat: int) -> Dict:
    """
    GameStateとseat番号から、全エンジンが必要とする
    完全なコンテキスト辞書を生成する。

    v3: 振聴情報・終局情報・受入品質を追加。
    """
    player = gs.players[seat]
    hand = player.hand

    # 順位計算
    scores = [(p.seat, p.score) for p in gs.players]
    scores.sort(key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (s, _) in enumerate(scores) if s == seat), 1)

    # リーチ数
    riichi_count = sum(1 for p in gs.players if p.is_riichi and p.seat != seat)

    # 危険度判定
    if riichi_count >= 2:
        danger = "high"
    elif riichi_count >= 1:
        danger = "med"
    else:
        danger = "low"

    # 形状解析
    shape = analyze_shape(hand)

    # 翻数推定
    current_han, potential_han = estimate_han(hand, gs, seat)

    # 役牌対子
    yakuhai_pair = has_yakuhai_pair_in_hand(hand, gs, seat)

    # 現物
    genbutsu = find_genbutsu(hand, gs, seat)

    # 向聴数
    try:
        shanten = gs.get_player_shanten(seat)
    except Exception:
        shanten = 6

    # 終局判定（残り局数）
    round_num = gs.round_wind.value
    dealer_pos = gs.dealer
    current_round = round_num * 4 + dealer_pos + 1
    remaining_rounds = max(0, 8 - current_round)

    return {
        "turn": gs.turn_count,
        "dealer_status": gs.dealer == seat,
        "riichi": riichi_count,
        "score_diff": player.score - 25000,
        "rank": rank,
        "honba": gs.honba,
        "danger": danger,
        # 翻数・打点（実計算）
        "current_han": current_han,
        "potential_han": potential_han,
        "fu": 30,  # 符は簡易固定（将来拡張）
        # 形状フラグ（実計算）
        "has_yakuhai_pair": yakuhai_pair,
        "has_4_connected": shape["has_4_connected"],
        "has_nakabukure": shape["has_nakabukure"],
        "is_genbutsu": len(genbutsu) > 0,
        # 追加情報
        "shanten": shanten,
        "dora_count": shape["dora_count"],
        "ryanmen_count": shape["ryanmen"],
        "isolated_count": len(shape["isolated"]),
        "genbutsu_tiles": genbutsu,
        # Phase2用: 手牌オブジェクト・GS・seat・孤立牌ID
        "hand_tiles": hand,
        "isolated_tiles": shape["isolated"],
        "_gs": gs,
        "_seat": seat,
        # v3追加: 終局情報
        "remaining_rounds": remaining_rounds,
        "is_endgame": remaining_rounds <= 2,
        # v3追加: 全プレイヤー点数（終局EV計算用）
        "all_scores": {p.seat: p.score for p in gs.players},
    }

