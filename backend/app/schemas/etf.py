from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List


class ETFBase(BaseModel):
    """Base ETF schema with common attributes"""
    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        pattern="^[A-Z]{1,10}$",
        description="ETF ticker symbol (uppercase letters only)"
    )

    @field_validator('ticker')
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        """Ensure ticker is uppercase"""
        return v.upper()


class ETFResponse(ETFBase):
    """Response schema for ETF data"""
    name: Optional[str] = None
    description: Optional[str] = None
    expense_ratio: Optional[float] = Field(None, ge=0, le=100, description="Expense ratio as percentage")
    aum: Optional[float] = Field(None, ge=0, description="Assets Under Management in dollars")
    inception_date: Optional[datetime] = None
    current_price: Optional[float] = Field(None, gt=0, description="Current price per share")
    open_price: Optional[float] = Field(None, gt=0, description="Opening price")
    risk_range_low: Optional[float] = Field(None, gt=0, description="Risk range lower bound")
    risk_range_high: Optional[float] = Field(None, gt=0, description="Risk range upper bound")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ETFHistoryItemResponse(BaseModel):
    """Response schema for a single historical data point"""
    date: str = Field(..., description="Date in ISO format")
    open_price: float = Field(..., gt=0)
    high_price: float = Field(..., gt=0)
    low_price: float = Field(..., gt=0)
    close_price: float = Field(..., gt=0)
    adjusted_close: Optional[float] = Field(None, gt=0)
    volume: float = Field(..., ge=0)
    risk_range_low: Optional[float] = Field(None, gt=0, description="Risk range lower bound")
    risk_range_high: Optional[float] = Field(None, gt=0, description="Risk range upper bound")

    @field_validator('high_price')
    @classmethod
    def high_must_be_highest(cls, v: float, info) -> float:
        """Validate that high_price is the highest price"""
        if 'low_price' in info.data and v < info.data['low_price']:
            raise ValueError('high_price must be >= low_price')
        return v


class ETFHistoryResponse(BaseModel):
    """Response schema for ETF historical data"""
    ticker: str
    history: List[ETFHistoryItemResponse]
    total_records: int = Field(..., ge=0)

    class Config:
        from_attributes = True


class ETFHistoryQueryParams(BaseModel):
    """Query parameters for ETF history endpoint"""
    start_date: Optional[str] = Field(
        None,
        description="Start date in YYYY-MM-DD format",
        pattern=r'^\d{4}-\d{2}-\d{2}$'
    )
    end_date: Optional[str] = Field(
        None,
        description="End date in YYYY-MM-DD format",
        pattern=r'^\d{4}-\d{2}-\d{2}$'
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of records to return"
    )

    @field_validator('end_date')
    @classmethod
    def end_after_start(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that end_date is after start_date"""
        if v and 'start_date' in info.data and info.data['start_date']:
            if v < info.data['start_date']:
                raise ValueError('end_date must be after start_date')
        return v


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str
    error_code: Optional[str] = None
