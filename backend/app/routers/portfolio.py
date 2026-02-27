from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pynamodb.exceptions import DoesNotExist
from datetime import datetime, timezone

from app.core.dependencies import get_current_active_user
from app.models.portfolio import Portfolio, HoldingMap
from app.models.etf import ETF
from app.schemas.portfolio import PortfolioResponse, PositionResponse, UploadResponse, UploadHoldingResponse
from app.schemas.etf import ErrorResponse
from app.services.csv_service import parse_fidelity_csv
from app.models.trading_rules import TradingRules, DEFAULT_MAX_POSITION_PCT
from app.services.recommendation_service import compute_recommendation

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
    except DoesNotExist:
        max_position_pct = DEFAULT_MAX_POSITION_PCT
    except Exception:
        max_position_pct = DEFAULT_MAX_POSITION_PCT

    # Compute recommendations
    for pos in positions:
        if (
            pos.current_price is not None
            and pos.risk_range_low is not None
            and pos.risk_range_high is not None
            and pos.risk_range_high - pos.risk_range_low > 0
            and total_value > 0
        ):
            position_value = pos.current_price * pos.shares
            position_weight = (position_value / total_value) * 100
            pos.recommendation = compute_recommendation(
                current_price=pos.current_price,
                risk_range_low=pos.risk_range_low,
                risk_range_high=pos.risk_range_high,
                position_weight=position_weight,
                max_position_pct=max_position_pct,
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
        portfolio.updated_at = datetime.now(timezone.utc)
        portfolio.save()
    except DoesNotExist:
        portfolio = Portfolio(
            user_id=user_id,
            holdings=holdings,
            initial_value=parsed.initial_value,
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
        positions=[
            UploadHoldingResponse(
                ticker=h.ticker,
                quantity=h.quantity,
                cost_basis=h.cost_basis,
            )
            for h in parsed.holdings
        ],
    )
