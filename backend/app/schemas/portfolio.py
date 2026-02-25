from pydantic import BaseModel
from typing import List, Optional


class HoldingResponse(BaseModel):
    ticker: str
    shares: float
    cost_basis: float


class PositionResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    open_price: Optional[float] = None
    risk_range_low: Optional[float] = None
    risk_range_high: Optional[float] = None
    shares: float


class PortfolioResponse(BaseModel):
    total_value: float
    initial_value: float
    percent_change: float
    positions: List[PositionResponse]
