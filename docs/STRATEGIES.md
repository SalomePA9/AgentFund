# AgentFund Strategy Documentation

> A complete guide to how every strategy works, how sentiment data flows through the system, and how uncorrelated macro signals protect and enhance the portfolio.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [How Signals Work](#2-how-signals-work)
3. [The Five Core Factors](#3-the-five-core-factors)
4. [The Nine Strategies](#4-the-nine-strategies)
   - [4.1 Momentum](#41-momentum)
   - [4.2 Quality Value](#42-quality-value)
   - [4.3 Quality Momentum](#43-quality-momentum)
   - [4.4 Dividend Growth](#44-dividend-growth)
   - [4.5 Trend Following](#45-trend-following)
   - [4.6 Short-Term Reversal](#46-short-term-reversal)
   - [4.7 Statistical Arbitrage](#47-statistical-arbitrage)
   - [4.8 Volatility Premium](#48-volatility-premium)
5. [Sentiment Integration](#5-sentiment-integration)
   - [5.1 Sentiment Data Sources](#51-sentiment-data-sources)
   - [5.2 The Five Sentiment Modes](#52-the-five-sentiment-modes)
   - [5.3 The Seven Integration Layers](#53-the-seven-integration-layers)
6. [Uncorrelated Signals](#6-uncorrelated-signals)
   - [6.1 Why Uncorrelated Signals Matter](#61-why-uncorrelated-signals-matter)
   - [6.2 Cross-Asset Macro Signals](#62-cross-asset-macro-signals)
   - [6.3 Alternative Data Signals](#63-alternative-data-signals)
   - [6.4 Fundamental Regime Signals](#64-fundamental-regime-signals)
7. [The Macro Risk Overlay](#7-the-macro-risk-overlay)
8. [Risk Management](#8-risk-management)
9. [The Execution Pipeline](#9-the-execution-pipeline)
10. [Glossary](#10-glossary)

---

## 1. System Overview

AgentFund is a quantitative trading platform where each user creates **agents** — autonomous trading bots that follow a chosen strategy. Every agent picks one of nine strategies, then the system handles everything: gathering data, scoring stocks, generating trading signals, managing risk, and producing buy/sell recommendations.

### The Big Picture

```
Market Data (prices, fundamentals, dividends)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    FACTOR SCORING                              │
│  Momentum · Value · Quality · Dividend · Volatility           │
│  Each stock gets a 0-100 percentile score per factor          │
└───────────────────┬───────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────┐
│              SENTIMENT INTEGRATION (7 layers)                  │
│  News sentiment + Social sentiment + Velocity                  │
│  → Convergence, Resonance, Triangulation, Dispersion,         │
│    Regime Tilting, Temporal Persistence, MA Confluence         │
│  Output: integrated_composite score (0-100) per stock         │
└───────────────────┬───────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────┐
│                   STRATEGY EXECUTION                           │
│  Signal generators → Portfolio construction → Risk rules       │
│  Produces: list of Position recommendations (symbol, side,     │
│            weight, stop-loss, take-profit, time horizon)       │
└───────────────────┬───────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────┐
│               MACRO RISK OVERLAY                               │
│  Credit Spreads · VIX Regime · Yield Curve · Seasonality ·    │
│  Insider Breadth                                               │
│  Output: risk_scale_factor (0.25 to 1.25) that multiplies     │
│          ALL position sizes across ALL agents                  │
└───────────────────┬───────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────┐
│            ORDER GENERATION & EXECUTION                        │
│  Diff recommended vs current positions → buy/sell/hold actions │
│  Stop-loss / Take-profit / Position aging checks               │
│  → Alpaca broker execution                                     │
└───────────────────────────────────────────────────────────────┘
```

### Key Design Principles

- **Every signal is normalised to -100 (strong sell) to +100 (strong buy).** This makes it possible to combine completely different data sources — a credit spread z-score and a social media sentiment score — on the same scale.
- **Factor scores are normalised to 0-100 percentile.** A stock with a momentum score of 85 is in the 85th percentile of the universe — it has stronger momentum than 85% of the other stocks being tracked.
- **Strategies never see raw data.** They receive pre-computed signals and scores, so you can swap data sources without changing strategy logic.
- **Sentiment is integrated before strategies run.** The 7-layer `SentimentFactorIntegrator` blends sentiment into factor scores *before* the strategy makes its decisions. The strategy-level sentiment overlay is then disabled to avoid double-counting.
- **The Macro Risk Overlay never overrides strategy direction.** It only scales position *sizes* up or down. If a strategy says "buy AAPL," the overlay can shrink how much AAPL you buy during a crisis, but it will never flip that buy into a sell.

---

## 2. How Signals Work

A **signal** is a single piece of information about a stock, normalised to a standard scale. Every signal has:

| Field | What it means |
|-------|--------------|
| `symbol` | Which stock (e.g., "AAPL") |
| `signal_type` | Category (e.g., PRICE_MOMENTUM, CREDIT_SPREAD) |
| `value` | Normalised score from -100 to +100 |
| `raw_value` | Original value before normalisation |
| `confidence` | 0 to 1 — how reliable this signal is |
| `metadata` | Extra details (z-scores, sources, etc.) |

### Signal Scale Convention

```
-100 ◄──────── -50 ──────── 0 ──────── +50 ────────► +100
 │                          │                          │
 Strong Sell         Neutral / No Signal         Strong Buy
```

When multiple signals are combined, they are weighted by both their configured importance and their confidence. A signal with `confidence=0.3` (like seasonality) has less pull than one with `confidence=1.0` (like a strong momentum reading).

### Signal Types

There are 26 signal types organised into five categories:

| Category | Signals | Scope |
|----------|---------|-------|
| **Price/Momentum** | Price Momentum, Cross-Sectional Momentum | Per-stock |
| **Fundamental** | Value, Quality, Dividend Yield | Per-stock |
| **Sentiment** | News, Social, Combined, Velocity | Per-stock |
| **Technical** | RSI, MACD, Z-Score, Reversal, Realised Vol | Per-stock |
| **Uncorrelated** | Credit Spread, Yield Curve, Vol Regime, Insider Transactions, Short Interest, Seasonality, Earnings Revisions, Accruals Quality | Macro or per-stock |

---

## 3. The Five Core Factors

Before any strategy runs, the `FactorCalculator` scores every stock on five fundamental factors. These scores are percentile ranks within the stock universe (0 = worst, 100 = best).

### 3.1 Momentum (how well has the price been trending?)

**What it measures:** Has this stock been going up?

**How it's calculated:**
- **6-month return** (40% weight): `(current_price - price_126_days_ago) / price_126_days_ago`
- **12-month return with 1-month skip** (30% weight): Uses the price from 12 months ago to 1 month ago, deliberately skipping the most recent month. This avoids the well-documented "short-term reversal" effect where last month's biggest winners tend to pull back.
- **Moving average alignment** (30% weight): Checks whether `Price > MA30 > MA100 > MA200`. Perfect uptrend alignment = +1.0, perfect downtrend = -1.0.

**In plain terms:** A stock that has been steadily rising for 6-12 months, with its short-term average above its long-term average, gets a high momentum score. Academic research going back to Jegadeesh & Titman (1993) shows that this "momentum effect" — winners keep winning — is one of the strongest factors in equity markets.

### 3.2 Value (how cheap is the stock?)

**What it measures:** Is this stock trading at a discount relative to its earnings and book value?

**How it's calculated:**
- **P/E ratio rank** (50% weight): Lower P/E = higher score (inverted ranking)
- **P/B ratio rank** (50% weight): Lower P/B = higher score (inverted ranking)
- Calculated within sectors when `sector_aware=True`, so a tech stock with P/E 20 isn't unfairly compared to a utility with P/E 12

**In plain terms:** A stock that is cheap relative to what it earns (low P/E) and what it owns (low P/B) gets a high value score. The "value premium" — cheap stocks outperforming expensive ones over time — has been documented across every major market since the 1930s.

### 3.3 Quality (how good is the business?)

**What it measures:** Is this a well-run, financially stable company?

**How it's calculated:**
- **Return on Equity (ROE)** (40% weight): Higher ROE = higher score. Measures how efficiently the company turns shareholder money into profit.
- **Profit Margin** (30% weight): Higher margin = higher score. Measures what percentage of revenue becomes profit.
- **Debt Stability** (30% weight): Lower debt-to-equity and lower beta = higher score (inverted). Calculated as `1 / (1 + debt_to_equity) * (2 - min(beta, 2))`.

**In plain terms:** A company with high profits, efficient use of capital, and manageable debt gets a high quality score. Quality stocks tend to hold up better in downturns and compound more reliably over time.

### 3.4 Dividend (how much income does it pay?)

**What it measures:** Does this stock pay a meaningful and growing dividend?

**How it's calculated:**
- **Current dividend yield** (60% weight): Higher yield = higher score
- **5-year dividend growth rate** (40% weight): Faster growth = higher score
- Non-dividend-paying stocks receive a score of 0

**In plain terms:** A stock that pays a 3% yield and has been raising its dividend by 8% per year scores well. This captures both current income and the likelihood that income will grow. Companies that consistently grow dividends tend to be mature, profitable businesses.

### 3.5 Volatility (how bumpy is the ride?)

**What it measures:** How much does this stock's price jump around day-to-day?

**How it's calculated:**
- Uses ATR (Average True Range) as a percentage of price, or 20-day annualised volatility from price history
- **Inverted ranking**: Lower volatility = higher score

**In plain terms:** A stock that moves 0.5% per day scores higher than one that moves 3% per day. The "low-volatility anomaly" shows that calmer stocks often deliver better risk-adjusted returns than wild ones — the opposite of what textbook finance predicts.

### Composite Score

The five factors are combined into a single composite score using strategy-specific weights. A momentum strategy weights momentum at 100% and ignores value; a quality-value strategy splits 50/50 between value and quality. These weights are set in each strategy's preset configuration.

---
