from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ResearchResult:
    sentiment: str  # "Bullish", "Bearish", "Neutral"
    summary: str


class ResearchProvider(ABC):
    @abstractmethod
    async def research_ticker(
        self,
        ticker: str,
        name: str,
        signal: str,
        current_price: float,
        risk_range_low: float,
        risk_range_high: float,
    ) -> ResearchResult:
        """Research a single ETF ticker and return sentiment + summary."""
