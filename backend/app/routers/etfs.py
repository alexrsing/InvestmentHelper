from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import Optional
from datetime import datetime
from pynamodb.exceptions import DoesNotExist, GetError

from app.core.dependencies import get_current_active_user
from app.schemas.etf import (
    ETFResponse,
    ETFHistoryResponse,
    ETFHistoryItemResponse,
    ErrorResponse
)
from app.models.etf import ETF, ETFHistory

router = APIRouter(
    prefix="/etfs",
    tags=["ETFs"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


@router.get(
    "",
    response_model=list[ETFResponse],
    summary="List all ETFs",
    description="Retrieve all ETFs in the system",
)
async def list_etfs(
    current_user: dict = Depends(get_current_active_user),
):
    try:
        etfs = ETF.scan()
        return [
            ETFResponse(
                ticker=etf.ticker,
                name=etf.name,
                description=etf.description,
                expense_ratio=etf.expense_ratio,
                aum=etf.aum,
                inception_date=etf.inception_date,
                current_price=etf.current_price,
                open_price=etf.open_price,
                risk_range_low=etf.risk_range_low,
                risk_range_high=etf.risk_range_high,
                created_at=etf.created_at,
                updated_at=etf.updated_at,
            )
            for etf in etfs
        ]
    except Exception as e:
        print(f"Error listing ETFs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing ETFs",
        )


@router.get(
    "/{ticker}",
    response_model=ETFResponse,
    summary="Get ETF data",
    description="Retrieve current ETF information including price and metadata"
)
async def get_etf(
    ticker: str = Path(
        ...,
        min_length=1,
        max_length=10,
        pattern="^[A-Za-z]{1,10}$",
        description="ETF ticker symbol"
    ),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get latest ETF data by ticker symbol.

    **Security features:**
    - Requires valid JWT authentication
    - Input validation on ticker format
    - SQL injection prevention through ORM
    - Rate limited per IP address

    **Args:**
        ticker: ETF ticker symbol (e.g., 'SPY', 'QQQ')
        current_user: Authenticated user from JWT token

    **Returns:**
        ETFResponse: ETF data including current price and metadata

    **Raises:**
        HTTPException 401: Invalid or missing authentication
        HTTPException 404: ETF not found
        HTTPException 422: Invalid ticker format
    """
    # Normalize ticker to uppercase
    ticker = ticker.upper()

    try:
        # Fetch ETF from DynamoDB using ORM (prevents injection)
        etf = ETF.get(ticker)

        # Convert to response model (validates output)
        return ETFResponse(
            ticker=etf.ticker,
            name=etf.name,
            description=etf.description,
            expense_ratio=etf.expense_ratio,
            aum=etf.aum,
            inception_date=etf.inception_date,
            current_price=etf.current_price,
            open_price=etf.open_price,
            risk_range_low=etf.risk_range_low,
            risk_range_high=etf.risk_range_high,
            created_at=etf.created_at,
            updated_at=etf.updated_at
        )

    except (DoesNotExist, GetError):
        # Don't expose internal details in error messages
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ETF with ticker '{ticker}' not found"
        )
    except Exception as e:
        # Log the actual error internally (don't expose to client)
        print(f"Error fetching ETF {ticker}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching ETF data"
        )


@router.get(
    "/{ticker}/history",
    response_model=ETFHistoryResponse,
    summary="Get ETF historical data",
    description="Retrieve historical price data for an ETF with optional date range filtering"
)
async def get_etf_history(
    ticker: str = Path(
        ...,
        min_length=1,
        max_length=10,
        pattern="^[A-Za-z]{1,10}$",
        description="ETF ticker symbol"
    ),
    start_date: Optional[str] = Query(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Start date in YYYY-MM-DD format",
        example="2024-01-01"
    ),
    end_date: Optional[str] = Query(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="End date in YYYY-MM-DD format",
        example="2024-12-31"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of records to return"
    ),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get ETF historical price data with optional filtering.

    **Security features:**
    - Requires valid JWT authentication
    - Input validation on all parameters
    - SQL injection prevention through ORM
    - Rate limited per IP address
    - Prevents data exposure beyond authorized limits

    **Args:**
        ticker: ETF ticker symbol
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        limit: Maximum records to return (1-1000)
        current_user: Authenticated user from JWT token

    **Returns:**
        ETFHistoryResponse: Historical price data

    **Raises:**
        HTTPException 401: Invalid or missing authentication
        HTTPException 404: ETF not found
        HTTPException 422: Invalid parameters
    """
    # Normalize ticker
    ticker = ticker.upper()

    # Validate date range if both provided
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be before or equal to end_date"
        )

    try:
        # First verify ETF exists
        try:
            ETF.get(ticker)
        except (DoesNotExist, GetError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ETF with ticker '{ticker}' not found"
            )

        # Query historical data with filters
        # Using DynamoDB query (parameterized, injection-safe)
        if start_date and end_date:
            history_items = ETFHistory.query(
                ticker,
                ETFHistory.date.between(start_date, end_date),
                limit=limit
            )
        elif start_date:
            history_items = ETFHistory.query(
                ticker,
                ETFHistory.date >= start_date,
                limit=limit
            )
        else:
            history_items = ETFHistory.query(
                ticker,
                limit=limit,
                scan_index_forward=False  # Most recent first
            )

        # Convert to response models (validates output)
        history_list = []
        for item in history_items:
            history_list.append(
                ETFHistoryItemResponse(
                    date=item.date,
                    open_price=item.open_price,
                    high_price=item.high_price,
                    low_price=item.low_price,
                    close_price=item.close_price,
                    adjusted_close=item.adjusted_close,
                    volume=item.volume,
                    risk_range_low=getattr(item, "risk_range_low", None),
                    risk_range_high=getattr(item, "risk_range_high", None),
                )
            )

        return ETFHistoryResponse(
            ticker=ticker,
            history=history_list,
            total_records=len(history_list)
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log error internally
        print(f"Error fetching history for {ticker}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching historical data"
        )

