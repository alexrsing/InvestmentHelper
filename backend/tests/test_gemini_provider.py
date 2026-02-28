import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.research.gemini_provider import GeminiResearchProvider
from app.services.research.provider import ResearchResult


@pytest.fixture
def provider():
    return GeminiResearchProvider(api_key="test-key", model="gemini-2.0-flash")


@pytest.mark.asyncio
async def test_research_ticker_bullish(provider):
    mock_response = MagicMock()
    mock_response.text = '{"sentiment": "Bullish", "summary": "Strong sector momentum and positive earnings outlook."}'

    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert isinstance(result, ResearchResult)
    assert result.sentiment == "Bullish"
    assert "momentum" in result.summary.lower() or len(result.summary) > 0


@pytest.mark.asyncio
async def test_research_ticker_bearish(provider):
    mock_response = MagicMock()
    mock_response.text = '{"sentiment": "Bearish", "summary": "Sector rotation risk and upcoming Fed rate decision."}'

    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert result.sentiment == "Bearish"
    assert len(result.summary) > 0


@pytest.mark.asyncio
async def test_research_ticker_malformed_json(provider):
    mock_response = MagicMock()
    mock_response.text = "This is not JSON at all"

    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert result.sentiment == "Neutral"
    assert "unable" in result.summary.lower() or len(result.summary) > 0


@pytest.mark.asyncio
async def test_research_ticker_api_error(provider):
    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert result.sentiment == "Neutral"
    assert "unavailable" in result.summary.lower() or "error" in result.summary.lower()
