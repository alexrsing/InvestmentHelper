import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from app.services.research.research_service import ResearchService
from app.services.research.provider import ResearchResult


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.research_ticker = AsyncMock(
        return_value=ResearchResult(sentiment="Bullish", summary="Positive outlook.")
    )
    return provider


@pytest.fixture
def service(mock_provider):
    return ResearchService(provider=mock_provider, expiry_hours=24)


def _make_position(ticker, signal, current_price=100.0, name="Test ETF",
                    risk_range_low=95.0, risk_range_high=115.0):
    return {
        "ticker": ticker,
        "signal": signal,
        "current_price": current_price,
        "name": name,
        "risk_range_low": risk_range_low,
        "risk_range_high": risk_range_high,
    }


@pytest.mark.asyncio
async def test_research_filters_to_buy_sell(service, mock_provider):
    positions = [
        _make_position("XLK", "Buy"),
        _make_position("XLE", "Sell"),
        _make_position("SPY", "Hold"),
        _make_position("QQQ", "Stay"),
    ]

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_model.return_value.save = MagicMock()
        results = await service.research_positions("user-1", positions)

    assert len(results) == 2
    assert mock_provider.research_ticker.call_count == 2
    tickers_researched = [call.kwargs["ticker"] for call in mock_provider.research_ticker.call_args_list]
    assert "XLK" in tickers_researched
    assert "XLE" in tickers_researched


@pytest.mark.asyncio
async def test_research_saves_to_dynamo(service, mock_provider):
    positions = [_make_position("XLK", "Buy")]

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_instance = MagicMock()
        mock_model.return_value = mock_instance
        await service.research_positions("user-1", positions)

    mock_instance.save.assert_called_once()


@pytest.mark.asyncio
async def test_research_returns_results(service, mock_provider):
    positions = [_make_position("XLK", "Buy")]

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_model.return_value.save = MagicMock()
        results = await service.research_positions("user-1", positions)

    assert len(results) == 1
    assert results[0]["ticker"] == "XLK"
    assert results[0]["sentiment"] == "Bullish"
    assert results[0]["summary"] == "Positive outlook."


@pytest.mark.asyncio
async def test_get_cached_research_filters_expired(service):
    now = datetime.now(timezone.utc)
    fresh = MagicMock()
    fresh.ticker = "XLK"
    fresh.sentiment = "Bullish"
    fresh.summary = "Fresh research."
    fresh.researched_at = now - timedelta(hours=2)

    stale = MagicMock()
    stale.ticker = "XLE"
    stale.sentiment = "Bearish"
    stale.summary = "Stale research."
    stale.researched_at = now - timedelta(hours=25)

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_model.query.return_value = [fresh, stale]
        results = service.get_cached_research("user-1")

    assert len(results) == 1
    assert results["XLK"]["sentiment"] == "Bullish"
    assert "XLE" not in results
