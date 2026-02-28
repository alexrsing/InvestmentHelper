from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    ticker: str
    action: Literal["accepted", "declined"]
    shares: float = Field(gt=0)
    signal: Literal["Buy", "Sell"]


class TradeResponse(BaseModel):
    ticker: str
    signal: str
    action: str
    shares: float
    price: float
    position_before: float
    position_after: float
    cash_before: float
    cash_after: float
    date: str
    created_at: datetime


class DecisionStatusResponse(BaseModel):
    action: str
    shares: float
    date: str


class TradeHistoryItem(BaseModel):
    ticker: str
    signal: str
    action: str
    shares: float
    price: float
    position_before: float
    position_after: float
    cash_before: float
    cash_after: float
    date: str
    created_at: datetime


class TradeHistoryResponse(BaseModel):
    trades: List[TradeHistoryItem]
