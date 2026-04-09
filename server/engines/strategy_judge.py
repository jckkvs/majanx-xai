"""
server/engines/strategy_judge.py
方向性2: 戦略判断ルールエンジン（Phase1+Phase2 打牌連動版）

Phase 1: 状況分析 → 戦略タグ判定
  SPEED_PUSH / VALUE_PUSH / DEFENSIVE_FOLD / BALANCED_SHAPE / RISKY_PUSH

Phase 2: 手牌スコアリング → 具体的打牌選択
  戦略タグに応じた重み関数で各手牌をスコアリングし、最高スコアの牌を推奨。
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 翻数→点数マッピング（子）
HAN_TO_POINTS = {
    1: 1000, 2: 2000, 3: 3900, 4: 7700,
    5: 8000, 6: 12000, 7: 12000, 8: 16000,
    9: 16000, 10: 16000, 11: 24000, 12: 24000, 13: 32000
}

# 戦略タグ間の競合解決マトリクス（row beats column の確率）
PRIORITY_MATRIX = {
    "DEFENSIVE_FOLD": {"VALUE_PUSH": 0.7, "SPEED_PUSH": 0.9, "BALANCED_SHAPE": 0.8, "RISKY_PUSH": 0.95},
    "VALUE_PUSH":     {"DEFENSIVE_FOLD": 0.3, "SPEED_PUSH": 0.6, "BALANCED_SHAPE": 0.7, "RISKY_PUSH": 0.4},
    "SPEED_PUSH":     {"DEFENSIVE_FOLD": 0.1, "VALUE_PUSH": 0.4, "BALANCED_SHAPE": 0.6, "RISKY_PUSH": 0.3},
    "BALANCED_SHAPE":  {"DEFENSIVE_FOLD": 0.2, "VALUE_PUSH": 0.3, "SPEED_PUSH": 0.4, "RISKY_PUSH": 0.2},
    "RISKY_PUSH":     {"DEFENSIVE_FOLD": 0.05, "VALUE_PUSH": 0.6, "SPEED_PUSH": 0.7, "BALANCED_SHAPE": 0.8},
}

# 信頼度の状況補正係数
CONFIDENCE_ADJUSTMENTS = {
    "turn_early": 1.1,    # 序盤は情報が少ないが形状判断は確実
    "turn_late": 0.9,     # 終盤は変動性が高い
    "dealer_bonus": 1.05, # 親番は和了メリット大
    "top_defense": 1.2,   # トップの守り切りは確実性高
}


@dataclass
class HanEvaluation:
    """翻数・打点の構造化評価"""
    current_han: int
    potential_han: int
    mangan_reachable: bool
    points_if_agari: int
    
    def to_dict(self) -> Dict:
        return {
            "current": self.current_han,
            "potential": self.potential_han,
            "mangan_reachable": self.mangan_reachable,
            "points_if_agari": self.points_if_agari
        }


@dataclass
class TileScore:
    """個別牌のスコアリング結果"""
    tile_id: str
    total_score: float
    danger: float
    ukeire: int
    is_isolated: bool
    components: Dict[str, float]  # スコア内訳


@dataclass
class StrategyResult:
    """方向性2の構造化出力"""
    tile: str              # 推奨切り牌（具体的な牌ID）
    judgment: str
    strategy_type: str     # SPEED_PUSH / VALUE_PUSH / DEFENSIVE_FOLD / BALANCED_SHAPE / RISKY_PUSH
    scores: Dict[str, float]
    triggered_rules: List[str]
    han_evaluation: Dict[str, Any]
    reasoning: str
    confidence: float      # 0.0-1.0
    tile_scores: List[Dict] = field(default_factory=list)  # 上位3牌のスコア詳細


class StrategyJudge:
    """
    Phase 1: 状況分析 → 戦略タグ判定（カタログルール + ヒューリスティック）
    Phase 2: 手牌スコアリング → 具体的打牌選択（戦略タグ別重み関数）
    Phase 3: 整合性検証 → 矛盾検出 + Confidence補正
    """
    
    def __init__(self, catalog_path: str = "server/rules/strategy_catalog.json"):
        self.catalog = self._load_catalog(catalog_path)
        
    def _load_catalog(self, path: str) -> List[Dict]:
        if not os.path.exists(path):
            logger.warning(f"Strategy catalog not found: {path}. Using empty.")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def judge(self, context: Dict) -> StrategyResult:
        """盤面コンテキストから戦略判断 + 具体的打牌を出力"""
        
        # ═══ Phase 1: 戦略タグ判定 ═══
        tag, tag_confidence, rule_ids = self._evaluate_strategy_tag(context)
        han_eval = self._evaluate_han(context)
        
        # ═══ Phase 2: 手牌スコアリング ═══
        hand_tiles = context.get("hand_tiles", [])
        if hand_tiles:
            tile_scores = self._score_all_tiles(hand_tiles, tag, context)
            tile_scores.sort(key=lambda ts: ts.total_score, reverse=True)
            best_tile = tile_scores[0].tile_id if tile_scores else "5m"
            top3 = [{"tile": ts.tile_id, "score": round(ts.total_score, 3),
                      "danger": round(ts.danger, 2), "ukeire": ts.ukeire,
                      "isolated": ts.is_isolated} for ts in tile_scores[:3]]
        else:
            best_tile = self._fallback_tile(tag, context)
            top3 = []
        
        # ═══ Phase 3: 整合性検証 + Confidence補正 ═══
        warnings = self._validate_consistency(tag, best_tile, han_eval, context)
        if warnings:
            tag_confidence *= 0.85  # 矛盾あれば信頼度を下げる
        
        # 出力生成
        reasoning = self._build_reasoning(context, tag, rule_ids, han_eval, best_tile)
        judgment = self._build_judgment(context, tag, han_eval, best_tile)
        
        # カタログルールからのスコア集計
        matched = self._filter_rules(context)
        total_atk = sum(r.get("w", {}).get("attack", 0.0) * r.get("priority", 50) for r in matched)
        total_def = sum(r.get("w", {}).get("defense", 0.0) * r.get("priority", 50) for r in matched)
        total_sit = sum(r.get("w", {}).get("situation", 0.0) * r.get("priority", 50) for r in matched)
        total_pri = sum(r.get("priority", 50) for r in matched) or 1
        
        return StrategyResult(
            tile=best_tile,
            judgment=judgment,
            strategy_type=tag,
            scores={
                "attack": round(total_atk / total_pri, 3),
                "defense": round(total_def / total_pri, 3),
                "situation": round(total_sit / total_pri, 3),
            },
            triggered_rules=rule_ids[:5],
            han_evaluation=han_eval.to_dict(),
            reasoning=reasoning,
            confidence=round(min(tag_confidence, 1.0), 2),
            tile_scores=top3,
        )

    # ═══════════════════════════════════════════════
    # Phase 1: 戦略タグ判定
    # ═══════════════════════════════════════════════

    def _evaluate_strategy_tag(self, ctx: Dict) -> Tuple[str, float, List[str]]:
        """入力局面から戦略タグ・信頼度・適用ルールIDを判定"""
        candidates = []
        
        # ── DEFENSIVE_FOLD: 他家リーチ + 低打点 + 現物あり ──
        riichi = ctx.get("riichi", 0)
        if riichi > 0 and ctx.get("current_han", 0) <= 2 and ctx.get("is_genbutsu", False):
            conf = 0.75 + riichi * 0.1  # 2本リーチなら0.95
            if ctx.get("dealer_status", False):
                conf *= CONFIDENCE_ADJUSTMENTS["dealer_bonus"]
            candidates.append(("DEFENSIVE_FOLD", min(conf, 0.98), ["DEF_GENBUTSU_PRIORITY"]))
        
        # ── VALUE_PUSH: 満貫到達可能 + 序盤 ──
        if (ctx.get("potential_han", 0) >= 5 or
            (ctx.get("potential_han", 0) >= 3 and ctx.get("has_yakuhai_pair", False))):
            if ctx.get("turn", 0) <= 12 and riichi <= 1:
                conf = 0.85
                candidates.append(("VALUE_PUSH", conf, ["ATK_MANGAN_YAKUHAI"]))
        
        # ── SPEED_PUSH: 良形 + 受入多 + 中盤以前 ──
        ryanmen = ctx.get("ryanmen_count", 0)
        if ryanmen >= 3 and ctx.get("turn", 0) <= 10 and riichi == 0:
            conf = min(0.8, 0.5 + ryanmen * 0.1)
            if ctx.get("has_4_connected", False):
                conf += 0.1
            candidates.append(("SPEED_PUSH", min(conf, 0.95), ["ATK_SPEED_EARLY"]))
        
        # ── RISKY_PUSH: ラス目 + 終盤 + 聴牌近い ──
        if (ctx.get("rank", 1) == 4 and ctx.get("turn", 0) >= 10 and
            ctx.get("shanten", 6) <= 1):
            conf = 0.70
            candidates.append(("RISKY_PUSH", conf, ["SIT_HONBA_PUSH"]))
        
        # ── カタログルールからの追加候補（phase1_tagを直接使用） ──
        matched = self._filter_rules(ctx)
        for r in matched[:3]:
            tag = r.get("phase1_tag") or self._category_to_tag(r.get("category", "SITUATION"), ctx)
            conf = r.get("confidence", 0.7)
            candidates.append((tag, conf, [r["id"]]))
        
        # 候補がない場合
        if not candidates:
            return "BALANCED_SHAPE", 0.5, []
        
        # 競合解決
        if len(candidates) == 1:
            return candidates[0]
        
        return self._resolve_conflict(candidates, ctx)
    
    def _category_to_tag(self, category: str, ctx: Dict) -> str:
        """カタログのカテゴリを戦略タグに変換"""
        if category == "ATTACK":
            if ctx.get("potential_han", 0) >= 5:
                return "VALUE_PUSH"
            return "SPEED_PUSH"
        elif category == "DEFENSE":
            return "DEFENSIVE_FOLD"
        else:  # SITUATION
            return "BALANCED_SHAPE"
    
    def _resolve_conflict(self, candidates: List[Tuple], ctx: Dict) -> Tuple[str, float, List[str]]:
        """複数候補間の競合を優先度マトリクスで解決"""
        # 最高confidence候補をベースに
        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0]
        
        # 2位との優先度マトリクス比較
        if len(candidates) >= 2:
            second = candidates[1]
            matrix_score = PRIORITY_MATRIX.get(best[0], {}).get(second[0], 0.5)
            
            # マトリクスで2位が勝つ場合
            if matrix_score < 0.5 and second[1] > best[1] * 0.8:
                # ルールIDをマージ
                merged_ids = list(set(second[2] + best[2]))
                return second[0], second[1], merged_ids
        
        return best

    # ═══════════════════════════════════════════════
    # Phase 2: 手牌スコアリング
    # ═══════════════════════════════════════════════

    def _score_all_tiles(self, hand_tiles: List, tag: str, ctx: Dict) -> List[TileScore]:
        """全手牌を戦略タグに応じてスコアリング"""
        from server.utils.mahjong_logic import calculate_danger, estimate_ukeire, analyze_shape
        
        results = []
        gs = ctx.get("_gs")  # GameState参照
        seat = ctx.get("_seat", 0)
        
        # 重複除去（同一牌は1回のみスコアリング）
        scored_ids = set()
        
        for tile in hand_tiles:
            if tile.id in scored_ids:
                continue
            scored_ids.add(tile.id)
            
            # 各要素スコアの計算
            danger = calculate_danger(tile, gs, seat) if gs else 0.2
            
            # 読みエンジンの danger_map による上書き
            reading_danger_map = ctx.get("reading_danger_map", {})
            if tile.id in reading_danger_map:
                reading_d = reading_danger_map[tile.id]
                # 読みの危険度が基本値より高ければ上書き、低ければ平均
                if reading_d > danger:
                    danger = reading_d
                else:
                    danger = (danger + reading_d) / 2
            
            ukeire = estimate_ukeire(hand_tiles, tile) if len(hand_tiles) > 1 else 0
            is_isolated = tile.id in ctx.get("isolated_tiles", [])
            is_dora = tile.is_red
            
            # 戦略タグ別の重み関数
            components = self._calc_tile_components(
                tile, tag, danger, ukeire, is_isolated, is_dora, ctx
            )
            total = sum(components.values())
            
            results.append(TileScore(
                tile_id=tile.id,
                total_score=total,
                danger=danger,
                ukeire=ukeire,
                is_isolated=is_isolated,
                components=components
            ))
        
        return results
    
    def _calc_tile_components(self, tile, tag: str, danger: float,
                               ukeire: int, is_isolated: bool, 
                               is_dora: bool, ctx: Dict) -> Dict[str, float]:
        """戦略タグ別の重み関数で牌スコアの内訳を計算"""
        
        # 高スコア = 切りやすい（切るべき）
        c = {}
        
        if tag == "DEFENSIVE_FOLD":
            # 防御時: 安全度が最重要、ドラ保持は気にしない
            c["safety"] = (1.0 - danger) * 5.0       # 安全牌を強く選好
            c["isolated"] = 1.0 if is_isolated else 0.0
            c["dora_penalty"] = 0.0                    # ドラでも安全なら切る
            c["ukeire_loss"] = 0.0                     # 受入は無視
            
        elif tag == "VALUE_PUSH":
            # 打点重視: ドラ・役牌を保持、孤立牌を切る
            c["isolated"] = 2.0 if is_isolated else 0.0
            c["dora_penalty"] = -3.0 if is_dora else 0.0  # ドラは切らない
            c["safety"] = (1.0 - danger) * 0.5
            c["ukeire_loss"] = ukeire * -0.01          # 受入の維持は副目標
            # 字牌の孤立は最優先で切り
            if tile.suit.value == "z" and is_isolated:
                c["honor_isolated"] = 3.0
            
        elif tag == "SPEED_PUSH":
            # 速度重視: 受入最大化、孤立牌・端牌を切る
            c["ukeire_keep"] = ukeire * -0.05           # 受入の大きい牌は切らない
            c["isolated"] = 2.5 if is_isolated else 0.0  # 孤立牌を切る
            c["safety"] = (1.0 - danger) * 0.3
            c["dora_penalty"] = -1.5 if is_dora else 0.0
            # 端牌(1,9)を切りやすく
            if tile.suit.value != "z" and tile.number in (1, 9):
                c["terminal"] = 1.0
            
        elif tag == "RISKY_PUSH":
            # 全押し: 受入と打点を最優先、安全度は無視
            c["ukeire_keep"] = ukeire * -0.08
            c["isolated"] = 3.0 if is_isolated else 0.0
            c["dora_penalty"] = -4.0 if is_dora else 0.0
            c["safety"] = 0.0  # 安全度完全無視
            if tile.suit.value == "z" and is_isolated:
                c["honor_isolated"] = 4.0
            
        else:  # BALANCED_SHAPE
            # バランス: 全要素を均等に考慮
            c["isolated"] = 1.5 if is_isolated else 0.0
            c["safety"] = (1.0 - danger) * 1.0
            c["dora_penalty"] = -2.0 if is_dora else 0.0
            c["ukeire_loss"] = ukeire * -0.02
            if tile.suit.value == "z" and is_isolated:
                c["honor_isolated"] = 2.0
        
        return {k: round(v, 3) for k, v in c.items()}
    
    def _fallback_tile(self, tag: str, ctx: Dict) -> str:
        """手牌情報がない場合のフォールバック"""
        if tag == "DEFENSIVE_FOLD":
            genbutsu = ctx.get("genbutsu_tiles", [])
            return genbutsu[0] if genbutsu else "安全牌"
        return "5m"

    # ═══════════════════════════════════════════════
    # Phase 3: 整合性検証
    # ═══════════════════════════════════════════════

    def _validate_consistency(self, tag: str, tile: str, 
                               han: HanEvaluation, ctx: Dict) -> List[str]:
        """戦略タグと推奨牌の論理的整合性を検証"""
        warnings = []
        
        # DEFENSIVE_FOLD時に高危険牌を推奨していないか
        # (手牌スコアリングが安全牌を選んでいるはず)
        if tag == "DEFENSIVE_FOLD":
            # 現物がctxにあるのに選ばれていない場合は警告
            genbutsu = ctx.get("genbutsu_tiles", [])
            if genbutsu and tile not in genbutsu:
                warnings.append(f"STRAT_TILE_MISMATCH: 防御戦略下で現物({','.join(genbutsu[:3])})を非選択")
        
        # VALUE_PUSH時に満貫到達可能性
        if tag == "VALUE_PUSH" and not han.mangan_reachable:
            if ctx.get("potential_han", 0) < 3:
                warnings.append("HAN_EVAL_INCONSISTENT: VALUE_PUSH戦略だが潜在翻数<3")
        
        if warnings:
            logger.info(f"Strategy validation warnings: {warnings}")
        
        return warnings

    # ═══════════════════════════════════════════════
    # カタログルール評価（従来ロジック）
    # ═══════════════════════════════════════════════

    def _filter_rules(self, ctx: Dict) -> List[Dict]:
        res = []
        for r in self.catalog:
            if "id" not in r:
                continue  # セクションマーカー等はスキップ
            cond = r.get("cond", {})
            if self._eval_conditions(cond, ctx):
                res.append(r)
        res.sort(key=lambda r: r.get("priority", 50), reverse=True)
        return res
    
    def _eval_conditions(self, cond: Dict, ctx: Dict) -> bool:
        """AND条件でルール適合を判定"""
        if cond.get("turn_min", 0) > ctx.get("turn", 0):
            return False
        if cond.get("turn_max", 24) < ctx.get("turn", 0):
            return False
        if cond.get("riichi_min", 0) > ctx.get("riichi", 0):
            return False
        if ctx.get("score_diff", 0) < cond.get("score_min", -99999):
            return False
        if ctx.get("score_diff", 0) > cond.get("score_max", 99999):
            return False
        if "rank" in cond and cond["rank"] != ctx.get("rank", 1):
            return False
        if "rank_min" in cond and ctx.get("rank", 1) < cond["rank_min"]:
            return False
        if "honba_min" in cond and cond["honba_min"] > ctx.get("honba", 0):
            return False
        if "dealer" in cond and cond["dealer"] != ctx.get("dealer_status", False):
            return False
        if "han_min" in cond and ctx.get("current_han", 0) < cond["han_min"]:
            return False
        if "han_max" in cond and ctx.get("current_han", 0) > cond["han_max"]:
            return False
            
        # Phase 3 / Direction 2 追加条件
        if "shanten_min" in cond and ctx.get("shanten", 6) < cond["shanten_min"]:
            return False
        if "shanten_max" in cond and ctx.get("shanten", 6) > cond["shanten_max"]:
            return False
        if "is_endgame" in cond and cond["is_endgame"] != ctx.get("is_endgame", False):
            return False
        if "score_diff_min" in cond and ctx.get("score_diff", 0) < cond["score_diff_min"]:
            return False
        if "ryanmen_min" in cond and ctx.get("ryanmen_count", 0) < cond["ryanmen_min"]:
            return False
        if "potential_han_min" in cond and ctx.get("potential_han", 0) < cond["potential_han_min"]:
            return False
        if "furiten_type" in cond and cond["furiten_type"] != ctx.get("furiten_type"):
            return False
        if "furiten_full" in cond and cond["furiten_full"] != ctx.get("furiten_full", False):
            return False
        if "has_furiten_safe" in cond and cond["has_furiten_safe"] != ctx.get("has_furiten_safe", False):
            return False
            
        if "reading_flag" in cond and cond["reading_flag"] not in ctx.get("reading_override_flags", []):
            return False
        if "has_override_flags" in cond and cond["has_override_flags"] != (len(ctx.get("reading_override_flags", [])) > 0):
            return False
        if "paradigm" in cond and cond["paradigm"] != ctx.get("paradigm_primary"):
            return False
            
        # 候補牌固有フラグ (Phase1用なので簡略化、存在しなければFalse扱い)
        if "candidate_is_one_chance" in cond and cond["candidate_is_one_chance"] != ctx.get("candidate_is_one_chance", False):
            return False
        if "candidate_is_aidayonken" in cond and cond["candidate_is_aidayonken"] != ctx.get("candidate_is_aidayonken", False):
            return False
        if "candidate_is_anko_suji" in cond and cond["candidate_is_anko_suji"] != ctx.get("candidate_is_anko_suji", False):
            return False
        if "candidate_is_riichi_ura_suji" in cond and cond["candidate_is_riichi_ura_suji"] != ctx.get("candidate_is_riichi_ura_suji", False):
            return False
        if "candidate_suit_5_in_early_pond" in cond and cond["candidate_suit_5_in_early_pond"] != ctx.get("candidate_suit_5_in_early_pond", False):
            return False
        if "candidate_is_19" in cond and cond["candidate_is_19"] != ctx.get("candidate_is_19", False):
            return False
        if "candidate_is_not_genbutsu" in cond and cond["candidate_is_not_genbutsu"] != ctx.get("candidate_is_not_genbutsu", False):
            return False

        return True

    # ═══════════════════════════════════════════════
    # 翻数評価 + 出力生成
    # ═══════════════════════════════════════════════

    def _evaluate_han(self, ctx: Dict) -> HanEvaluation:
        current = ctx.get("current_han", 0)
        potential = ctx.get("potential_han", current)
        mangan = potential >= 5 or (potential >= 3 and ctx.get("fu", 30) >= 60)
        points = HAN_TO_POINTS.get(min(potential, 13), 1000) if potential > 0 else 0
        if ctx.get("dealer_status", False) and points > 0:
            points = int(points * 1.5)
        return HanEvaluation(current, potential, mangan, points)
    
    def _build_reasoning(self, ctx: Dict, tag: str, rule_ids: List[str],
                          han: HanEvaluation, tile: str) -> str:
        parts = []
        
        # 戦略タグの日本語説明
        tag_names = {
            "SPEED_PUSH": "速度攻め",
            "VALUE_PUSH": "打点攻め", 
            "DEFENSIVE_FOLD": "守備的オリ",
            "BALANCED_SHAPE": "攻防バランス",
            "RISKY_PUSH": "全押し",
        }
        parts.append(f"戦略: {tag_names.get(tag, tag)}")
        parts.append(f"推奨打牌: {tile}")
        
        if han.current_han > 0:
            parts.append(f"現在{han.current_han}翻")
            if han.mangan_reachable:
                parts.append(f"→{han.potential_han}翻で満貫({han.points_if_agari}点)到達可能")
        
        # 適用ルール
        if rule_ids:
            matched = [r for r in self.catalog if r.get("id") in rule_ids]
            if matched:
                parts.append(f"根拠: {matched[0].get('intent', '不明')}")
                ref = matched[0].get("reference", "")
                if ref:
                    parts.append(f"参照: {ref}")
        
        return "。".join(parts)
    
    def _build_judgment(self, ctx: Dict, tag: str, han: HanEvaluation, tile: str) -> str:
        turn = ctx.get('turn', 1)
        base = f"巡目{turn}"
        
        if tag == "VALUE_PUSH":
            if han.mangan_reachable:
                return f"{base}・{han.potential_han}翻({han.points_if_agari}点)到達可能→{tile}切りで打点維持"
            return f"{base}・打点重視→{tile}切りで役構成を維持"
        elif tag == "SPEED_PUSH":
            return f"{base}・速度攻め→{tile}切りで受入最大化"
        elif tag == "DEFENSIVE_FOLD":
            riichi = ctx.get('riichi', 0)
            if riichi > 0:
                return f"{base}・他家{riichi}本リーチ→{tile}切り(安全牌)"
            return f"{base}・守り優先→{tile}切りで放銃回避"
        elif tag == "RISKY_PUSH":
            return f"{base}・ラス目全押し→{tile}切りで和了最優先"
        else:
            return f"{base}・攻防バランス→{tile}切りで形状改良"
