from fastapi import APIRouter, Depends, HTTPException, status
from pynamodb.exceptions import DoesNotExist
from datetime import datetime, timezone

from app.core.dependencies import get_current_active_user
from app.models.trading_rules import TradingRules
from app.schemas.trading_rules import TradingRulesResponse, TradingRulesUpdate
from app.schemas.etf import ErrorResponse

router = APIRouter(
    prefix="/trading-rules",
    tags=["Trading Rules"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


@router.get("", response_model=TradingRulesResponse)
async def get_trading_rules(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["user_id"]

    try:
        rules = TradingRules.get(user_id)
        return TradingRulesResponse(max_position_pct=float(rules.max_position_pct))
    except DoesNotExist:
        # Create default rules for new users
        rules = TradingRules(user_id=user_id, max_position_pct=2.5)
        rules.save()
        return TradingRulesResponse(max_position_pct=2.5)
    except Exception as e:
        print(f"Error fetching trading rules for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching trading rules",
        )


@router.put("", response_model=TradingRulesResponse)
async def update_trading_rules(
    update: TradingRulesUpdate,
    current_user: dict = Depends(get_current_active_user),
):
    user_id = current_user["user_id"]

    try:
        try:
            rules = TradingRules.get(user_id)
            rules.max_position_pct = update.max_position_pct
            rules.updated_at = datetime.now(timezone.utc)
            rules.save()
        except DoesNotExist:
            rules = TradingRules(
                user_id=user_id,
                max_position_pct=update.max_position_pct,
            )
            rules.save()

        return TradingRulesResponse(max_position_pct=update.max_position_pct)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating trading rules for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating trading rules",
        )
