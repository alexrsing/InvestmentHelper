from pydantic import BaseModel, Field, model_validator


class TradingRulesResponse(BaseModel):
    max_position_pct: float
    min_position_pct: float


class TradingRulesUpdate(BaseModel):
    max_position_pct: float = Field(..., ge=1, le=100)
    min_position_pct: float = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def min_less_than_max(self) -> "TradingRulesUpdate":
        if self.min_position_pct > 0 and self.min_position_pct >= self.max_position_pct:
            raise ValueError("Min position size must be less than max position size")
        return self
