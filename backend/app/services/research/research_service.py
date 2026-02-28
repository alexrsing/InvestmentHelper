import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from app.models.etf_research import ETFResearch
from app.services.research.provider import ResearchProvider


class ResearchService:
    def __init__(self, provider: ResearchProvider, expiry_hours: int = 24):
        self._provider = provider
        self._expiry_hours = expiry_hours

    async def research_positions(
        self, user_id: str, positions: List[dict]
    ) -> List[dict]:
        actionable = [p for p in positions if p["signal"] in ("Buy", "Sell")]

        tasks = [
            self._research_and_save(user_id, p) for p in actionable
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = []
        for pos, result in zip(actionable, results):
            if isinstance(result, Exception):
                print(f"Research failed for {pos['ticker']}: {result}")
                continue
            output.append(result)
        return output

    async def _research_and_save(self, user_id: str, position: dict) -> dict:
        result = await self._provider.research_ticker(
            ticker=position["ticker"],
            name=position.get("name", ""),
            signal=position["signal"],
            current_price=position["current_price"],
            risk_range_low=position["risk_range_low"],
            risk_range_high=position["risk_range_high"],
        )

        now = datetime.now(timezone.utc)
        record = ETFResearch(
            user_id=user_id,
            ticker=position["ticker"],
            sentiment=result.sentiment,
            summary=result.summary,
            signal_at_research=position["signal"],
            researched_at=now,
        )
        record.save()

        return {
            "ticker": position["ticker"],
            "sentiment": result.sentiment,
            "summary": result.summary,
            "researched_at": now.isoformat(),
        }

    def get_cached_research(self, user_id: str) -> Dict[str, dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._expiry_hours)
        results = {}
        try:
            for item in ETFResearch.query(user_id):
                if item.researched_at >= cutoff:
                    results[item.ticker] = {
                        "sentiment": item.sentiment,
                        "summary": item.summary,
                        "researched_at": item.researched_at.isoformat(),
                    }
        except Exception as e:
            print(f"Error fetching cached research for {user_id}: {e}")
        return results
