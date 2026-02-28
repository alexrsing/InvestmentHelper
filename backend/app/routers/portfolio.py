from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pynamodb.exceptions import DoesNotExist
from datetime import datetime, timezone

from app.core.dependencies import get_current_active_user
from app.models.portfolio import Portfolio, HoldingMap
from app.models.etf import ETF
from app.schemas.portfolio import PortfolioResponse, PositionResponse, RecommendationResponse, ResearchResponse, UploadResponse, UploadHoldingResponse, CashUpdateRequest, CashUpdateResponse
from app.schemas.etf import ErrorResponse
from app.services.csv_service import parse_fidelity_csv
from app.models.trading_rules import TradingRules, DEFAULT_MAX_POSITION_PCT, DEFAULT_MIN_POSITION_PCT
from app.services.recommendation_service import compute_recommendation, PositionRecommendation, apply_cash_cap
from app.services.research.research_service import get_cached_research
from app.core.config import settings

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(current_user: dict = Depends(get_current_active_user)):
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

    positions = []
    total_value = 0.0

    for holding in portfolio.holdings:
        try:
            etf = ETF.get(holding.ticker)
            price = etf.current_price or 0
            position_value = price * holding.shares
            total_value += position_value
            positions.append(
                PositionResponse(
                    ticker=holding.ticker,
                    name=etf.name,
                    current_price=etf.current_price,
                    open_price=getattr(etf, "open_price", None),
                    risk_range_low=getattr(etf, "risk_range_low", None),
                    risk_range_high=getattr(etf, "risk_range_high", None),
                    shares=holding.shares,
                )
            )
        except DoesNotExist:
            positions.append(
                PositionResponse(
                    ticker=holding.ticker,
                    shares=holding.shares,
                )
            )
        except Exception as e:
            print(f"Error fetching ETF {holding.ticker}: {e}")
            positions.append(
                PositionResponse(
                    ticker=holding.ticker,
                    shares=holding.shares,
                )
            )

    # Fetch trading rules for position sizing
    try:
        rules = TradingRules.get(user_id)
        max_position_pct = float(rules.max_position_pct)
        min_position_pct = float(rules.min_position_pct)
    except DoesNotExist:
        max_position_pct = DEFAULT_MAX_POSITION_PCT
        min_position_pct = DEFAULT_MIN_POSITION_PCT
    except Exception as e:
        print(f"Error fetching trading rules for {user_id}: {e}")
        max_position_pct = DEFAULT_MAX_POSITION_PCT
        min_position_pct = DEFAULT_MIN_POSITION_PCT

    # Compute recommendations
    position_recs = []
    for pos in positions:
        if (
            pos.current_price is not None
            and pos.risk_range_low is not None
            and pos.risk_range_high is not None
            and pos.risk_range_high - pos.risk_range_low > 0
            and total_value > 0
        ):
            position_value = pos.current_price * pos.shares
            rec = compute_recommendation(
                current_price=pos.current_price,
                risk_range_low=pos.risk_range_low,
                risk_range_high=pos.risk_range_high,
                current_position_value=position_value,
                portfolio_value=total_value,
                max_position_pct=max_position_pct,
                min_position_pct=min_position_pct,
            )
            position_recs.append(PositionRecommendation(
                ticker=pos.ticker,
                current_price=pos.current_price,
                recommendation=rec,
            ))

    # Apply cash capping to buy recommendations
    cash_balance = float(portfolio.cash_balance or 0)
    capped_recs = apply_cash_cap(position_recs, cash_balance)
    capped_by_ticker = {pr.ticker: pr.recommendation for pr in capped_recs}
    for pos in positions:
        if pos.ticker in capped_by_ticker:
            capped = capped_by_ticker[pos.ticker]
            pos.recommendation = RecommendationResponse(
                signal=capped.signal,
                shares_to_trade=capped.shares_to_trade,
                target_position_value=capped.target_position_value,
                current_position_value=capped.current_position_value,
                penetration_depth=capped.penetration_depth,
            )

    # Attach cached research
    cached = get_cached_research(user_id, settings.RESEARCH_EXPIRY_HOURS)
    for pos in positions:
        if pos.ticker in cached:
            r = cached[pos.ticker]
            pos.research = ResearchResponse(
                sentiment=r["sentiment"],
                summary=r["summary"],
                researched_at=r["researched_at"],
            )

    initial_value = portfolio.initial_value or 0
    percent_change = (
        ((total_value - initial_value) / initial_value * 100)
        if initial_value > 0
        else 0.0
    )

    return PortfolioResponse(
        total_value=total_value,
        initial_value=initial_value,
        percent_change=percent_change,
        cash_balance=cash_balance,
        positions=positions,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_portfolio(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
):
    user_id = current_user["user_id"]

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be a CSV",
        )

    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be UTF-8 encoded text",
        )

    try:
        parsed = parse_fidelity_csv(content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # Build holdings list for DynamoDB
    holdings = [
        HoldingMap(
            ticker=h.ticker,
            shares=h.quantity,
            cost_basis=h.cost_basis,
        )
        for h in parsed.holdings
    ]

    # Upsert portfolio (full replace)
    try:
        portfolio = Portfolio.get(user_id)
        portfolio.holdings = holdings
        portfolio.initial_value = parsed.initial_value
        portfolio.cash_balance = parsed.cash_balance
        portfolio.updated_at = datetime.now(timezone.utc)
        portfolio.save()
    except DoesNotExist:
        portfolio = Portfolio(
            user_id=user_id,
            holdings=holdings,
            initial_value=parsed.initial_value,
            cash_balance=parsed.cash_balance,
        )
        portfolio.save()
    except Exception as e:
        print(f"Error saving portfolio for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving portfolio",
        )

    return UploadResponse(
        total_value=parsed.total_value,
        initial_value=parsed.initial_value,
        cash_balance=parsed.cash_balance,
        positions=[
            UploadHoldingResponse(
                ticker=h.ticker,
                quantity=h.quantity,
                cost_basis=h.cost_basis,
            )
            for h in parsed.holdings
        ],
    )


@router.patch("/cash", response_model=CashUpdateResponse)
async def update_cash(
    request: CashUpdateRequest,
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

    current_cash = float(portfolio.cash_balance or 0)

    if request.action == "deposit":
        new_cash = current_cash + request.amount
    else:
        new_cash = max(0.0, current_cash - request.amount)

    portfolio.cash_balance = new_cash
    portfolio.updated_at = datetime.now(timezone.utc)
    portfolio.save()

    return CashUpdateResponse(cash_balance=new_cash)
