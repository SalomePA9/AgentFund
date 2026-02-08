"""
Macro Data Collection Job

Fetches uncorrelated macro signals and alternative data, stores in the
database, and computes the current MacroRiskOverlay state.

Execution order in the nightly pipeline:
1. market_data_job     — prices, fundamentals
2. sentiment_job       — news/social sentiment
3. >>> macro_data_job  — FRED, VIX, insider, short interest (NEW)
4. factor_scoring_job  — factor scores + sentiment integration
5. strategy_execution_job — strategy execution with macro overlay

This job runs BEFORE factor_scoring and strategy_execution so that
the overlay state is available when strategies execute.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from config import settings
from core.macro_risk_overlay import MacroRiskOverlay
from data.macro.fred import FredClient
from data.macro.volatility_regime import VolatilityRegimeClient
from data.alternative.insider_transactions import InsiderTransactionClient
from data.alternative.short_interest import ShortInterestClient

logger = logging.getLogger(__name__)


async def run_macro_data_job(
    db_client: Any = None,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the full macro data collection and overlay computation.

    Args:
        db_client: Supabase client for database operations.
        symbols: Optional list of symbols for stock-level signals.
                 If None, uses top 200 by market cap from stocks table.

    Returns:
        Job summary dictionary.
    """
    start_time = datetime.utcnow()
    logger.info("Starting macro data collection job")

    summary: dict[str, Any] = {
        "start_time": start_time.isoformat(),
        "fred_fetched": False,
        "vix_fetched": False,
        "insider_fetched": 0,
        "short_interest_fetched": 0,
        "overlay_computed": False,
    }

    # ---------------------------------------------------------------
    # Step 1: Fetch FRED macro data (credit spreads, yield curve)
    # ---------------------------------------------------------------
    fred_data: dict[str, Any] = {}
    fred_client = FredClient(api_key=settings.fred_api_key)
    try:
        fred_data = await fred_client.fetch_all(lookback_days=90)
        summary["fred_fetched"] = bool(fred_data)
        logger.info("FRED data: fetched %d series", len(fred_data))

        # Store in macro_indicators table
        if db_client and fred_data:
            await _store_macro_indicators(db_client, fred_data)

    except Exception:
        logger.warning("Failed to fetch FRED data", exc_info=True)

    # ---------------------------------------------------------------
    # Step 2: Fetch VIX / volatility regime data
    # ---------------------------------------------------------------
    vol_regime_data: dict[str, Any] = {}
    vol_client = VolatilityRegimeClient()
    try:
        vol_regime_data = await vol_client.fetch_regime(lookback_days=120)
        summary["vix_fetched"] = vol_regime_data.get("vix_current") is not None
        logger.info(
            "VIX data: current=%.2f regime=%s",
            vol_regime_data.get("vix_current", 0),
            vol_regime_data.get("regime_label", "unknown"),
        )

        # Store VIX as macro indicator
        if db_client and vol_regime_data.get("vix_current") is not None:
            await _store_vix_indicator(db_client, vol_regime_data)

    except Exception:
        logger.warning("Failed to fetch VIX data", exc_info=True)

    # ---------------------------------------------------------------
    # Step 3: Resolve symbols for stock-level signals
    # ---------------------------------------------------------------
    if symbols is None and db_client:
        symbols = await _get_top_symbols(db_client, limit=200)
    symbols = symbols or []

    # ---------------------------------------------------------------
    # Step 4: Fetch insider transaction data
    # ---------------------------------------------------------------
    insider_data: dict[str, dict[str, Any]] = {}
    if symbols:
        insider_client = InsiderTransactionClient()
        try:
            insider_data = await insider_client.fetch_insider_signals(
                symbols, lookback_days=90
            )
            summary["insider_fetched"] = len(insider_data)
            logger.info("Insider data: fetched for %d symbols", len(insider_data))

            # Store in insider_signals table and update stocks table
            if db_client and insider_data:
                await _store_insider_signals(db_client, insider_data)

        except Exception:
            logger.warning("Failed to fetch insider data", exc_info=True)

    # ---------------------------------------------------------------
    # Step 5: Fetch short interest data
    # ---------------------------------------------------------------
    short_interest_data: dict[str, dict[str, Any]] = {}
    if symbols:
        si_client = ShortInterestClient()
        try:
            short_interest_data = await si_client.fetch_short_interest(
                symbols, batch_size=20
            )
            summary["short_interest_fetched"] = len(short_interest_data)
            logger.info(
                "Short interest data: fetched for %d symbols",
                len(short_interest_data),
            )

            # Store in short_interest table and update stocks table
            if db_client and short_interest_data:
                await _store_short_interest(db_client, short_interest_data)

        except Exception:
            logger.warning("Failed to fetch short interest data", exc_info=True)

    # ---------------------------------------------------------------
    # Step 6: Compute MacroRiskOverlay
    # ---------------------------------------------------------------
    try:
        overlay = MacroRiskOverlay()
        overlay_result = overlay.compute(
            macro_data=fred_data,
            insider_data=insider_data,
            vol_regime_data=vol_regime_data,
        )

        summary["overlay_computed"] = True
        summary["risk_scale_factor"] = overlay_result.risk_scale_factor
        summary["composite_risk_score"] = overlay_result.composite_risk_score
        summary["regime_label"] = overlay_result.regime_label
        summary["warnings"] = overlay_result.warnings

        logger.info(
            "MacroRiskOverlay: scale=%.2f score=%.1f regime=%s",
            overlay_result.risk_scale_factor,
            overlay_result.composite_risk_score,
            overlay_result.regime_label,
        )

        # Store overlay state in database
        if db_client:
            await _store_overlay_state(db_client, overlay_result)

    except Exception:
        logger.warning("Failed to compute macro risk overlay", exc_info=True)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    end_time = datetime.utcnow()
    summary["end_time"] = end_time.isoformat()
    summary["duration_seconds"] = round((end_time - start_time).total_seconds(), 2)

    logger.info("Macro data job complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Database storage helpers
# ---------------------------------------------------------------------------


async def _get_top_symbols(db_client: Any, limit: int = 200) -> list[str]:
    """Get top symbols by market cap from the stocks table."""
    try:
        result = (
            db_client.table("stocks")
            .select("symbol")
            .not_.is_("market_cap", "null")
            .order("market_cap", desc=True)
            .limit(limit)
            .execute()
        )
        return [r["symbol"] for r in result.data if r.get("symbol")]
    except Exception:
        logger.warning("Failed to fetch top symbols", exc_info=True)
        return []


async def _store_macro_indicators(
    db_client: Any, fred_data: dict[str, dict[str, Any]]
) -> None:
    """Store FRED macro indicator values."""
    now = datetime.utcnow().isoformat()
    rows = []

    for name, data in fred_data.items():
        if data.get("current") is None:
            continue
        rows.append(
            {
                "indicator_name": name,
                "source": "fred",
                "value": data["current"],
                "z_score": data.get("z_score"),
                "percentile": data.get("percentile"),
                "rate_of_change": data.get("rate_of_change"),
                "metadata": {"mean": data.get("mean"), "std": data.get("std")},
                "recorded_at": now,
            }
        )

    if rows:
        try:
            db_client.table("macro_indicators").upsert(
                rows,
                on_conflict="indicator_name",
            ).execute()
        except Exception:
            logger.warning("Failed to store macro indicators", exc_info=True)


async def _store_vix_indicator(db_client: Any, vol_data: dict[str, Any]) -> None:
    """Store VIX regime data as a macro indicator."""
    now = datetime.utcnow().isoformat()
    try:
        db_client.table("macro_indicators").upsert(
            {
                "indicator_name": "vix",
                "source": "yahoo_finance",
                "value": vol_data["vix_current"],
                "z_score": vol_data.get("vix_z_score"),
                "percentile": vol_data.get("vix_percentile"),
                "rate_of_change": vol_data.get("vix_rate_of_change"),
                "metadata": {
                    "term_structure": vol_data.get("vix_term_structure"),
                    "regime_label": vol_data.get("regime_label"),
                    "regime_score": vol_data.get("regime_score"),
                    "iv_rv_spread": vol_data.get("iv_rv_spread"),
                },
                "recorded_at": now,
            },
            on_conflict="indicator_name",
        ).execute()
    except Exception:
        logger.warning("Failed to store VIX indicator", exc_info=True)


async def _store_insider_signals(
    db_client: Any, insider_data: dict[str, dict[str, Any]]
) -> None:
    """Store insider signals and update stocks table."""
    now = datetime.utcnow().isoformat()
    rows = []
    stock_updates = []

    for symbol, data in insider_data.items():
        rows.append(
            {
                "symbol": symbol,
                "buy_count": data.get("buy_count", 0),
                "sell_count": data.get("sell_count", 0),
                "filing_count": data.get("filing_count", 0),
                "buy_ratio": data.get("buy_ratio"),
                "cluster_score": data.get("cluster_score"),
                "net_sentiment": data.get("net_sentiment"),
                "recorded_at": now,
            }
        )
        stock_updates.append(
            {
                "symbol": symbol,
                "insider_net_sentiment": data.get("net_sentiment"),
                "insider_cluster_score": data.get("cluster_score"),
            }
        )

    try:
        if rows:
            db_client.table("insider_signals").upsert(
                rows, on_conflict="symbol"
            ).execute()
        if stock_updates:
            db_client.table("stocks").upsert(
                stock_updates, on_conflict="symbol"
            ).execute()
    except Exception:
        logger.warning("Failed to store insider signals", exc_info=True)


async def _store_short_interest(
    db_client: Any, si_data: dict[str, dict[str, Any]]
) -> None:
    """Store short interest and update stocks table."""
    now = datetime.utcnow().isoformat()
    rows = []
    stock_updates = []

    for symbol, data in si_data.items():
        rows.append(
            {
                "symbol": symbol,
                "short_pct_float": data.get("short_pct_float"),
                "shares_short": data.get("shares_short"),
                "short_ratio": data.get("short_ratio"),
                "short_interest_score": data.get("short_interest_score"),
                "recorded_at": now,
            }
        )
        stock_updates.append(
            {
                "symbol": symbol,
                "short_pct_float": data.get("short_pct_float"),
                "short_interest_score": data.get("short_interest_score"),
            }
        )

    try:
        if rows:
            db_client.table("short_interest").upsert(
                rows, on_conflict="symbol"
            ).execute()
        if stock_updates:
            db_client.table("stocks").upsert(
                stock_updates, on_conflict="symbol"
            ).execute()
    except Exception:
        logger.warning("Failed to store short interest", exc_info=True)


async def _store_overlay_state(db_client: Any, result: Any) -> None:
    """Store the overlay computation result for audit."""
    try:
        snapshot = result.snapshot
        db_client.table("macro_risk_overlay_state").insert(
            {
                "risk_scale_factor": result.risk_scale_factor,
                "composite_risk_score": result.composite_risk_score,
                "regime_label": result.regime_label,
                "credit_spread_signal": (
                    snapshot.credit_spread_signal if snapshot else None
                ),
                "vol_regime_signal": (snapshot.vol_regime_signal if snapshot else None),
                "yield_curve_signal": (
                    snapshot.yield_curve_signal if snapshot else None
                ),
                "seasonality_signal": (
                    snapshot.seasonality_signal if snapshot else None
                ),
                "insider_breadth_signal": (
                    snapshot.insider_breadth_signal if snapshot else None
                ),
                "warnings": result.warnings,
                "computed_at": datetime.utcnow().isoformat(),
            }
        ).execute()
    except Exception:
        logger.warning("Failed to store overlay state", exc_info=True)
