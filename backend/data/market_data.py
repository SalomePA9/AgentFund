"""
Market Data Pipeline
Fetches stock data from yfinance, calculates moving averages, and stores in Supabase.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from database import supabase

logger = logging.getLogger(__name__)


# =============================================================================
# Custom HTTP Session (bypass Yahoo Finance IP blocking)
# =============================================================================

_yf_session: requests.Session | None = None


def _get_yf_session() -> requests.Session:
    """
    Get a shared requests.Session with browser-like headers and
    pre-fetched Yahoo Finance cookies.

    Yahoo Finance blocks requests from cloud/CI IPs (e.g. GitHub Actions)
    based on IP ranges AND default User-Agent strings.  This session:
    1. Uses realistic browser headers (including Sec-Fetch-* headers)
    2. Pre-warms cookies by visiting fc.yahoo.com (Yahoo's cookie endpoint)
    3. Pre-fetches a crumb token needed for authenticated API calls
    4. Is reused across all requests to maintain cookie state
    """
    global _yf_session
    if _yf_session is not None:
        return _yf_session

    session = requests.Session()

    # Support proxy via environment variable
    proxy = os.environ.get("YF_PROXY") or os.environ.get("HTTPS_PROXY")
    if proxy:
        session.proxies = {"https": proxy, "http": proxy}
        logger.info(f"Using proxy for Yahoo Finance: {proxy[:20]}...")

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
    )

    # Pre-warm: fetch Yahoo Finance cookie (fc.yahoo.com is Yahoo's cookie
    # endpoint that yfinance uses internally)
    try:
        resp = session.get("https://fc.yahoo.com", timeout=10, allow_redirects=True)
        cookie_names = list(session.cookies.keys())
        logger.info(
            f"Yahoo cookie pre-warm: status={resp.status_code}, "
            f"cookies={cookie_names}"
        )
    except Exception as e:
        logger.warning(f"Failed to pre-warm Yahoo session: {e}")

    # Pre-fetch crumb token (required for Yahoo Finance API calls)
    try:
        crumb_resp = session.get(
            "https://query2.finance.yahoo.com/v1/test/getcrumb",
            timeout=10,
        )
        crumb_text = crumb_resp.text[:30] if crumb_resp.text else "empty"
        logger.info(
            f"Yahoo crumb fetch: status={crumb_resp.status_code}, "
            f"crumb={crumb_text}"
        )
    except Exception as e:
        logger.warning(f"Failed to fetch Yahoo crumb: {e}")

    _yf_session = session
    return session


# =============================================================================
# Stock Universe Definition
# =============================================================================

# S&P 500 Components (as of early 2026)
SP500_TICKERS = [
    "AAPL",
    "MSFT",
    "AMZN",
    "NVDA",
    "GOOGL",
    "GOOG",
    "META",
    "BRK.B",
    "UNH",
    "XOM",
    "LLY",
    "JPM",
    "JNJ",
    "V",
    "PG",
    "MA",
    "AVGO",
    "HD",
    "CVX",
    "MRK",
    "ABBV",
    "COST",
    "PEP",
    "KO",
    "ADBE",
    "WMT",
    "MCD",
    "CSCO",
    "CRM",
    "BAC",
    "PFE",
    "TMO",
    "ACN",
    "NFLX",
    "AMD",
    "ABT",
    "LIN",
    "DIS",
    "ORCL",
    "CMCSA",
    "DHR",
    "NKE",
    "VZ",
    "INTC",
    "WFC",
    "PM",
    "TXN",
    "UNP",
    "COP",
    "QCOM",
    "INTU",
    "RTX",
    "BMY",
    "UPS",
    "LOW",
    "SPGI",
    "CAT",
    "HON",
    "NEE",
    "ELV",
    "BA",
    "GE",
    "PLD",
    "AMAT",
    "IBM",
    "DE",
    "AMGN",
    "T",
    "MS",
    "AXP",
    "MDT",
    "GS",
    "BLK",
    "ISRG",
    "SYK",
    "ADI",
    "GILD",
    "BKNG",
    "ADP",
    "VRTX",
    "LMT",
    "SBUX",
    "MDLZ",
    "MMC",
    "TJX",
    "REGN",
    "ETN",
    "CB",
    "CI",
    "MO",
    "LRCX",
    "PGR",
    "ZTS",
    "C",
    "SCHW",
    "PANW",
    "NOW",
    "BSX",
    "CME",
    "SNPS",
    "CVS",
    "EOG",
    "FI",
    "SO",
    "TMUS",
    "SLB",
    "BDX",
    "DUK",
    "MU",
    "ITW",
    "NOC",
    "CDNS",
    "KLAC",
    "APD",
    "AON",
    "SHW",
    "ICE",
    "WM",
    "HUM",
    "FCX",
    "CL",
    "PYPL",
    "MCK",
    "CMG",
    "PNC",
    "EQIX",
    "TGT",
    "ORLY",
    "EMR",
    "USB",
    "MMM",
    "NSC",
    "ROP",
    "MSI",
    "GD",
    "PSX",
    "MPC",
    "MAR",
    "TDG",
    "EL",
    "APH",
    "AIG",
    "PXD",
    "ECL",
    "NXPI",
    "AZO",
    "ADSK",
    "AFL",
    "HES",
    "OXY",
    "TT",
    "CSX",
    "MCHP",
    "SRE",
    "FTNT",
    "GM",
    "PCAR",
    "VLO",
    "AEP",
    "F",
    "CCI",
    "PSA",
    "CARR",
    "DXCM",
    "TEL",
    "KMB",
    "CTAS",
    "NUE",
    "D",
    "HLT",
    "JCI",
    "WELL",
    "DVN",
    "MRNA",
    "MET",
    "AJG",
    "MNST",
    "O",
    "MSCI",
    "IQV",
    "KDP",
    "GWW",
    "ANET",
    "STZ",
    "DOW",
    "AMP",
    "PRU",
    "ALL",
    "KHC",
    "SPG",
    "BK",
    "GIS",
    "EXC",
    "BIIB",
    "FDX",
    "CMI",
    "A",
    "SYY",
    "PAYX",
    "YUM",
    "CTVA",
    "IDXX",
    "PCG",
    "OTIS",
    "ED",
    "DG",
    "FAST",
    "ROST",
    "VRSK",
    "DHI",
    "ON",
    "AME",
    "HAL",
    "APTV",
    "RMD",
    "DLR",
    "EW",
    "CEG",
    "WEC",
    "PPG",
    "CBRE",
    "ODFL",
    "WMB",
    "EA",
    "CPRT",
    "ROK",
    "GEHC",
    "EXR",
    "DD",
    "MTD",
    "XEL",
    "KR",
    "ALB",
    "WST",
    "OKE",
    "ACGL",
    "HIG",
    "KEYS",
    "AWK",
    "BKR",
    "GLW",
    "LHX",
    "IR",
    "DLTR",
    "IT",
    "CDW",
    "ZBH",
    "ANSS",
    "HPQ",
    "VICI",
    "HSY",
    "CAH",
    "LEN",
    "WBD",
    "AVB",
    "PEG",
    "GPN",
    "ILMN",
    "URI",
    "STT",
    "VMC",
    "TSCO",
    "MLM",
    "EBAY",
    "RJF",
    "IFF",
    "ES",
    "NVR",
    "EIX",
    "FTV",
    "CHD",
    "WAB",
    "DFS",
    "DOV",
    "ULTA",
    "PWR",
    "GRMN",
    "MPWR",
    "HWM",
    "ADM",
    "FRC",
    "TRV",
    "XYL",
    "EFX",
    "TROW",
    "BR",
    "BAX",
    "COO",
    "ALGN",
    "EQR",
    "WTW",
    "AEE",
    "FITB",
    "MOH",
    "LUV",
    "PPL",
    "FANG",
    "DAL",
    "MTB",
    "NTRS",
    "ARE",
    "CTRA",
    "INVH",
    "GPC",
    "HPE",
    "TTWO",
    "SBAC",
    "WY",
    "K",
    "CINF",
    "WAT",
    "BRO",
    "MKC",
    "HUBB",
    "TYL",
    "LYB",
    "STE",
    "TRGP",
    "CNC",
    "DRI",
    "CLX",
    "TDY",
    "RF",
    "FE",
    "HOLX",
    "EXPE",
    "VTR",
    "HRL",
    "MAA",
    "IP",
    "BALL",
    "NTAP",
    "PKI",
    "AES",
    "ESS",
    "DTE",
    "ATO",
    "SWKS",
    "IEX",
    "CNP",
    "J",
    "EXPD",
    "ETR",
    "NDAQ",
    "OMC",
    "MRO",
    "NI",
    "COF",
    "CAG",
    "HBAN",
    "JBHT",
    "NRG",
    "KEY",
    "AMCR",
    "AKAM",
    "BBY",
    "TER",
    "CFG",
    "TSN",
    "SJM",
    "CPT",
    "CMS",
    "WRB",
    "ZBRA",
    "LKQ",
    "AVY",
    "KMX",
    "PEAK",
    "DGX",
    "BXP",
    "EPAM",
    "TXT",
    "APA",
    "SNA",
    "POOL",
    "ALLE",
    "PTC",
    "TECH",
    "IRM",
    "VTRS",
    "MGM",
    "CE",
    "L",
    "RE",
    "TPR",
    "CTLT",
    "JKHY",
    "HST",
    "PAYC",
    "BEN",
    "WRK",
    "CHRW",
    "CBOE",
    "CF",
    "BF.B",
    "EVRG",
    "SEDG",
    "CDAY",
    "QRVO",
    "IPG",
    "NWS",
    "NWSA",
    "LNT",
    "KIM",
    "REG",
    "UDR",
    "CZR",
    "PNR",
    "MAS",
    "BWA",
    "FOXA",
    "FOX",
    "EMN",
    "TAP",
    "AAL",
    "WHR",
    "RHI",
    "HAS",
    "SEE",
    "HII",
    "AAP",
    "FRT",
    "WYNN",
    "BIO",
    "NCLH",
    "NWL",
    "AIZ",
    "FFIV",
    "MHK",
    "LUMN",
    "PNW",
    "BBWI",
    "PARA",
    "DXC",
    "IVZ",
    "DISH",
    "VFC",
    "GNRC",
    "CMA",
    "ZION",
    "FMC",
    "DVA",
    "ALK",
    "RCL",
    "CCL",
    "RL",
    "MTCH",
    "XRAY",
    "LW",
    "CPB",
]

# Russell 1000 additional tickers (excluding S&P 500 overlap)
RUSSELL_1000_ADDITIONAL = [
    "SPOT",
    "SQ",
    "COIN",
    "HOOD",
    "PLTR",
    "RBLX",
    "U",
    "DDOG",
    "ZS",
    "CRWD",
    "SNOW",
    "NET",
    "MDB",
    "TEAM",
    "OKTA",
    "ZI",
    "DOCN",
    "CFLT",
    "PATH",
    "APP",
    "GTLB",
    "TWLO",
    "HUBS",
    "VEEV",
    "WDAY",
    "DOCU",
    "ZM",
    "BILL",
    "COUP",
    "DOMO",
    "DUOL",
    "UBER",
    "LYFT",
    "ABNB",
    "DASH",
    "BROS",
    "RIVN",
    "LCID",
    "FSR",
    "POLESTAR",
    "SOFI",
    "UPST",
    "AFRM",
    "LMND",
    "ROOT",
    "OPEN",
    "OPENDOOR",
    "RDFN",
    "Z",
    "ZG",
    "CVNA",
    "VROOM",
    "CARG",
    "CARS",
    "SAH",
    "AN",
    "LAD",
    "PAG",
    "GPI",
    "ABG",
    "W",
    "ETSY",
    "CHWY",
    "BABA",
    "JD",
    "PDD",
    "BIDU",
    "NIO",
    "XPEV",
    "LI",
    "SE",
    "GRAB",
    "MELI",
    "NU",
    "STNE",
    "PAGS",
    "XP",
    "VTEX",
    "GLBE",
    "MNDY",
    "TTD",
    "PUBM",
    "MGNI",
    "IS",
    "DV",
    "IAS",
    "APPS",
    "DT",
    "S",
    "ESTC",
    "FROG",
    "SUMO",
    "NEWR",
    "SPLK",
    "SMAR",
    "BOX",
    "DBX",
    "FIVN",
    "RNG",
    "BAND",
    "LOGI",
    "HEAR",
    "SONO",
    "GPRO",
    "IRBT",
    "VUZI",
    "IMMR",
    "HIMX",
    "CREE",
    "WOLF",
    "ENPH",
    "SEDG",
    "RUN",
    "NOVA",
    "SPWR",
    "FSLR",
    "ARRY",
    "MAXN",
    "JKS",
    "CSIQ",
    "PLUG",
    "BLDP",
    "BE",
    "FCEL",
    "BLOOM",
    "CHPT",
    "EVGO",
    "BLNK",
    "VLTA",
    "SBE",
    "QS",
    "SLDP",
    "MVST",
    "DCRC",
    "PTRA",
    "LEV",
    "XL",
    "HYLN",
    "GOEV",
    "NKLA",
    "LCID",
    "TSLA",
    "GM",
    "F",
    "TM",
    "HMC",
    "STLA",
    "VWAGY",
    "BMWYY",
    "MBGYY",
    "ARKK",
    "ARKG",
    "ARKW",
    "ARKF",
    "ARKQ",
    "ARKX",
    "PRNT",
    "IZRL",
    "CTRU",
    "ACES",
    "ICLN",
    "TAN",
    "QCLN",
    "FAN",
    "PBW",
    "LIT",
    "REMX",
    "KRBN",
    "CNRG",
    "RNRG",
    "WCLD",
    "SKYY",
    "CLOU",
    "HACK",
    "BUG",
    "CIBR",
    "BOTZ",
    "ROBO",
    "IRBO",
    "ARKQ",
    "IBB",
    "XBI",
    "ARKG",
    "GNOM",
    "LABU",
    "LABD",
    "CURE",
    "PILL",
    "GDXJ",
    "NUGT",
    "JNUG",
    "DUST",
    "JDST",
    "GDX",
    "SIL",
    "SLV",
    "GLD",
    "IAU",
    "SGOL",
    "PHYS",
]


# Combined unique tickers
def get_stock_universe() -> list[str]:
    """Get the complete stock universe (S&P 500 + Russell 1000)."""
    all_tickers = list(set(SP500_TICKERS + RUSSELL_1000_ADDITIONAL))
    # Filter out invalid tickers (with special characters that yfinance doesn't like)
    valid_tickers = [t for t in all_tickers if "." not in t or t.endswith(".B")]
    return sorted(valid_tickers)


# =============================================================================
# Rate Limiting
# =============================================================================


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 2.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0.0

    async def acquire(self):
        """Wait if needed to respect rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_call_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call_time = time.time()


rate_limiter = RateLimiter(calls_per_second=2.0)


# =============================================================================
# Data Fetching
# =============================================================================


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def fetch_stock_data(ticker: str, period: str = "1y") -> dict[str, Any] | None:
    """
    Fetch stock data from yfinance with retry logic.

    Args:
        ticker: Stock ticker symbol
        period: Data period (e.g., "1y", "2y", "5y")

    Returns:
        Dictionary with stock data or None if fetch fails
    """
    try:
        session = _get_yf_session()
        stock = yf.Ticker(ticker, session=session)

        # Get historical data for moving averages
        hist = stock.history(period=period)

        if hist.empty:
            logger.warning(f"No historical data for {ticker}")
            return None

        # Get stock info for fundamentals
        info = stock.info

        # Calculate current price
        current_price = hist["Close"].iloc[-1] if len(hist) > 0 else None

        # Calculate moving averages
        ma_30 = (
            hist["Close"].rolling(window=30).mean().iloc[-1]
            if len(hist) >= 30
            else None
        )
        ma_100 = (
            hist["Close"].rolling(window=100).mean().iloc[-1]
            if len(hist) >= 100
            else None
        )
        ma_200 = (
            hist["Close"].rolling(window=200).mean().iloc[-1]
            if len(hist) >= 200
            else None
        )

        # Calculate ATR (14-day Average True Range) for position sizing
        if len(hist) >= 14:
            high = hist["High"]
            low = hist["Low"]
            close = hist["Close"].shift(1)

            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)

            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.rolling(window=14).mean().iloc[-1]
        else:
            atr = None

        # Calculate price changes
        if len(hist) >= 2:
            prev_close = hist["Close"].iloc[-2]
            change_1d = (
                ((current_price - prev_close) / prev_close) * 100
                if prev_close > 0
                else 0.0
            )
        else:
            change_1d = 0.0

        # Calculate 52-week metrics (None when less than a full year of data)
        high_52w = hist["High"].max() if len(hist) >= 252 else None
        low_52w = hist["Low"].min() if len(hist) >= 252 else None

        # Calculate volume metrics
        avg_volume = hist["Volume"].mean() if len(hist) > 0 else None
        volume_today = hist["Volume"].iloc[-1] if len(hist) > 0 else None

        # Calculate momentum metrics
        momentum_6m = None
        momentum_12m = None
        if len(hist) >= 126:
            price_6m_ago = hist["Close"].iloc[-126]
            momentum_6m = (
                ((current_price - price_6m_ago) / price_6m_ago)
                if price_6m_ago > 0
                else None
            )
        if len(hist) >= 252:
            price_12m_ago = hist["Close"].iloc[-252]
            momentum_12m = (
                ((current_price - price_12m_ago) / price_12m_ago)
                if price_12m_ago > 0
                else None
            )

        # Extract quality metrics
        roe = info.get("returnOnEquity")  # As decimal (0.15 = 15%)
        profit_margin = info.get("profitMargins")  # As decimal
        debt_to_equity = info.get("debtToEquity")  # As ratio (e.g., 50 = 0.5)
        if debt_to_equity:
            debt_to_equity = debt_to_equity / 100  # Convert to decimal

        # Dividend growth (approximate from payout history if available)
        dividend_growth_5y = info.get("fiveYearAvgDividendYield")

        return {
            "symbol": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "price": round(current_price, 2) if current_price else None,
            "change_percent": round(change_1d, 2) if change_1d else 0.0,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "eps": info.get("trailingEps"),
            "beta": info.get("beta"),
            "ma_30": round(ma_30, 2) if ma_30 and not pd.isna(ma_30) else None,
            "ma_100": round(ma_100, 2) if ma_100 and not pd.isna(ma_100) else None,
            "ma_200": round(ma_200, 2) if ma_200 and not pd.isna(ma_200) else None,
            "atr": round(atr, 4) if atr and not pd.isna(atr) else None,
            "high_52w": round(high_52w, 2) if high_52w else None,
            "low_52w": round(low_52w, 2) if low_52w else None,
            "avg_volume": int(avg_volume) if avg_volume else None,
            "volume": int(volume_today) if volume_today else None,
            # Quality metrics for factor scoring
            "roe": round(roe, 4) if roe and not pd.isna(roe) else None,
            "profit_margin": (
                round(profit_margin, 4)
                if profit_margin and not pd.isna(profit_margin)
                else None
            ),
            "debt_to_equity": (
                round(debt_to_equity, 4)
                if debt_to_equity and not pd.isna(debt_to_equity)
                else None
            ),
            # Momentum metrics
            "momentum_6m": (
                round(momentum_6m, 4)
                if momentum_6m and not pd.isna(momentum_6m)
                else None
            ),
            "momentum_12m": (
                round(momentum_12m, 4)
                if momentum_12m and not pd.isna(momentum_12m)
                else None
            ),
            # Dividend growth
            "dividend_growth_5y": (
                round(dividend_growth_5y, 4)
                if dividend_growth_5y and not pd.isna(dividend_growth_5y)
                else None
            ),
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {str(e)}")
        return None


async def fetch_stock_data_async(
    ticker: str, period: str = "1y"
) -> dict[str, Any] | None:
    """Async wrapper for fetch_stock_data with rate limiting."""
    await rate_limiter.acquire()
    return await asyncio.to_thread(fetch_stock_data, ticker, period)


# =============================================================================
# Batch Data Fetching (yf.download)
# =============================================================================


def fetch_batch_price_data(
    tickers: list[str], period: str = "1y"
) -> dict[str, pd.DataFrame]:
    """
    Batch-download OHLCV data for multiple tickers using yf.download().

    This makes far fewer HTTP requests than individual Ticker.history() calls,
    making it much more resilient to Yahoo Finance rate-limiting on shared IPs
    (e.g. GitHub Actions).

    Args:
        tickers: List of ticker symbols
        period: Data period (e.g., "1y")

    Returns:
        Dict mapping ticker -> DataFrame of OHLCV data
    """
    if not tickers:
        return {}

    try:
        session = _get_yf_session()
        data = yf.download(
            tickers,
            period=period,
            group_by="ticker",
            threads=False,
            progress=False,
            session=session,
        )

        if data.empty:
            logger.warning("Batch download returned empty DataFrame")
            return {}

        result = {}

        if len(tickers) == 1:
            # Single ticker returns flat DataFrame (no MultiIndex)
            ticker = tickers[0]
            if isinstance(data.columns, pd.MultiIndex):
                try:
                    ticker_data = data[ticker].dropna(how="all")
                    if not ticker_data.empty:
                        result[ticker] = ticker_data
                except KeyError:
                    pass
            else:
                if not data.empty:
                    result[ticker] = data
        else:
            # Multiple tickers: MultiIndex columns (ticker, field)
            for ticker in tickers:
                try:
                    ticker_data = data[ticker].dropna(how="all")
                    if not ticker_data.empty:
                        result[ticker] = ticker_data
                except (KeyError, AttributeError):
                    continue

        logger.info(
            f"Batch download: {len(result)}/{len(tickers)} tickers returned data"
        )
        return result

    except Exception as e:
        logger.error(f"Batch download error: {e}")
        return {}


def build_stock_record(ticker: str, hist: pd.DataFrame) -> dict[str, Any] | None:
    """
    Build a stock data record from a historical price DataFrame.

    Computes technical indicators (MAs, ATR, momentum) from OHLCV data.
    Fundamental data (P/E, ROE, etc.) is not available from batch downloads
    and will be set to None.

    Args:
        ticker: Stock ticker symbol
        hist: DataFrame with OHLCV columns

    Returns:
        Stock data dictionary or None if data is insufficient
    """
    if hist.empty:
        return None

    try:
        current_price = float(hist["Close"].iloc[-1])
        if pd.isna(current_price) or current_price <= 0:
            return None

        # Moving averages
        ma_30 = (
            hist["Close"].rolling(window=30).mean().iloc[-1]
            if len(hist) >= 30
            else None
        )
        ma_100 = (
            hist["Close"].rolling(window=100).mean().iloc[-1]
            if len(hist) >= 100
            else None
        )
        ma_200 = (
            hist["Close"].rolling(window=200).mean().iloc[-1]
            if len(hist) >= 200
            else None
        )

        # ATR (14-day Average True Range)
        atr = None
        if len(hist) >= 14:
            high = hist["High"]
            low = hist["Low"]
            close = hist["Close"].shift(1)
            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.rolling(window=14).mean().iloc[-1]

        # Daily price change
        change_1d = 0.0
        if len(hist) >= 2:
            prev_close = float(hist["Close"].iloc[-2])
            if prev_close > 0:
                change_1d = ((current_price - prev_close) / prev_close) * 100

        # 52-week metrics
        high_52w = float(hist["High"].max()) if len(hist) >= 252 else None
        low_52w = float(hist["Low"].min()) if len(hist) >= 252 else None

        # Volume
        avg_volume = hist["Volume"].mean() if len(hist) > 0 else None
        volume_today = hist["Volume"].iloc[-1] if len(hist) > 0 else None

        # Momentum
        momentum_6m = None
        momentum_12m = None
        if len(hist) >= 126:
            price_6m_ago = float(hist["Close"].iloc[-126])
            if price_6m_ago > 0:
                momentum_6m = (current_price - price_6m_ago) / price_6m_ago
        if len(hist) >= 252:
            price_12m_ago = float(hist["Close"].iloc[-252])
            if price_12m_ago > 0:
                momentum_12m = (current_price - price_12m_ago) / price_12m_ago

        return {
            "symbol": ticker,
            "name": ticker,
            "sector": None,
            "industry": None,
            "price": round(current_price, 2),
            "change_percent": round(change_1d, 2),
            "market_cap": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "eps": None,
            "beta": None,
            "ma_30": (
                round(float(ma_30), 2)
                if ma_30 is not None and not pd.isna(ma_30)
                else None
            ),
            "ma_100": (
                round(float(ma_100), 2)
                if ma_100 is not None and not pd.isna(ma_100)
                else None
            ),
            "ma_200": (
                round(float(ma_200), 2)
                if ma_200 is not None and not pd.isna(ma_200)
                else None
            ),
            "atr": (
                round(float(atr), 4) if atr is not None and not pd.isna(atr) else None
            ),
            "high_52w": round(high_52w, 2) if high_52w is not None else None,
            "low_52w": round(low_52w, 2) if low_52w is not None else None,
            "avg_volume": (
                int(avg_volume)
                if avg_volume is not None and not pd.isna(avg_volume)
                else None
            ),
            "volume": (
                int(volume_today)
                if volume_today is not None and not pd.isna(volume_today)
                else None
            ),
            "roe": None,
            "profit_margin": None,
            "debt_to_equity": None,
            "momentum_6m": (
                round(float(momentum_6m), 4)
                if momentum_6m is not None and not pd.isna(momentum_6m)
                else None
            ),
            "momentum_12m": (
                round(float(momentum_12m), 4)
                if momentum_12m is not None and not pd.isna(momentum_12m)
                else None
            ),
            "dividend_growth_5y": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error building record for {ticker}: {e}")
        return None


# =============================================================================
# Batch Processing
# =============================================================================


async def process_stock_batch(
    tickers: list[str], batch_size: int = 50, progress_callback: callable = None
) -> tuple[list[dict], list[str]]:
    """
    Process a batch of stocks using yf.download() for efficient batch fetching.

    Uses batch downloads instead of individual ticker requests to minimize
    HTTP requests and avoid Yahoo Finance rate-limiting on shared IPs.

    Args:
        tickers: List of ticker symbols
        batch_size: Number of tickers per batch download
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (successful results, failed tickers)
    """
    results = []
    failed = []
    total = len(tickers)

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]

        # Batch download price data (single HTTP request per batch)
        price_data = await asyncio.to_thread(fetch_batch_price_data, batch, "1y")

        for ticker in batch:
            hist = price_data.get(ticker)
            if hist is None or (isinstance(hist, pd.DataFrame) and hist.empty):
                failed.append(ticker)
                continue

            record = build_stock_record(ticker, hist)
            if record:
                results.append(record)
            else:
                failed.append(ticker)

        # Progress callback
        processed = min(i + batch_size, total)
        if progress_callback:
            progress_callback(processed, total, len(results), len(failed))

        logger.info(
            f"Processed {processed}/{total} stocks ({len(results)} success, {len(failed)} failed)"
        )

        # Delay between batches to respect rate limits
        if i + batch_size < total:
            await asyncio.sleep(2.0)

    return results, failed


# =============================================================================
# Data Validation
# =============================================================================


def validate_stock_data(data: dict) -> tuple[bool, list[str]]:
    """
    Validate stock data for sanity.

    Args:
        data: Stock data dictionary

    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []

    # Required fields
    required = ["symbol", "price"]
    for field in required:
        if not data.get(field):
            issues.append(f"Missing required field: {field}")

    # Price validation
    price = data.get("price")
    if price is not None:
        if price <= 0:
            issues.append(f"Invalid price: {price}")
        if price > 100000:  # Sanity check (e.g., BRK.A excluded)
            issues.append(f"Price unusually high: {price}")

    # Moving average validation
    ma_30 = data.get("ma_30")

    if price and ma_30:
        if abs((price - ma_30) / ma_30) > 1.0:  # More than 100% deviation
            issues.append(f"Large MA30 deviation: price={price}, ma_30={ma_30}")

    # Market cap validation
    market_cap = data.get("market_cap")
    if market_cap is not None and market_cap < 0:
        issues.append(f"Invalid market cap: {market_cap}")

    # P/E ratio validation
    pe_ratio = data.get("pe_ratio")
    if pe_ratio is not None:
        if pe_ratio < 0:
            pass  # Negative P/E is valid for unprofitable companies
        elif pe_ratio > 1000:
            issues.append(f"P/E ratio unusually high: {pe_ratio}")

    return len(issues) == 0, issues


# =============================================================================
# Database Operations
# =============================================================================


async def upsert_stock_data(data: dict) -> bool:
    """
    Insert or update stock data in Supabase.

    Args:
        data: Stock data dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate data first
        is_valid, issues = validate_stock_data(data)
        if not is_valid:
            logger.warning(f"Validation issues for {data.get('symbol')}: {issues}")
            # Still insert but log the issues

        # Upsert to database
        supabase.table("stocks").upsert(data, on_conflict="symbol").execute()

        return True

    except Exception as e:
        logger.error(f"Database error for {data.get('symbol')}: {str(e)}")
        return False


async def upsert_stock_batch(stocks: list[dict]) -> tuple[int, int]:
    """
    Batch upsert stock data to Supabase.

    Args:
        stocks: List of stock data dictionaries

    Returns:
        Tuple of (success_count, failure_count)
    """
    success = 0
    failures = 0

    # Process in smaller batches for database
    batch_size = 100

    for i in range(0, len(stocks), batch_size):
        batch = stocks[i : i + batch_size]

        try:
            # Validate batch
            valid_batch = []
            for stock in batch:
                is_valid, issues = validate_stock_data(stock)
                if is_valid or stock.get("price"):  # Allow partial data if price exists
                    valid_batch.append(stock)
                else:
                    logger.warning(f"Skipping {stock.get('symbol')}: {issues}")
                    failures += 1

            if valid_batch:
                supabase.table("stocks").upsert(
                    valid_batch, on_conflict="symbol"
                ).execute()
                success += len(valid_batch)

        except Exception as e:
            logger.error(f"Batch upsert error: {str(e)}")
            failures += len(batch)

    return success, failures


async def store_price_history(ticker: str, price: float, date: datetime = None) -> bool:
    """Store price in history table."""
    try:
        if date is None:
            date = datetime.utcnow()

        data = {
            "symbol": ticker,
            "price": price,
            "date": date.date().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }

        supabase.table("price_history").upsert(
            data, on_conflict="symbol,date"
        ).execute()

        return True

    except Exception as e:
        logger.error(f"Error storing price history for {ticker}: {str(e)}")
        return False


# =============================================================================
# Full Update Job
# =============================================================================


async def run_market_data_update(
    tickers: list[str] = None, batch_size: int = 50
) -> dict:
    """
    Run full market data update job.

    Args:
        tickers: Optional list of specific tickers (defaults to full universe)
        batch_size: Batch size for processing

    Returns:
        Job summary dictionary
    """
    start_time = datetime.utcnow()
    logger.info("Starting market data update job")

    # Get tickers to process
    if tickers is None:
        tickers = get_stock_universe()

    logger.info(f"Processing {len(tickers)} tickers")

    # Fetch all stock data
    results, failed_tickers = await process_stock_batch(tickers, batch_size)

    logger.info(f"Fetched {len(results)} stocks, {len(failed_tickers)} failed")

    # Store in database
    if results:
        success_count, failure_count = await upsert_stock_batch(results)
        logger.info(f"Database: {success_count} success, {failure_count} failures")
    else:
        success_count = 0
        failure_count = 0

    # Store price history for successful fetches
    history_stored = 0
    for stock in results:
        if stock.get("price"):
            if await store_price_history(stock["symbol"], stock["price"]):
                history_stored += 1

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    summary = {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": round(duration, 2),
        "total_tickers": len(tickers),
        "fetch_success": len(results),
        "fetch_failed": len(failed_tickers),
        "db_success": success_count,
        "db_failed": failure_count,
        "history_stored": history_stored,
        "failed_tickers": failed_tickers[:50],  # Limit list size
    }

    logger.info(f"Market data update complete: {summary}")

    return summary


# =============================================================================
# Query Functions
# =============================================================================


async def get_stock_by_symbol(symbol: str) -> dict | None:
    """Get a single stock by symbol."""
    try:
        result = (
            supabase.table("stocks")
            .select("*")
            .eq("symbol", symbol.upper())
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Error fetching stock {symbol}: {str(e)}")
        return None


async def get_stocks_paginated(
    page: int = 1,
    per_page: int = 50,
    sector: str = None,
    min_market_cap: float = None,
    sort_by: str = "symbol",
    sort_order: str = "asc",
) -> tuple[list[dict], int]:
    """
    Get paginated list of stocks with filters.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page
        sector: Filter by sector
        min_market_cap: Minimum market cap filter
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)

    Returns:
        Tuple of (stocks list, total count)
    """
    try:
        # Build query
        query = supabase.table("stocks").select("*", count="exact")

        # Apply filters
        if sector:
            query = query.eq("sector", sector)

        if min_market_cap:
            query = query.gte("market_cap", min_market_cap)

        # Apply sorting
        query = query.order(sort_by, desc=(sort_order.lower() == "desc"))

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)

        result = query.execute()

        return result.data, result.count

    except Exception as e:
        logger.error(f"Error fetching stocks: {str(e)}")
        return [], 0


async def get_sectors() -> list[str]:
    """Get list of unique sectors."""
    try:
        result = supabase.table("stocks").select("sector").execute()
        sectors = set(item["sector"] for item in result.data if item.get("sector"))
        return sorted(list(sectors))
    except Exception as e:
        logger.error(f"Error fetching sectors: {str(e)}")
        return []


async def get_stocks_above_ma(ma_period: int = 200) -> list[dict]:
    """Get stocks trading above their moving average."""
    try:
        ma_field = f"ma_{ma_period}"
        result = (
            supabase.table("stocks").select("*").not_.is_(ma_field, "null").execute()
        )

        # Filter where price > MA
        above_ma = [
            stock
            for stock in result.data
            if stock.get("price")
            and stock.get(ma_field)
            and stock["price"] > stock[ma_field]
        ]

        return above_ma
    except Exception as e:
        logger.error(f"Error fetching stocks above MA: {str(e)}")
        return []


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Market Data Pipeline")
    parser.add_argument("--ticker", help="Fetch single ticker")
    parser.add_argument("--full", action="store_true", help="Run full update")
    parser.add_argument("--test", action="store_true", help="Test with small batch")

    args = parser.parse_args()

    if args.ticker:
        # Fetch single ticker
        data = fetch_stock_data(args.ticker.upper())
        print(data)
    elif args.full:
        # Run full update
        asyncio.run(run_market_data_update())
    elif args.test:
        # Test with small batch
        test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        asyncio.run(run_market_data_update(tickers=test_tickers))
    else:
        print("Usage: python market_data.py --ticker AAPL | --full | --test")
