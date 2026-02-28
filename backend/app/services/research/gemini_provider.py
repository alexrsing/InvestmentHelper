import json
import re
from google import genai
from google.genai import types

from app.services.research.provider import ResearchProvider, ResearchResult


RESEARCH_SYSTEM_PROMPT = """You are a financial research assistant. For the given ETF, search for:
1. Recent news about the ETF and its sector (last 1-2 weeks)
2. Upcoming earnings dates, dividend dates, or rebalancing events
3. Broad market or macroeconomic conditions that could affect this ETF

Based on your findings, respond with a JSON object:
{
  "sentiment": "Bullish" | "Bearish" | "Neutral",
  "summary": "1-2 sentence summary of key findings that could affect the price"
}

Rules:
- "Bullish" means news/events support price going up
- "Bearish" means news/events suggest price pressure or downside risk
- "Neutral" means no significant news or mixed signals
- Keep the summary concise and actionable for a trader
- Focus on facts, not speculation
- Always respond with valid JSON only, no other text
"""


class GeminiResearchProvider(ResearchProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def research_ticker(
        self,
        ticker: str,
        name: str,
        signal: str,
        current_price: float,
        risk_range_low: float,
        risk_range_high: float,
    ) -> ResearchResult:
        prompt = (
            f"Research ETF: {ticker} ({name})\n"
            f"Current price: ${current_price:.2f}\n"
            f"Risk range: ${risk_range_low:.2f} - ${risk_range_high:.2f}\n"
            f"Current mechanical signal: {signal}\n\n"
            f"Search for recent news, upcoming events, and macro conditions "
            f"that could affect this ETF's price."
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=RESEARCH_SYSTEM_PROMPT,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            return self._parse_response(response.text)
        except Exception as e:
            print(f"Gemini research error for {ticker}: {e}")
            return ResearchResult(
                sentiment="Neutral",
                summary=f"Research unavailable for {ticker}.",
            )

    def _parse_response(self, text: str) -> ResearchResult:
        if not text:
            return ResearchResult(sentiment="Neutral", summary="No research data returned.")
        try:
            # Strip markdown code fences if present (e.g. ```json\n{...}\n```)
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            data = json.loads(cleaned)
            sentiment = data.get("sentiment", "Neutral")
            if sentiment not in ("Bullish", "Bearish", "Neutral"):
                sentiment = "Neutral"
            summary = data.get("summary", "No summary available.")
            return ResearchResult(sentiment=sentiment, summary=summary)
        except (json.JSONDecodeError, KeyError, TypeError):
            print(f"Failed to parse Gemini response: {text[:500]}")
            return ResearchResult(
                sentiment="Neutral",
                summary="Unable to parse research results.",
            )
