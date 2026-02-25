from fastapi import APIRouter, Depends, HTTPException, status
from pynamodb.exceptions import DoesNotExist

from app.core.dependencies import get_current_active_user
from app.models.portfolio import Portfolio
from app.models.etf import ETF
from app.schemas.portfolio import PortfolioResponse, PositionResponse
from app.schemas.etf import ErrorResponse

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
