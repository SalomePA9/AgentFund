"""
Insider Transaction Data (SEC EDGAR)

Fetches SEC Form 4 filings to detect insider buying/selling clusters.
Insider buying clusters are strongly predictive and structurally uncorrelated
to price momentum — insiders buy based on private knowledge of fundamentals,
not price trends.

Data source: SEC EDGAR XBRL full-text search (free, no API key required)
Rate limits: 10 requests/second with User-Agent header

Signals produced:
- insider_buy_ratio: Buys / (Buys + Sells) over recent window
- insider_cluster_score: Strength of coordinated insider activity
- insider_net_shares: Net shares purchased (buys - sells)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# SEC requires a User-Agent header identifying the requester
SEC_USER_AGENT = "AgentFund Research contact@agentfund.ai"

# CIK lookup for common tickers (subset — full mapping should be loaded from
# the SEC's company_tickers.json file at startup)
_CIK_CACHE: dict[str, str] = {}


class InsiderTransactionClient:
    """
    Fetches insider transaction data from SEC EDGAR.

    Uses the EDGAR full-text search API to find recent Form 4 filings
    and compute insider activity metrics per symbol.

    Usage::

        client = InsiderTransactionClient()
        data = await client.fetch_insider_signals(["AAPL", "MSFT"], lookback_days=90)
        # data["AAPL"] = {
        #     "buy_count": 5,
        #     "sell_count": 2,
        #     "buy_ratio": 0.71,
        #     "cluster_score": 65.0,
        #     "net_sentiment": 42.0,  # -100 to +100
        # }
    """

    def __init__(self):
        self._cik_cache: dict[str, str] = {}

    async def fetch_insider_signals(
        self,
        symbols: list[str],
        lookback_days: int = 90,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch insider transaction signals for a list of symbols.

        Returns a dict of symbol -> insider metrics.
        """
        results: dict[str, dict[str, Any]] = {}

        # Load CIK mapping if needed
        if not self._cik_cache:
            await self._load_cik_mapping()

        for i, symbol in enumerate(symbols):
            try:
                data = await self._fetch_for_symbol(symbol, lookback_days)
                if data:
                    results[symbol] = data
            except Exception:
                logger.debug(
                    "Failed to fetch insider data for %s", symbol, exc_info=True
                )
            # SEC EDGAR enforces 10 requests/second. Sleep between symbols
            # to stay well under the rate limit and avoid IP bans.
            if i < len(symbols) - 1:
                await asyncio.sleep(0.15)

        logger.info(
            "Insider transactions: fetched data for %d/%d symbols",
            len(results),
            len(symbols),
        )
        return results

    async def _load_cik_mapping(self) -> None:
        """Load ticker → CIK mapping from SEC's company_tickers.json."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": SEC_USER_AGENT},
            ) as client:
                resp = await client.get(
                    "https://www.sec.gov/files/company_tickers.json"
                )
                resp.raise_for_status()
                data = resp.json()

                for entry in data.values():
                    ticker = entry.get("ticker", "").upper()
                    cik = str(entry.get("cik_str", ""))
                    if ticker and cik:
                        self._cik_cache[ticker] = cik.zfill(10)

                logger.info("Loaded %d CIK mappings from SEC", len(self._cik_cache))

        except Exception:
            logger.warning("Failed to load SEC CIK mapping", exc_info=True)

    async def _fetch_for_symbol(
        self, symbol: str, lookback_days: int
    ) -> dict[str, Any] | None:
        """
        Fetch and process insider filings for a single symbol.

        Uses EDGAR's XBRL full-text search to find Form 4 filings,
        then categorises as buy/sell/exercise based on transaction codes.
        """
        cik = self._cik_cache.get(symbol.upper())
        if not cik:
            return None

        date_from = (datetime.utcnow() - timedelta(days=lookback_days)).strftime(
            "%Y-%m-%d"
        )

        try:
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": SEC_USER_AGENT},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            # Parse recent Form 4 filings
            recent_filings = data.get("filings", {}).get("recent", {})
            forms = recent_filings.get("form", [])
            dates = recent_filings.get("filingDate", [])

            primary_docs = recent_filings.get("primaryDocument", [])
            accession_numbers = recent_filings.get("accessionNumber", [])

            buy_count = 0
            sell_count = 0
            filing_count = 0

            filings_to_classify: list[tuple[str, str]] = []

            for form, filing_date in zip(forms, dates):
                if form != "4":
                    continue
                if filing_date < date_from:
                    continue
                filing_count += 1

            # Classify filings by fetching individual Form 4 XML documents.
            # SEC Form 4 XML contains <transactionCode> elements:
            #   P = Open market purchase (buy)
            #   S = Open market sale (sell)
            #   A = Grant/award (neutral — ignore)
            #   M = Exercise of derivative (neutral — ignore)
            #   F = Tax withholding sale (sell — involuntary)
            #   G = Gift (neutral — ignore)
            # We fetch up to 10 recent filings to classify the buy/sell ratio.
            for i, (form, filing_date) in enumerate(zip(forms, dates)):
                if form != "4" or filing_date < date_from:
                    continue
                if i < len(accession_numbers) and i < len(primary_docs):
                    filings_to_classify.append((accession_numbers[i], primary_docs[i]))
                if len(filings_to_classify) >= 10:
                    break

            # Classify each filing via XML parsing (with rate limiting)
            for j, (accession, primary_doc) in enumerate(filings_to_classify):
                if j > 0:
                    await asyncio.sleep(0.15)  # SEC rate limit: 10 req/s
                tx_type = await self._classify_filing(cik, accession, primary_doc)
                if tx_type == "buy":
                    buy_count += 1
                elif tx_type == "sell":
                    sell_count += 1
                # "neutral" filings (grants, exercises) are not counted

            # If NO XML documents were available to classify but we have
            # filings, apply the empirical prior: ~40% of Form 4s are
            # purchases, ~60% are sales (option exercises + dispositions).
            # Do NOT apply this when classification was attempted but all
            # filings were neutral (grants/exercises) — that is a real
            # signal meaning "no meaningful insider buying or selling".
            if (
                filing_count > 0
                and buy_count == 0
                and sell_count == 0
                and not filings_to_classify
            ):
                buy_count = round(filing_count * 0.4)
                sell_count = filing_count - buy_count

            if filing_count == 0:
                return None

            # Approximate buy/sell ratio from filing metadata
            # In practice, ~60% of Form 4s are sells (option exercises + sales)
            # Unusually high filing count relative to baseline = signal
            buy_ratio = buy_count / max(1, buy_count + sell_count)

            # Cluster score: normalised filing count relative to baseline
            # Assume baseline of ~2 filings per quarter for a typical stock
            baseline_filings = max(1, lookback_days / 90 * 2)
            cluster_score = min(100.0, (filing_count / baseline_filings) * 50.0)

            # Convert to -100 to +100 signal
            # High filing activity with buys = positive, sells = negative
            net_sentiment = (buy_ratio - 0.5) * 200  # -100 to +100

            return {
                "buy_count": buy_count,
                "sell_count": sell_count,
                "filing_count": filing_count,
                "buy_ratio": round(buy_ratio, 4),
                "cluster_score": round(cluster_score, 2),
                "net_sentiment": round(net_sentiment, 2),
            }

        except Exception:
            logger.debug(
                "Failed to fetch EDGAR data for %s (CIK=%s)", symbol, cik, exc_info=True
            )
            return None

    async def _classify_filing(self, cik: str, accession: str, primary_doc: str) -> str:
        """
        Classify a Form 4 filing as buy, sell, or neutral by parsing its XML.

        Fetches the filing XML from SEC EDGAR and looks for <transactionCode>
        elements. Transaction codes:
          P = Open market purchase → buy
          S = Open market sale → sell
          F = Tax withholding sale → sell
          A, M, G, J, C, etc. → neutral (grants, exercises, gifts)

        Returns "buy", "sell", or "neutral".
        """
        import re

        accession_clean = accession.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik.lstrip('0')}/{accession_clean}/{primary_doc}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                headers={"User-Agent": SEC_USER_AGENT},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content = resp.text

            # Validate that we received XML, not an HTML error page.
            # Form 4 XML documents contain <ownershipDocument>.
            if "<ownershipDocument" not in content and "<?xml" not in content:
                logger.debug("Filing %s returned non-XML content", accession)
                return "neutral"

            # Parse transactionCode elements from XML
            codes = re.findall(
                r"<transactionCode>\s*([A-Z])\s*</transactionCode>",
                content,
                re.IGNORECASE,
            )

            buys = sum(1 for c in codes if c.upper() == "P")
            sells = sum(1 for c in codes if c.upper() in ("S", "F"))

            if buys > sells:
                return "buy"
            elif sells > buys:
                return "sell"
            elif buys > 0:
                return "buy"
            else:
                return "neutral"

        except Exception:
            logger.debug("Could not classify filing %s", accession)
            return "neutral"
