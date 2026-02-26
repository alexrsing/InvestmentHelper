from pydantic import BaseModel, Field


class TradingRulesResponse(BaseModel):
    max_position_pct: float


class TradingRulesUpdate(BaseModel):
    max_position_pct: float = Field(..., ge=1, le=100)
