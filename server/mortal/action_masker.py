import numpy as np
from typing import List, Dict, Optional
from mahjong.agari import Agari
from mahjong.tile import TilesConverter

class ActionMasker:
    """Mortal用 46次元合法アクションマスク生成器"""
    # アクションインデックス定義 (Mortal準拠)
    ACTION_DAHAI = list(range(34))          # 0-33: 打牌(1m~9s)
    ACTION_TSUMOGIRI = 34                   # 34: ツモ切り
    ACTION_CHI = 35                         # 35: チー
    ACTION_PON = 36                         # 36: ポン
    ACTION_KAN_OPEN = 37                    # 37: 大明槓
    ACTION_KAN_CLOSED = 38                  # 38: 暗槓
    ACTION_KAN_ADDED = 39                   # 39: 加槓
    ACTION_RON = 40                         # 40: ロン (ツモ和了も含む)
    ACTION_NONE = 41                        # 41: パス/なし
    # 42-45: リザーブ（将来拡張用）

    def __init__(self):
        self.agari_calc = Agari()

    def generate_mask(self, hand_34: List[int], tsumo_idx: int, last_dahai: str,
                      last_dahai_actor: int, river_34: List[int], round_info: Dict) -> np.ndarray:
        """
        現在の局面から合法手マスク(46)を生成
        """
        mask = np.zeros(46, dtype=bool)
        if tsumo_idx < 0:  # 他家打牌待ち時
            return self._mask_for_others_play(hand_34, last_dahai, last_dahai_actor, round_info, mask)
        
        # 自番ツモ時
        return self._mask_for_self_draw(hand_34, tsumo_idx, river_34, round_info, mask)

    def _mask_for_self_draw(self, hand_34, tsumo_idx, river_34, info, mask):
        full = hand_34.copy()
        if tsumo_idx >= 0: full[tsumo_idx] += 1

        # 打牌・ツモ切り判定
        for i in self.ACTION_DAHAI:
            mask[i] = full[i] > 0
        mask[self.ACTION_TSUMOGIRI] = tsumo_idx >= 0 and full[tsumo_idx] > 0

        # 暗槓判定
        if tsumo_idx >= 0 and full[tsumo_idx] == 4:
            mask[self.ACTION_KAN_CLOSED] = True
            
        # 加槓判定
        for i in range(34):
            if full[i] == 3 and (i // 9 != 3 or i % 9 < 4): # 字牌は南まで(白発中は適当に扱う等、仕様依存)
                # 既存の刻子から加槓可能か（簡易判定）
                mask[self.ACTION_KAN_ADDED] = True
                break

        # 立直制限: 立直後は打牌・ツモ切りのみ
        if info.get("is_riichi", False):
            mask[self.ACTION_CHI] = mask[self.ACTION_PON] = mask[self.ACTION_KAN_OPEN] = False
            mask[self.ACTION_KAN_CLOSED] = mask[self.ACTION_KAN_ADDED] = False # 待ち牌固定後加槓不可
            
            # 立直後はツモ切り以外不許可
            for i in self.ACTION_DAHAI:
                mask[i] = False
            if tsumo_idx >= 0:
                mask[tsumo_idx] = True # ツモ牌がどれか分かればそれだけ打てる (実質ツモ切り)
                mask[self.ACTION_TSUMOGIRI] = True

        # 和了判定(ツモ)
        if self.agari_calc.is_agari(full):
            mask[self.ACTION_RON] = True # mjaiではツモ和了もロンフラグ等で表現

        return mask

    def _mask_for_others_play(self, hand_34, last_dahai, actor, info, mask):
        if not last_dahai: return mask
        tile_idx = TilesConverter.string_to_34_array([last_dahai])[0]
        
        # チー判定
        suit = tile_idx // 9
        num = tile_idx % 9 + 1
        if suit < 3 and num > 2:  # チー可能数牌
            needed = [num-2, num-1]
            if all(hand_34[suit*9 + n - 1] > 0 for n in needed):
                mask[self.ACTION_CHI] = True
                
        # ポン判定
        if hand_34[tile_idx] >= 2:
            mask[self.ACTION_PON] = True
            
        # 大明槓判定
        if hand_34[tile_idx] >= 3:
            mask[self.ACTION_KAN_OPEN] = True

        # ロン判定（振聴・立直・フリテンチェック）
        can_ron = self._check_ron_valid(hand_34, tile_idx, info)
        if can_ron:
            mask[self.ACTION_RON] = True

        mask[self.ACTION_NONE] = True # スキップは常に可能
        return mask

    def _check_ron_valid(self, hand_34, tile_idx, info) -> bool:
        # 振聴チェック（自分の捨て牌に待ち牌が含まれていないか等）
        # 簡易版：Agari判定
        sim = hand_34.copy()
        sim[tile_idx] += 1
        # 和了形かどうかだけチェック
        return self.agari_calc.is_agari(sim)
