from datetime import datetime

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class HoldingResponse(BaseModel):
    ticker: str
    shares: float
    cost_basis: float


class RecommendationResponse(BaseModel):
    signal: str
    shares_to_trade: float
    target_position_value: float
    current_position_value: float
    penetration_depth: float


class ResearchResponse(BaseModel):
    ticker: Optional[str] = None
    sentiment: str
    summary: str
    researched_at: datetime


class PositionResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    open_price: Optional[float] = None
    risk_range_low: Optional[float] = None
    risk_range_high: Optional[float] = None
    shares: float
    recommendation: Optional[RecommendationResponse] = None
    research: Optional[ResearchResponse] = None


class PortfolioResponse(BaseModel):
    total_value: float
    initial_value: float
    percent_change: float
    cash_balance: float
    positions: List[PositionResponse]


class UploadHoldingResponse(BaseModel):
    ticker: str
    quantity: float
    cost_basis: float


class CashUpdateRequest(BaseModel):
    action: Literal["deposit", "withdraw"]
    amount: float = Field(gt=0)


class CashUpdateResponse(BaseModel):
    cash_balance: float


class UploadResponse(BaseModel):
    total_value: float
    initial_value: float
    cash_balance: float
    positions: List[UploadHoldingResponse]
