"""
Broker API endpoints.

Handles Alpaca broker connection and status.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from api.auth import get_current_user
from database import get_db
from config import get_settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BrokerConnect(BaseModel):
    """Schema for connecting broker account."""

    api_key: str
    api_secret: str
    paper_mode: bool = True


class BrokerStatus(BaseModel):
    """Schema for broker status response."""

    connected: bool
    paper_mode: bool | None = None
    account_id: str | None = None
    status: str | None = None
    portfolio_value: float | None = None
    cash: float | None = None
    buying_power: float | None = None


class AccountInfo(BaseModel):
    """Schema for full account information."""

    id: str
    status: str
    portfolio_value: float
    cash: float
    buying_power: float
    equity: float
    currency: str
    pattern_day_trader: bool
    paper_mode: bool


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def encrypt_api_key(key: str) -> str:
    """Encrypt API key for storage."""
    # TODO: Implement proper encryption using Fernet
    # For now, return as-is (implement in Week 1.4)
    return key


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key from storage."""
    # TODO: Implement proper decryption
    return encrypted_key


def get_alpaca_client(api_key: str, api_secret: str, paper: bool = True):
    """Create an Alpaca client instance."""
    import alpaca_trade_api as tradeapi

    base_url = (
        "https://paper-api.alpaca.markets"
        if paper
        else "https://api.alpaca.markets"
    )

    return tradeapi.REST(
        key_id=api_key,
        secret_key=api_secret,
        base_url=base_url,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/connect", response_model=BrokerStatus)
async def connect_broker(
    credentials: BrokerConnect,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Connect Alpaca broker account."""
    try:
        # Test connection
        client = get_alpaca_client(
            credentials.api_key,
            credentials.api_secret,
            credentials.paper_mode,
        )
        account = client.get_account()

        # Encrypt and store credentials
        encrypted_key = encrypt_api_key(credentials.api_key)
        encrypted_secret = encrypt_api_key(credentials.api_secret)

        db.table("users").update(
            {
                "alpaca_api_key": encrypted_key,
                "alpaca_api_secret": encrypted_secret,
                "alpaca_paper_mode": credentials.paper_mode,
                "total_capital": float(account.portfolio_value),
            }
        ).eq("id", current_user["id"]).execute()

        return BrokerStatus(
            connected=True,
            paper_mode=credentials.paper_mode,
            account_id=account.id,
            status=account.status,
            portfolio_value=float(account.portfolio_value),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to Alpaca: {str(e)}",
        )


@router.get("/status", response_model=BrokerStatus)
async def get_broker_status(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get broker connection status."""
    api_key = current_user.get("alpaca_api_key")
    api_secret = current_user.get("alpaca_api_secret")

    if not api_key or not api_secret:
        return BrokerStatus(connected=False)

    try:
        paper_mode = current_user.get("alpaca_paper_mode", True)
        client = get_alpaca_client(
            decrypt_api_key(api_key),
            decrypt_api_key(api_secret),
            paper_mode,
        )
        account = client.get_account()

        return BrokerStatus(
            connected=True,
            paper_mode=paper_mode,
            account_id=account.id,
            status=account.status,
            portfolio_value=float(account.portfolio_value),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
        )

    except Exception:
        return BrokerStatus(connected=False)


@router.get("/account", response_model=AccountInfo)
async def get_account_info(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get full Alpaca account information."""
    api_key = current_user.get("alpaca_api_key")
    api_secret = current_user.get("alpaca_api_secret")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Broker not connected",
        )

    try:
        paper_mode = current_user.get("alpaca_paper_mode", True)
        client = get_alpaca_client(
            decrypt_api_key(api_key),
            decrypt_api_key(api_secret),
            paper_mode,
        )
        account = client.get_account()

        return AccountInfo(
            id=account.id,
            status=account.status,
            portfolio_value=float(account.portfolio_value),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            equity=float(account.equity),
            currency=account.currency,
            pattern_day_trader=account.pattern_day_trader,
            paper_mode=paper_mode,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get account info: {str(e)}",
        )


@router.post("/switch-mode", response_model=BrokerStatus)
async def switch_trading_mode(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Toggle between paper and live trading mode."""
    api_key = current_user.get("alpaca_api_key")
    api_secret = current_user.get("alpaca_api_secret")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Broker not connected",
        )

    current_paper_mode = current_user.get("alpaca_paper_mode", True)
    new_paper_mode = not current_paper_mode

    try:
        # Test connection with new mode
        client = get_alpaca_client(
            decrypt_api_key(api_key),
            decrypt_api_key(api_secret),
            new_paper_mode,
        )
        account = client.get_account()

        # Update mode in database
        db.table("users").update(
            {"alpaca_paper_mode": new_paper_mode}
        ).eq("id", current_user["id"]).execute()

        return BrokerStatus(
            connected=True,
            paper_mode=new_paper_mode,
            account_id=account.id,
            status=account.status,
            portfolio_value=float(account.portfolio_value),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to switch mode: {str(e)}",
        )
