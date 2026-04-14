# server/core/explanation/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class TechnicalFactor(BaseModel):
    """層1: 技術的要因（数値根拠）"""
    code: str
    label: str
    value: Optional[float] = None
    detail: Optional[str] = None

class StrategicFactor(BaseModel):
    """層2: 戦略的要因（局面判断）"""
    code: str
    label: str
    context: str
    priority: float  # 0.0〜1.0: 重要度

class NaturalSummary(BaseModel):
    """層3: 自然言語統合（要約）"""
    one_liner: str
    full_paragraph: str

class CompleteExplanation(BaseModel):
    """包括的説明出力（単一構造）"""
    recommended_move: str
    technical_factors: List[TechnicalFactor] = Field(default_factory=list)
    strategic_factors: List[StrategicFactor] = Field(default_factory=list)
    summary: NaturalSummary
    confidence_score: float
    alternative_moves: List[Dict[str, Any]] = Field(default_factory=list)
