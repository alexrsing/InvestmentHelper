from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.core.dependencies import get_current_active_user
from app.core.config import settings
from app.models.portfolio import Portfolio
from app.models.etf import ETF
from app.schemas.portfolio import ResearchResponse
from app.schemas.etf import ErrorResponse
from app.services.recommendation_service import compute_recommendation
from app.services.research.gemini_provider import GeminiResearchProvider
from app.services.research.research_service import ResearchService
from app.models.trading_rules import TradingRules, DEFAULT_MAX_POSITION_PCT, DEFAULT_MIN_POSITION_PCT
from pynamodb.exceptions import DoesNotExist

router = APIRouter(
    prefix="/portfolio",
    tags=["Research"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


def _get_research_service() -> ResearchService:
    provider = GeminiResearchProvider(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
    )
    return ResearchService(
        provider=provider,
        expiry_hours=settings.RESEARCH_EXPIRY_HOURS,
    )


@router.post("/research", response_model=List[ResearchResponse])
async def research_positions(
    current_user: dict = Depends(get_current_active_user),
):
    user_id = current_user["user_id"]

    try:
        portfolio = Portfolio.get(user_id)
    except DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    except Exception as e:
        print(f"Error fetching portfolio for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching portfolio",
        )

    # Compute total value
    total_value = 0.0
    enriched = []
    for holding in portfolio.holdings:
        try:
            etf = ETF.get(holding.ticker)
            price = etf.current_price or 0
            position_value = price * holding.shares
            total_value += position_value
            enriched.append({
                "ticker": holding.ticker,
                "name": etf.name or "",
                "current_price": price,
                "risk_range_low": getattr(etf, "risk_range_low", None),
                "risk_range_high": getattr(etf, "risk_range_high", None),
                "shares": holding.shares,
                "position_value": position_value,
            })
        except Exception:
            continue

    if total_value <= 0:
        return []

    # Fetch trading rules
    try:
        rules = TradingRules.get(user_id)
        max_position_pct = float(rules.max_position_pct)
        min_position_pct = float(rules.min_position_pct)
    except DoesNotExist:
        max_position_pct = DEFAULT_MAX_POSITION_PCT
        min_position_pct = DEFAULT_MIN_POSITION_PCT
    except Exception:
        max_position_pct = DEFAULT_MAX_POSITION_PCT
        min_position_pct = DEFAULT_MIN_POSITION_PCT

    # Compute signals and build research input
    research_input = []
    for pos in enriched:
        if (
            pos["current_price"] > 0
            and pos["risk_range_low"] is not None
            and pos["risk_range_high"] is not None
            and pos["risk_range_high"] - pos["risk_range_low"] > 0
        ):
            rec = compute_recommendation(
                current_price=pos["current_price"],
                risk_range_low=pos["risk_range_low"],
                risk_range_high=pos["risk_range_high"],
                current_position_value=pos["position_value"],
                portfolio_value=total_value,
                max_position_pct=max_position_pct,
                min_position_pct=min_position_pct,
            )
            pos["signal"] = rec.signal
            if rec.signal in ("Buy", "Sell"):
                research_input.append(pos)

    service = _get_research_service()
    try:
        results = await service.research_positions(user_id, research_input)
    except Exception as e:
        print(f"Research error for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during research",
        )

    return [
        ResearchResponse(
            sentiment=r["sentiment"],
            summary=r["summary"],
            researched_at=r["researched_at"],
        )
        for r in results
    ]
