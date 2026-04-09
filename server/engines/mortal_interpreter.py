"""
server/engines/mortal_interpreter.py
方向性3: Mortal解釈ルールエンジン

AI行動からの定石パターン逆推論と専門的説明の生成。
3カテゴリの逆推論:
  1. 牌効率パターン (RYANMEN_PRIORITY, NAKA_FUKURE, etc.)
  2. 打点評価パターン (MANGAN_YAKUHAI, DORA_KEEP, etc.)
  3. 防御パターン (GENBUTSU_DEFENSE, KABE_SAFETY, etc.)
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class DefaultDict(dict):
    """format_map用: 未定義キーを'{key}'として返す安全辞書"""
    def __missing__(self, key):
        return f"{{{key}}}"

@dataclass
class InterpretResult:
    """方向性3の構造化出力"""
    tile: str
    text: str                 # 言語化された解説文
    confidence: str           # "high" / "medium" / "low"
    confidence_score: float   # 0.0-1.0 の定量値
    intents: List[str]        # 推定された戦術意図
    matched_rules: List[str]  # マッチしたパターンID
    category: str             # マッチカテゴリ (EFFICIENCY / VALUE / DEFENSE)
    han_context: Dict[str, Any]  # 翻数に関する文脈情報

class MortalInterpreter:
    """
    Mortal出力の戦術的逆推論エンジン
    
    AIが選択した切り牌から、その背後にある戦術的意図を
    ルールベースで逆推論し、専門的な日本語解説を生成する。
    """
    
    def __init__(self, catalog_path: str = "server/rules/interpret_catalog.json"):
        self.catalog = self._load_catalog(catalog_path)
        
    def _load_catalog(self, path: str) -> List[Dict]:
        if not os.path.exists(path):
            logger.warning(f"Interpret catalog not found: {path}. Using empty.")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def interpret(self, ai_tile: str, prob: float, context: Dict) -> InterpretResult:
        """AI推奨手と盤面から意図を逆推論"""
        
        # 全パターンマッチング（スコア付き）
        scored_matches = self._score_all_patterns(ai_tile, prob, context)
        
        # スコア降順でソート
        scored_matches.sort(key=lambda x: x[1], reverse=True)
        
        if not scored_matches:
            return InterpretResult(
                tile=ai_tile,
                text=f"{ai_tile}切り：標準的な牌効率に基づく選択",
                confidence="medium",
                confidence_score=0.4,
                intents=["牌効率最適化"],
                matched_rules=[],
                category="EFFICIENCY",
                han_context={}
            )
        
        # 最高スコアのパターンを採用
        best_rule, best_score = scored_matches[0]
        
        # 解説文の生成
        text = self._render_template(best_rule, ai_tile, prob, context)
        
        # 全マッチから意図を抽出
        all_intents = list({r.get("intent", "不明") for r, _ in scored_matches[:3]})
        
        # confidence算出
        conf_score = self._calc_confidence(prob, best_score, len(scored_matches))
        conf_label = "high" if conf_score > 0.7 else "medium" if conf_score > 0.4 else "low"
        
        # 翻数文脈
        han_ctx = self._extract_han_context(best_rule, context)
        
        return InterpretResult(
            tile=ai_tile,
            text=text,
            confidence=conf_label,
            confidence_score=round(conf_score, 2),
            intents=all_intents,
            matched_rules=[r["id"] for r, _ in scored_matches[:3]],
            category=best_rule.get("category", "EFFICIENCY"),
            han_context=han_ctx
        )

    def _score_all_patterns(self, tile: str, prob: float, ctx: Dict) -> List[tuple]:
        """全パターンをスコアリングしてマッチ度を返す"""
        results = []
        for rule in self.catalog:
            if "id" not in rule:
                continue  # セクションマーカー等はスキップ
            score = self._calc_match_score(rule, tile, prob, ctx)
            if score > 0:
                results.append((rule, score))
        return results
    
    def _calc_match_score(self, rule: Dict, tile: str, prob: float, ctx: Dict) -> float:
        """個別パターンのマッチスコアを算出 (0.0 = 不適合, 1.0 = 完全適合)"""
        score = 0.0
        
        # 牌のマッチング
        target = rule.get("target", "any")
        if target == "any":
            score += 0.3
        elif target in tile:
            score += 0.5
        else:
            # targetが牌種指定で不一致の場合は不適合
            if target in ("m", "p", "s", "z"):
                return 0.0
        
        # 危険度条件
        danger = ctx.get("danger", "low")
        danger_cond = rule.get("danger_cond", ["low", "med", "high"])
        if danger in danger_cond:
            score += 0.2
        else:
            return 0.0  # 危険度不適合は完全不適合
        
        # カテゴリ別の追加条件
        category = rule.get("category", "EFFICIENCY")
        
        if category == "DEFENSE":
            # 防御パターン: リーチ下でスコアUP
            if ctx.get("riichi", 0) > 0:
                score += 0.3
            # 現物フラグ
            if rule.get("requires_genbutsu") and ctx.get("is_genbutsu"):
                score += 0.4
        
        elif category == "VALUE":
            # 打点パターン: 翻数文脈でスコアUP
            if ctx.get("current_han", 0) >= rule.get("han_min", 0):
                score += 0.2
            if ctx.get("has_yakuhai_pair"):
                score += 0.3
        
        elif category == "EFFICIENCY":
            # 牌効率パターン: 序盤でスコアUP
            turn = ctx.get("turn", 0)
            if turn <= 8:
                score += 0.2
            # shape_trigger による直接形状マッチング
            shape_trigger = rule.get("shape_trigger")
            if shape_trigger:
                if ctx.get(shape_trigger, False):
                    score += 0.5  # 形状トリガー一致 → 高スコア
                else:
                    score *= 0.3  # 形状不一致 → 大幅減点
            else:
                # フォールバック：テンプレート内のキーワードで形状判定
                if ctx.get("has_4_connected") and "4連形" in rule.get("tpl", ""):
                    score += 0.4
                if ctx.get("has_nakabukure") and "中膨れ" in rule.get("tpl", ""):
                    score += 0.4
        
        # 巡目条件
        if "turn_min" in rule and ctx.get("turn", 0) < rule["turn_min"]:
            score *= 0.5
        if "turn_max" in rule and ctx.get("turn", 0) > rule["turn_max"]:
            score *= 0.5
        
        # 優先度によるスケーリング
        score *= rule.get("priority", 50) / 100.0
        
        return score
    
    def _render_template(self, rule: Dict, tile: str, prob: float, ctx: Dict) -> str:
        """テンプレートに変数を埋め込んで解説文を生成"""
        tpl = rule.get("tpl", "{tile}は戦術的選択")
        
        # テンプレート変数の辞書
        variables = {
            "tile": tile,
            "prob": f"{prob*100:.1f}%",
            "turn": str(ctx.get("turn", "?")),
            "han": str(ctx.get("current_han", "?")),
            "potential_han": str(ctx.get("potential_han", "?")),
            "riichi_count": str(ctx.get("riichi", 0)),
            "required_han": str(ctx.get("required_han", "?")),
            "furiten_tiles": str(ctx.get("furiten_tiles", "")),
        }
        
        try:
            return tpl.format_map(DefaultDict(variables))
        except Exception:
            # 全てのフォールバックが失敗した場合
            return f"{tile}切り：戦術的選択"
    
    def _calc_confidence(self, prob: float, match_score: float, match_count: int) -> float:
        """逆推論の信頼度を定量化"""
        # Mortalの確率が高いほど推論に自信
        prob_factor = min(prob * 1.5, 0.6)
        # マッチスコアが高いほど自信
        match_factor = min(match_score * 0.4, 0.3)
        # 複数パターンが一致すれば補強
        count_bonus = min(match_count * 0.03, 0.1)
        
        return min(prob_factor + match_factor + count_bonus, 1.0)
    
    def _extract_han_context(self, rule: Dict, ctx: Dict) -> Dict:
        """翻数に関連する文脈情報を抽出"""
        result = {}
        if rule.get("category") == "VALUE":
            result["current_han"] = ctx.get("current_han", 0)
            result["potential_han"] = ctx.get("potential_han", 0)
            result["mangan_reachable"] = ctx.get("potential_han", 0) >= 5
        return result
