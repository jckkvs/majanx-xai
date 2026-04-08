"""
server/engines/mortal_interpreter.py
方向性3: Mortal解釈ルールエンジン - 推奨手の逆推論・戦術言語化
"""
from __future__ import annotations
import json
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class InterpretResult:
    tile: str
    text: str
    confidence: str
    intents: List[str]
    matched_rules: List[str]

class MortalInterpreter:
    """Mortal出力の戦術的逆推論エンジン"""
    
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
        matched = self._match_rules(ai_tile, context)
        
        if not matched:
            return InterpretResult(tile=ai_tile, text="標準的な牌効率選択", confidence="medium",
                                   intents=["牌効率最適化"], matched_rules=[])
                                   
        intents = list({r.get("intent", "不明") for r in matched})
        conf = "high" if prob > 0.4 else "medium" if prob > 0.2 else "low"
        text = matched[0].get("tpl", "{tile}は戦術的選択").format(tile=ai_tile)
        
        return InterpretResult(tile=ai_tile, text=text, confidence=conf, intents=intents,
                               matched_rules=[r["id"] for r in matched[:3]])

    def _match_rules(self, tile: str, ctx: Dict) -> List[Dict]:
        res = []
        for r in self.catalog:
            if (r.get("target", "any") == "any" or r.get("target", "") in tile) and \
               ctx.get("danger", "low") in r.get("danger_cond", ["low", "med", "high"]):
                res.append(r)
        return res
