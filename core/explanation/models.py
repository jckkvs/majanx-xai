# core/explanation/models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class TechnicalFactor(BaseModel):
    """層1: 技術的要因（数値根拠・牌理）"""
    code: str = Field(..., description="識別子 (例: shanten_down, anzen, efficiency)")
    label: str = Field(..., description="日本語ラベル")
    value: Optional[float] = Field(None, description="数値指標（向聴数変化、安全度スコア等）")
    detail: Optional[str] = Field(None, description="補足説明")

class StrategicFactor(BaseModel):
    """層2: 戦略的要因（局面判断・状況読み）"""
    code: str = Field(..., description="識別子 (例: oya_attack, betaori, comeback)")
    label: str = Field(..., description="日本語ラベル")
    context: str = Field(..., description="適用状況（例: 終盤・点差-8000）")
    priority: float = Field(..., ge=0.0, le=1.0, description="重要度スコア")

class NaturalSummary(BaseModel):
    """層3: 自然言語統合（要約）"""
    one_liner: str = Field(..., description="一行要約（常時表示）")
    full_paragraph: str = Field(..., description="詳細説明（展開表示）")

class CompleteExplanation(BaseModel):
    """包括的説明出力（単一構造・階層化）"""
    recommended_move: str
    technical_factors: List[TechnicalFactor] = Field(default_factory=list)
    strategic_factors: List[StrategicFactor] = Field(default_factory=list)
    summary: NaturalSummary
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    alternative_moves: List[dict] = Field(default_factory=list, description="次点候補と簡易スコア")
