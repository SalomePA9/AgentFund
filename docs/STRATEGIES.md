# AgentFund Strategy Documentation

> A complete guide to how every strategy works, how sentiment data flows through the system, and how uncorrelated macro signals protect and enhance the portfolio.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [How Signals Work](#2-how-signals-work)
3. [The Five Core Factors](#3-the-five-core-factors)
4. [The Eight Strategies](#4-the-eight-strategies)
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

AgentFund is a quantitative trading platform where each user creates **agents** — autonomous trading bots that follow a chosen strategy. Every agent picks one of eight strategies, then the system handles everything: gathering data, scoring stocks, generating trading signals, managing risk, and producing buy/sell recommendations.

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
- **Sentiment is integrated before strategies run.** The 7-layer `SentimentFactorIntegrator` blends sentiment into factor scores *before* the strategy makes its decisions. For factor-based strategies (Momentum, Quality Value, Quality Momentum, Dividend Growth), the strategy-level sentiment overlay is disabled to avoid double-counting because they already consume the `integrated_composite` scores. Advanced strategies (Trend Following, Short-Term Reversal, Statistical Arbitrage, Volatility Premium) keep their designed sentiment modes active since they use their own specialised signal pipelines rather than the integrated composite.
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
- Non-dividend-paying stocks receive a neutral score of 50 (universe median)

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

## 4. The Eight Strategies

AgentFund has two tiers of strategies:

- **4 user-facing strategies** (simpler, designed for most investors): Momentum, Quality Value, Quality Momentum, Dividend Growth
- **4 advanced strategies** (for power users who understand the trade-offs): Trend Following, Short-Term Reversal, Statistical Arbitrage, Volatility Premium

All eight strategies are concrete implementations that inherit from `BaseStrategy`. The first four all use the `CrossSectionalFactorStrategy` engine (they rank stocks against each other using different factor weights), while the advanced four each have their own specialised engine.

### How Strategies Use Sentiment and Uncorrelated Signals

Every strategy interacts with sentiment and uncorrelated signals through **three independent layers**:

1. **Pre-execution integration** — The `SentimentFactorIntegrator` blends sentiment into factor scores *before* the strategy runs. This produces an `integrated_composite` score (0-100) that the strategy uses for ranking. Every strategy benefits from this.

2. **Macro Risk Overlay** — After the strategy produces its positions, the `MacroRiskOverlay` scales all position sizes based on credit spreads, VIX, yield curve, seasonality, and insider breadth. Every strategy is affected by this equally.

3. **Strategy-specific sentiment mode** — Each strategy is configured with a sentiment mode (FILTER, ALPHA, CONFIRMATION, RISK_ADJUSTMENT). For the four **factor-based strategies** (Momentum, Quality Value, Quality Momentum, Dividend Growth), this mode is **disabled at runtime** because they consume the `integrated_composite` scores from layer 1, and running sentiment twice would double-count it. The four **advanced strategies** (Trend Following, Short-Term Reversal, Statistical Arbitrage, Volatility Premium) **keep their designed sentiment modes active** — they don't read the integrated composite and instead apply sentiment through their own specialised mechanisms (position sizing via confidence, sentiment confirmation, crisis gating, etc.).

---

### 4.1 Momentum

**One-sentence summary:** Buy stocks that have been going up the most over the past 6 months.

**Strategy type:** Cross-Sectional Factor
**Default sentiment mode:** FILTER (only buy winners with positive sentiment)
**Factor weights:** Momentum 100%

**How it works step by step:**

1. The `CrossSectionalMomentumSignal` generator calculates 6-month returns for every stock in the universe.
2. Stocks are ranked by return — top performers get signal values near +100, bottom performers near -100.
3. The `SentimentFactorIntegrator` has already blended sentiment into factor scores with these weights: momentum 55%, sentiment 25%, quality 10%, volatility 10%. This means a stock with strong momentum *and* positive sentiment ranks higher than one with strong momentum but negative sentiment.
4. The strategy selects the **top 20%** of ranked stocks for long positions.
5. Positions are **equal-weighted** and capped at 5% each.
6. Position sizes are **volatility-scaled**: each position is sized inversely to its stock's volatility, targeting 15% annual portfolio volatility.
7. Stop-losses are set at 2x ATR below entry price.

**Why sentiment matters here:** Pure momentum strategies are vulnerable to "momentum crashes" — sudden reversals where last year's winners collapse. This happens when crowded trades unwind. The sentiment filter catches early warning signs: if a momentum winner's sentiment starts turning negative (bad news, social media panic), the system avoids entering or exits early.

**Uncorrelated signals' role:** The Macro Risk Overlay protects momentum strategies during regime changes. When credit spreads widen and the VIX spikes, it's often the start of a momentum crash. The overlay reduces all position sizes before the crash fully develops.

**Best for:** Growth-oriented investors who believe trends persist. Works well in trending markets, struggles in choppy, range-bound periods.

---

### 4.2 Quality Value

**One-sentence summary:** Buy cheap stocks (low P/E, low P/B) that are also high-quality businesses (high ROE, stable margins, low debt).

**Strategy type:** Cross-Sectional Factor
**Default sentiment mode:** CONFIRMATION (require sentiment isn't deteriorating)
**Factor weights:** Value 50%, Quality 50%

**How it works step by step:**

1. The `ValueSignal` generator ranks stocks by P/E and P/B ratios (lower = better, inverted so cheap stocks score highest).
2. The `QualitySignal` generator ranks stocks by ROE, profit margin, and financial stability.
3. Signals are combined with equal weight (50/50) via the `SignalCombiner`.
4. The `SentimentFactorIntegrator` uses these weights: value 30%, quality 30%, sentiment 25%, volatility 10%, dividend 5%. The sentiment integration acts as a "value trap detector" — if a stock is cheap but sentiment is collapsing, it might be cheap for a reason.
5. The strategy selects the **top 20%** for long positions.
6. Positions use **equal-risk** sizing (each position contributes the same amount of portfolio risk), targeting 12% annual volatility.
7. Stop-losses are wider at 2.5x ATR, giving value stocks more room to recover from short-term dips.

**Why sentiment matters here:** The biggest risk for value investors is the "value trap" — a stock that looks cheap but keeps getting cheaper because the business is deteriorating. Sentiment confirmation catches this: if news sentiment and social sentiment are both deteriorating for a cheap stock, the system reduces confidence. The sentiment velocity signal is especially important, weighted at 30%, because a *worsening* sentiment trend for a value stock is a red flag.

**Uncorrelated signals' role:** Insider transactions are particularly valuable for value stocks. When company insiders buy shares of a stock that looks cheap on financial metrics, it's a strong confirmation that the value is real, not a trap. The earnings revisions signal also helps: if analysts are revising estimates upward for a cheap stock, the cheapness is more likely to correct.

**Best for:** Patient, conservative investors with a long time horizon. Tends to underperform in momentum-driven bull markets but provides a margin of safety during corrections.

---

### 4.3 Quality Momentum

**One-sentence summary:** Buy stocks with strong price momentum that also have quality fundamentals, using sentiment as a third ranking factor.

**Strategy type:** Cross-Sectional Factor
**Default sentiment mode:** ALPHA (sentiment is an additional factor signal)
**Factor weights:** Momentum 50%, Quality 50%

**How it works step by step:**

1. The `CrossSectionalMomentumSignal` ranks stocks by 6-month relative returns.
2. The `QualitySignal` ranks stocks by ROE, profit margin, and stability.
3. Both signals are combined 50/50.
4. The `SentimentFactorIntegrator` uses aggressive sentiment weighting: momentum 30%, quality 25%, **sentiment 35%**, volatility 10%. Sentiment is the *largest single weight* for this strategy because it acts as the tiebreaker between equally strong momentum-quality candidates.
5. The integrated composite score is blended into the strategy's signal combiner output at 40% weight, so sentiment-favoured stocks get a meaningful ranking boost.
6. Top 20% are selected, equal-weighted, capped at 5% each.
7. Volatility-scaled sizing targeting 15% annual vol. Stop-losses at 2x ATR.

**Why sentiment matters here:** This strategy uses sentiment more heavily than any other — it's literally the largest factor weight at 35%. The idea is GARP (Growth at a Reasonable Price): among stocks with good momentum and quality, pick the ones the market *also* feels good about. Sentiment velocity confirms that momentum will continue: if a stock is going up AND sentiment is accelerating, the trend is more likely to persist.

**Uncorrelated signals' role:** Earnings revisions are particularly synergistic. A stock with strong momentum + quality + upward earnings revisions is the "trifecta" — the price trend, the business quality, and the analyst outlook all agree. The accruals quality signal adds another check: if earnings are coming from real cash flows (not accounting tricks), the momentum is more sustainable.

**Best for:** Active investors who want to ride trends but with a quality safety net. A more sophisticated version of pure momentum.

---

### 4.4 Dividend Growth

**One-sentence summary:** Buy stocks with solid dividend yields that also have quality characteristics ensuring the dividend is sustainable and growing.

**Strategy type:** Cross-Sectional Factor
**Default sentiment mode:** FILTER (avoid dividend stocks with negative sentiment)
**Factor weights:** Quality 40%, Dividend 20%, Value 20%, Low Volatility 20%

**How it works step by step:**

1. The `DividendYieldSignal` ranks stocks by dividend yield (must meet a minimum of 2%).
2. The `QualitySignal` ranks by ROE, margin, and stability — ensuring dividends are sustainable.
3. The `ValueSignal` and `RealizedVolatilitySignal` add value and low-vol dimensions.
4. These are combined with the multi-factor weights above.
5. The `SentimentFactorIntegrator` uses: quality 25%, dividend 25%, sentiment 20%, value 15%, volatility 15%. News sentiment gets 60% of the sentiment weight (vs. 20% social) because institutional news is more relevant for dividend safety than retail chatter.
6. A sentiment filter threshold of +10 is applied — the stock needs *positive* sentiment, not just neutral. This is more conservative than other strategies.
7. Top 25% are selected (slightly broader than other strategies), equal-weighted.
8. **Equal-risk** sizing targeting only 10% annual volatility (the most conservative target of any strategy).
9. Stop-losses are wide at 3x ATR — income stocks need room to breathe through ex-dividend date volatility.

**Why sentiment matters here:** For dividend investors, the worst outcome is a dividend cut. Companies that cut dividends see massive price drops (typically 20-30% immediately). The sentiment filter catches early warnings: deteriorating news sentiment often precedes dividend cuts by weeks or months. The sentiment velocity signal helps detect when fundamentals are worsening faster than the price reflects.

**Uncorrelated signals' role:** Short interest is a strong negative signal for dividend stocks. If hedge funds are aggressively shorting a high-yield stock, they may know about impending earnings problems or a dividend cut. The credit spread signal also matters: when credit markets tighten, highly-leveraged dividend payers are the first to cut. The overlay will reduce dividend stock exposure when credit conditions deteriorate.

**Best for:** Income-focused investors, retirees, conservative portfolios that prioritise capital preservation and steady cash flow.

---

### 4.5 Trend Following

**One-sentence summary:** Go long assets in uptrends and short assets in downtrends, using moving average crossovers with volatility-based position sizing.

**Strategy type:** Trend Following (dedicated engine)
**Default sentiment mode:** RISK_ADJUSTMENT (reduce size when sentiment diverges from trend)
**Supports shorting:** Yes

**How it works step by step:**

1. The `TimeSeriesMomentumSignal` generator computes trend strength for each stock:
   - Calculates short-window (20-day) and long-window (60-day) returns
   - Checks if price is above both the 20-day and 60-day moving averages
   - Combines into a trend score: `(short_return * 0.4 + long_return * 0.6) * 100 + trend_direction * 10`
2. Stocks with a signal value above +20 go **long**. Stocks below -20 go **short** (if shorting is enabled).
3. Each position is **volatility-scaled**: `weight = (target_vol / stock_vol) * (signal_strength / 100)`. A stock with 10% annualised volatility in a portfolio targeting 15% gets a 1.5x weight multiplier, while a 30% vol stock gets a 0.5x multiplier. This creates a natural risk-parity effect.
4. Max position size: 10%. Max portfolio leverage: 1.5x (allows for combined long + short exposure).
5. **Hysteresis** is applied to prevent "whipsaw" — if a stock is already held, it gets a 5-point bonus to its signal strength, so it won't be exited just because the signal dipped marginally below the threshold. Direction flips (long to short) require extra conviction (signal > 2x the hysteresis band).
6. Max holding period: ~90 days (1 quarter).

**Why sentiment matters here:** The risk-adjustment mode reduces position sizes when sentiment diverges from the price trend. Example: if AAPL is in a technical uptrend but social sentiment has turned negative, the position size is reduced by up to 20%. Conversely, when sentiment confirms the trend (uptrend + bullish sentiment), positions can be up to 20% larger. This catches situations where the price trend hasn't broken yet but market participants are already getting nervous.

**Uncorrelated signals' role:** The VIX regime signal is critical for trend following. When VIX spikes above 35 and the term structure inverts (backwardation), it signals a panic environment where trends break down rapidly. The overlay reduces all trend-following positions to protect against sudden reversals. The yield curve signal helps identify macro regime changes (inversions precede recessions) that can invalidate long-running equity trends.

**Best for:** Tactical allocation, crisis hedging, diversification from long-only strategies. Trend following historically provides "crisis alpha" — positive returns during extended equity drawdowns.

---

### 4.6 Short-Term Reversal

**One-sentence summary:** Buy stocks that dropped sharply over the last 1-5 days (oversold) and sell stocks that rose sharply (overbought), betting they'll revert to the mean.

**Strategy type:** Short-Term Reversal (dedicated engine)
**Default sentiment mode:** CONFIRMATION (only trade reversals when sentiment also reverting)
**Supports shorting:** Yes (market-neutral by default)

**How it works step by step:**

1. The `ShortTermReversalSignal` generator calculates 5-day returns for all stocks.
2. Returns are converted to **z-scores** — how many standard deviations each stock's return is from the cross-sectional average.
3. Only stocks with |z-score| >= 1.5 are considered. A stock that dropped 2.5 standard deviations is a stronger candidate than one that dropped 1.6.
4. The reversal signal is **inverted**: stocks with negative returns (z < 0) get positive signals (buy), and vice versa.
5. Position sizing scales with z-score extremity: `weight = min(z_score / 5 * 0.05, max_position_size)`. More extreme oversold = larger position.
6. Max position size is small: 3% (more positions, more diversification).
7. The portfolio is **balanced for market neutrality**: total long weight = total short weight. This means the strategy profits from the spread between losers bouncing back and winners pulling back, regardless of overall market direction.
8. **Hysteresis band of 3.0** prevents unnecessary churn.
9. Holding period: 5 days (this is a short-horizon strategy).

**Why sentiment matters here:** The confirmation mode is crucial. Without it, the strategy would buy every stock that drops sharply — including stocks dropping on legitimate bad news (earnings miss, fraud discovery, product failure). These are "falling knives" that don't revert.

The sentiment velocity signal (weighted at 40% — the highest of any strategy) distinguishes between:
- **Noise-driven drops** (no sentiment change or sentiment improving): Good reversal candidate
- **Fundamental drops** (sentiment plunging alongside price): Falling knife — skip it

**Uncorrelated signals' role:** Short interest provides a critical filter. If a stock is heavily shorted (>10% of float) and just dropped sharply, the decline may be a short squeeze setup (bullish) or a continued bear raid (bearish). The insider transaction signal helps resolve ambiguity: if insiders are buying into the dip, reversion is more likely.

**Best for:** Active traders comfortable with high turnover and short holding periods. Requires low transaction costs to be profitable.

---

### 4.7 Statistical Arbitrage

**One-sentence summary:** Trade relative mispricings between related stocks using statistical z-scores, staying market-neutral.

**Strategy type:** Statistical Arbitrage (dedicated engine)
**Default sentiment mode:** ALPHA (use sentiment divergence as an additional spread signal)
**Supports shorting:** Yes (inherently market-neutral)

**How it works step by step:**

1. The `ZScoreSignal` generator calculates a 60-day rolling z-score for each stock: `z = (current_price - 60_day_mean) / 60_day_std`.
2. **Pairs mode** (if pairs are configured): For each pair (e.g., KO/PEP), the system calculates a spread z-score. If the spread is too wide (z > 2.0), it shorts the outperformer and buys the underperformer, betting the spread will narrow.
3. **Individual mode** (no pairs): Each stock is treated independently. Stocks with z > 2.0 are shorted (overbought), stocks with z < -2.0 are bought (oversold).
4. Z-scores beyond 4.0 are excluded — extreme outliers may be driven by genuine fundamental changes, not statistical deviations.
5. Position weight scales with z-score magnitude: `weight = min(|z| / 10, max_position_size)`.
6. Max position size: 5%. Target volatility: 8% (the lowest of any strategy).
7. **Hysteresis band of 4.0** — stat arb positions shouldn't flip easily.
8. Max holding period: ~30 days (mean reversion should happen within a month).

**Why sentiment matters here:** In alpha mode, sentiment divergence between paired stocks is treated as an additional spread signal. If KO and PEP historically move together, but KO's sentiment is improving while PEP's is deteriorating, that sentiment divergence amplifies the statistical signal. News sentiment is weighted at 50% (higher than social) because institutional information flow matters more for relative value.

**Uncorrelated signals' role:** Accruals quality is especially relevant. If two stocks in a pair have diverging accruals quality (one has clean cash earnings, the other has aggressive accounting), the "cheap" stock might be cheap because its earnings are lower quality. The earnings revisions signal helps too: if one leg of the pair has upward revisions while the other has downward, the spread may not revert.

**Best for:** Market-neutral investors, quantitative traders who want zero market beta. Requires constant monitoring and can fail when correlations break down.

---

### 4.8 Volatility Premium

**One-sentence summary:** Own the calmest stocks in the market (low volatility), acting as an equity proxy for systematically selling insurance.

**Strategy type:** Volatility Premium (dedicated engine)
**Default sentiment mode:** FILTER (don't own low-vol stocks during crisis)
**Supports shorting:** Optional (can short high-vol stocks)

**How it works step by step:**

1. The `RealizedVolatilitySignal` generator calculates 20-day annualised volatility for each stock.
2. Stocks are ranked by volatility — the **bottom 30%** (lowest volatility) are selected.
3. Position sizing is **inversely proportional to volatility**: `weight = min(target_vol / stock_vol * 0.1, max_position_size)`. Calmer stocks get larger positions.
4. Max position size: 5%. Target volatility: 10% (conservative).
5. If configured, the **top 30% highest-vol** stocks can be shorted (at half the size of long positions).
6. **Crisis detection**: Before constructing the portfolio, the strategy checks aggregate news sentiment. If average sentiment drops below -50 (extreme fear), the strategy goes entirely to cash — it won't hold low-vol stocks during a genuine crisis because even "safe" stocks sell off in panics. The sentiment filter threshold is -30 for individual stocks.
7. **Hysteresis band of 6.0** — the widest of any strategy, because vol premium is a slow, low-turnover approach.
8. Max holding period: ~120 days (1 quarter).

**Why sentiment matters here:** The volatility premium strategy is essentially selling insurance. You earn a steady premium (calm stocks outperform their risk suggests they should), but you face a "tail risk" — occasionally, even safe-looking stocks crash during systemic events. The sentiment filter acts as an early-warning system: when aggregate fear spikes (sentiment < -50), the strategy exits *before* the crash hits. It's like an insurance company stopping underwriting when a hurricane is forming.

**Uncorrelated signals' role:** The VIX regime signal is the most important overlay for this strategy. When VIX is elevated (>30) or the VIX term structure is in backwardation (near-term fear exceeds long-term), the overlay aggressively reduces all vol-premium positions. The credit spread signal reinforces this: widening credit spreads mean the market is repricing risk, and vol sellers should step back.

**Best for:** Defensive, income-oriented investors. Performs well in calm, slowly-rising markets. Vulnerable during sudden crashes if the sentiment filter doesn't trigger in time.

---

## 5. Sentiment Integration

Sentiment is not a simple "positive = buy, negative = sell" overlay. AgentFund uses a sophisticated multi-layer integration system that combines sentiment with quantitative factors in nuanced ways.

### 5.1 Sentiment Data Sources

AgentFund collects sentiment from two primary sources:

**FinBERT (News Sentiment)**
- Uses the `ProsusAI/finbert` model, a BERT model fine-tuned specifically on financial text
- Analyses news headlines and articles for each stock
- Produces a score from -100 (very negative) to +100 (very positive)
- More weight given to institutional-quality sources

**StockTwits (Social Sentiment)**
- Pulls real-time posts from the StockTwits public API
- Captures retail investor sentiment — what individual traders are saying and feeling
- Score from -100 to +100
- Includes mention volume (how much people are talking about a stock)

**Derived Signals:**
- **Combined Sentiment**: Weighted average of news and social — typically 40% news + 30% social + 30% velocity
- **Sentiment Velocity**: How fast sentiment is changing (the "acceleration" of mood). Calculated as the rate of change over the past 7 days. A stock whose sentiment went from 0 to +40 in a week has high positive velocity.

### 5.2 The Five Sentiment Modes

Each strategy is configured with one of five modes that determine how sentiment interacts with strategy signals. For the four factor-based strategies (Momentum, Quality Value, Quality Momentum, Dividend Growth), sentiment is handled entirely by the pre-execution 7-layer integrator and the strategy-level mode is disabled. For the four advanced strategies (Trend Following, Short-Term Reversal, Statistical Arbitrage, Volatility Premium), the configured mode is applied at the strategy level through the `_apply_sentiment_overlay` method, which modifies signal confidence and/or value before portfolio construction.

#### DISABLED
Sentiment is ignored entirely. The strategy relies purely on quantitative factor scores.

#### FILTER
Sentiment acts as a **gate**. Signals that disagree with sentiment are blocked:
- Bullish signal + negative sentiment = signal **dropped** (don't buy into negativity)
- Bearish signal + positive sentiment = signal **dropped** (don't short into positivity)

Think of it as: "I'll only trade when sentiment *agrees* with my quantitative signal." This is the most conservative use of sentiment.

**Used by:** Momentum, Dividend Growth, Volatility Premium

#### ALPHA
Sentiment is used as an **additional ranking factor**. It doesn't block signals but adjusts their scores:
- Signal value is modified: `new_value = original * (1 - alpha_weight) + sentiment * alpha_weight`
- Typical alpha weight: 15-20% of the total signal

Think of it as: "Sentiment is one more factor in my multi-factor model, alongside momentum, value, and quality."

**Used by:** Quality Momentum (15% weight), Statistical Arbitrage (20% weight)

#### RISK_ADJUSTMENT
Sentiment adjusts **position sizing** through confidence:
- Signal direction matches sentiment → confidence boosted by 20%
- Signal direction conflicts with sentiment → confidence reduced by 20%
- Higher confidence → larger position; lower confidence → smaller position

Think of it as: "I'll still trade, but I'll size positions smaller when sentiment disagrees with me."

**Used by:** Trend Following

#### CONFIRMATION
Sentiment must **confirm** the signal for full conviction:
- Bullish signal + negative sentiment → confidence cut to 50%
- Bearish signal + positive sentiment → confidence cut to 50%
- Aligned signal + sentiment → full confidence maintained

Think of it as: "I need sentiment to back up my signal, or I'll only put half the money on."

**Used by:** Quality Value, Short-Term Reversal

### 5.3 The Seven Integration Layers

The `SentimentFactorIntegrator` is the engine that blends sentiment into factor scores *before* strategies run. It applies seven proprietary techniques in sequence. Here's how each one works:

#### Layer 1: Convergence Amplification (bonus: -15 to +15 points)

**What it does:** Rewards stocks where factor direction and sentiment direction agree, penalises disagreement.

**How it works:**
1. Compute a strategy-weighted factor direction. For a momentum strategy, this is mostly the momentum score. For a quality-value strategy, it's the average of value and quality scores.
2. Convert both factor direction and sentiment direction to a [-1, +1] scale.
3. Multiply them together: `agreement = factor_direction * sentiment_direction`
4. Scale to [-15, +15] and add to the composite score.

**Example:** A stock with momentum score 80 (factor direction = +0.6) and combined sentiment +60 (sentiment direction = +0.6) gets a convergence bonus of `0.6 * 0.6 * 15 = +5.4 points`. A stock with momentum 80 but sentiment -60 gets a penalty of `-5.4 points`.

**Why it matters:** When quantitative factors and human sentiment agree, the signal is more reliable. Disagreement suggests one side is wrong, warranting caution.

#### Layer 2: Velocity-Momentum Resonance (multiplier: 0.8x to 1.2x)

**What it does:** When sentiment velocity (acceleration) aligns with price momentum, the momentum score is amplified. When they diverge, it's dampened.

**How it works:**
1. Check momentum direction: score > 50 = bullish, < 50 = bearish
2. Normalise sentiment velocity to [-1, +1] (typical range is about -10 to +10 points per day)
3. If momentum is bullish and velocity is positive (sentiment improving): momentum is multiplied by up to 1.2x
4. If momentum is bullish but velocity is negative (sentiment deteriorating): momentum is multiplied by as little as 0.8x

**Example:** A stock with momentum score 75 and positive sentiment velocity gets its momentum boosted to `75 * 1.15 = 86.25`. The same stock with negative velocity would see momentum dampened to `75 * 0.85 = 63.75`.

**Why it matters:** Momentum is most reliable when market participants are *increasingly* optimistic (or pessimistic). Decelerating sentiment in a momentum stock is an early warning that the trend may be exhausting.

#### Layer 3: Cross-Source Triangulation (confidence: 0.5 to 1.0)

**What it does:** Measures agreement between news and social sentiment to determine overall confidence.

**How it works:**
1. If news and social sentiment have the **same sign** (both positive or both negative):
   - Confidence ranges from 0.7 to 1.0, depending on how close their magnitudes are
   - News +40, Social +35 → high confidence (close agreement)
   - News +80, Social +10 → moderate confidence (same direction but different intensity)
2. If they have **opposite signs** (news positive, social negative or vice versa):
   - Confidence drops to 0.5 to 0.7 (significant disagreement)
   - The larger the gap, the lower the confidence
3. If one source is missing: confidence defaults to 0.75

**Why it matters:** When institutional analysis (news) and retail crowd wisdom (social) agree, the sentiment signal is more trustworthy. Disagreement may mean the crowd is wrong (retail mania), or the institutions are wrong (lagging narrative), or both — in any case, certainty is lower.

#### Layer 4: Sentiment Dispersion Risk (risk: 0.0 to 1.0)

**What it does:** Quantifies the uncertainty when news and social sentiment diverge significantly.

**How it works:**
- `spread = |news_sentiment - social_sentiment|` (range: 0 to 200)
- Dispersion risk = `1 - 1 / (1 + (spread / 60)^1.5)` — a sigmoid that is near 0 when spread is small and approaches 1.0 when spread exceeds 100
- The composite score is then scaled: `composite *= triangulation_confidence * (1 - 0.3 * dispersion_risk)`

**Example:** News +70, Social -30 → spread = 100 → dispersion risk = ~0.72. The composite score is pulled 22% toward the mean (50), reducing the strength of any directional bet.

**Why it matters:** High dispersion means the market hasn't reached consensus. Trading on ambiguous information is risky, so positions should be smaller.

#### Layer 5: Regime-Aware Factor Tilting (weight adjustments)

**What it does:** Detects whether the overall market is in a "risk-on" or "risk-off" regime and shifts factor weights accordingly.

**How it works:**
1. Calculate aggregate sentiment across all stocks: `avg_sentiment = mean of all combined_sentiment scores`
2. Calculate breadth: what fraction of stocks have positive sentiment
3. Compute regime strength using `tanh(avg_sentiment / 25)` blended with breadth → continuous value from -1.0 (strong risk-off) to +1.0 (strong risk-on)
4. Apply proportional weight tilts:

| Factor | Risk-On Tilt | Risk-Off Tilt |
|--------|-------------|---------------|
| Momentum | +8% | -8% |
| Value | -4% | +4% |
| Quality | -4% | +6% |
| Dividend | -2% | +4% |
| Volatility | -4% | +4% |
| Sentiment | +6% | -10% |

The tilt is applied proportionally to regime strength. A regime strength of +0.5 applies 50% of the risk-on tilt. Weights are renormalised to sum to 1.0 after tilting.

**Example:** In a risk-on regime (strength +0.7), a momentum strategy would see its momentum weight increase from 55% to ~60.6% while its sentiment weight increases from 25% to ~29.2%. In a risk-off regime, quality and value weights would increase at the expense of momentum and sentiment.

**Why it matters:** Different factors perform better in different market environments. Momentum thrives in risk-on rallies but crashes in risk-off panics. Quality and value provide protection during downturns. By dynamically tilting weights, the system adapts to the current environment instead of running a static model.

#### Layer 6: Temporal Persistence (bonus: -10 to +10 points)

**What it does:** Rewards sustained, multi-day sentiment and penalises noisy single-day spikes.

**How it works:**
1. **Streak count**: Consecutive days of same-sign sentiment. A 10-day bullish streak is more meaningful than a 1-day blip.
2. **Persistence**: How stable sentiment has been (low variance = high persistence, range 0-1)
3. **Trend slope**: Linear regression slope of sentiment over the lookback window
4. **Breakout detection**: If recent sentiment differs from prior baseline by >30 points AND crosses zero, it's flagged as a regime change

The temporal bonus is computed as:
```
streak_component = sign(streak) * log(1 + |streak|) * 2.0
persistence_multiplier = 0.4 + 0.9 * persistence
slope_component = clamp(trend_slope * 0.5, -2, +2)
breakout_bonus = ±2.0 if breakout detected

bonus = (streak_component * persistence_multiplier) + slope_component + breakout_bonus
clamped to [-10, +10]
```

**Example:** A stock with a 10-day bullish streak (component = +4.6), high persistence 0.8 (multiplier = 1.12), rising trend slope +3 (component = +1.5), and no breakout: `bonus = (4.6 * 1.12) + 1.5 = +6.65 points`.

**Why it matters:** A single-day sentiment spike might be a reaction to a news event that is quickly forgotten. But if sentiment stays elevated for 5-10 consecutive days, the market has formed a genuine consensus. This layer separates signal from noise.

#### Layer 7: MA-Sentiment Confluence (bonus: -12 to +12 points)

**What it does:** Generates a strong signal when price position relative to the 200-day moving average aligns with sustained sentiment direction.

**How it works:**
1. Check if price is above or below the 200-day MA
2. Check the sentiment streak direction (multi-day bullish or bearish)
3. If both agree (price above MA + bullish streak, or price below MA + bearish streak):
   - Bonus scales with both streak length and MA distance
   - `bonus = 12.0 * min(|streak| / 10, 1.0) * min(|ma_deviation| / 0.10, 1.0)`
   - Maximum ±12 points
4. If they **diverge** (price above MA but bearish sentiment, or vice versa):
   - Mild penalty: `-3.0 * min(|streak| / 10, 1.0)`

**Example:** AAPL is 7% above its MA200, with a 7-day bullish sentiment streak: `bonus = 12.0 * (7/10) * (0.07/0.10) = +5.88 points`. If AAPL were 7% above MA200 but had a 7-day bearish streak: `penalty = -3.0 * (7/10) = -2.1 points`.

**Why it matters:** The 200-day MA is the most-watched technical level in the market. When a stock is above its MA200 AND sentiment has been positive for multiple days, there is genuine institutional and retail conviction behind the trend. This confluence is one of the strongest predictive patterns in equity markets.

### How the Seven Layers Combine

The final integrated composite score for each stock is computed as:

```
1. Start with strategy-weighted factor scores (0-100 scale)
2. Apply regime-tilted weights (Layer 5)
3. Multiply momentum by resonance multiplier (Layer 2)
4. Add sentiment as a weighted factor
5. Compute weighted average → base composite
6. Add convergence bonus (Layer 1)
7. Add temporal persistence bonus (Layer 6)
8. Add MA-sentiment confluence bonus (Layer 7)
9. Scale by triangulation confidence * (1 - 0.3 * dispersion risk) (Layers 3 & 4)
10. Center around 50, clamp to [0, 100]
```

The result is an `integrated_composite` score that captures not just the quantitative fundamentals of a stock, but the market's collective sentiment about it, how strongly different sentiment sources agree, how persistent that sentiment has been, and whether the current market regime favours or disfavours the stock's factor profile.

### Default Factor Weights by Strategy (with sentiment)

| Factor | Momentum | Quality Value | Quality Momentum | Dividend Growth |
|--------|----------|---------------|-------------------|-----------------|
| Momentum | 55% | 0% | 30% | 0% |
| Value | 0% | 30% | 0% | 15% |
| Quality | 10% | 30% | 25% | 25% |
| Dividend | 0% | 5% | 0% | 25% |
| Volatility | 10% | 10% | 10% | 15% |
| **Sentiment** | **25%** | **25%** | **35%** | **20%** |

---

## 6. Uncorrelated Signals

### 6.1 Why Uncorrelated Signals Matter

Traditional equity strategies rely on signals that are correlated with each other. Momentum, value, and quality are all derived from the same stock prices and financial statements. Retail sentiment (StockTwits, news) tends to follow price action — people feel good about stocks that are going up.

The problem: when these correlated signals all fail at the same time (a market regime change), every strategy suffers simultaneously. The 2008 "quant quake" and the 2020 COVID crash both saw momentum, value, and quality factors crash together.

**Uncorrelated signals** come from entirely different data sources:

- **Credit markets** (bond spreads) measure risk appetite among institutional fixed-income investors
- **Volatility markets** (VIX, options) capture how much people are willing to pay for insurance
- **Insider transactions** (SEC filings) reflect what people with private company knowledge are doing with their own money
- **Short interest** captures what sophisticated institutional short-sellers think
- **Calendar patterns** are purely time-based and mathematically independent of everything else

Because these signals are structurally different from equity factor signals, they provide information that the existing system was blind to. They don't replace the existing signals — they add a new dimension of context.

### 6.2 Cross-Asset Macro Signals

These are **global signals** that affect ALL stocks equally. They don't tell you which stock to buy — they tell you whether it's safe to buy *anything*.

#### Credit Spread Signal

**Data source:** FRED API — BofA High-Yield Option-Adjusted Spread (series: `BAMLH0A0HYM2`)

**What it is:** The difference in yield between risky corporate bonds and safe government bonds. When investors demand a bigger premium to hold risky debt, it means they're worried about default risk — and that worry usually spreads to equities.

**How the signal works:**
1. Fetch the current high-yield spread and its history
2. Calculate a **z-score**: how many standard deviations the current spread is from its historical mean
3. Calculate **rate of change**: is the spread widening (bad) or tightening (good)?
4. Signal formula: `signal = -z_score * 30 - rate_of_change * 5`
5. The signal is **inverted** because high spreads = bearish: a z-score of +2 (spreads well above average) produces a signal of -60 (strong sell)

**Confidence:** Based on z-score magnitude. A z-score of 2.0 → confidence 1.0, z-score of 0.5 → confidence 0.25.

**Why it matters in simple terms:** Credit markets are often called "the smart money." Bond investors tend to be institutional, analytical, and risk-aware. When they start demanding higher yields to hold corporate debt, they're telling you something that equity investors haven't figured out yet. Research by Friewald, Wagner & Zechner (2014) shows that credit spreads lead equity market moves by 2-6 weeks.

**Real-world example:** In June 2007, high-yield spreads started widening months before the equity market peaked in October 2007. Any system watching credit spreads would have been reducing equity exposure while the S&P 500 was still making new highs.

#### Yield Curve Signal

**Data source:** FRED API — 10-Year minus 2-Year Treasury Spread (series: `T10Y2Y`)

**What it is:** The difference between the 10-year and 2-year US Treasury yields. Normally, longer-term bonds pay higher yields than shorter ones (a "normal" upward-sloping curve). When this inverts (2-year yields exceed 10-year), it has preceded every US recession since 1955.

**How the signal works:**
1. Fetch the current 10Y-2Y spread
2. Positive spread = normal curve = bullish (growth expectations healthy)
3. Negative spread = inverted curve = bearish (recession risk)
4. Signal formula: `signal = spread * 50 + rate_of_change * 20`
5. A spread of +2.0% → signal of +100 (maximum bullish). A spread of -0.5% → signal of -25 (moderately bearish).

**Why it matters in simple terms:** The yield curve captures the economy's "metabolism." When investors expect growth, they demand higher yields for tying up money longer (normal curve). When they expect a downturn, they rush into long-term bonds for safety, driving long yields below short yields (inversion). An inverted curve doesn't just predict recessions — it often *causes* them by making bank lending unprofitable.

**Important nuance:** A *rapidly flattening* curve (rate of change is negative) is more ominous than a *stably inverted* one. Once the curve has been inverted for a while, markets have already priced in the recession risk. That's why rate of change gets a 20-point weight.

#### Volatility Regime Signal

**Data source:** Yahoo Finance — VIX (^VIX) and VIX 3-Month (^VIX3M) indices, plus SPY for realised volatility

**What it is:** A composite reading of three volatility dimensions:
1. **VIX level**: How much options traders are paying for S&P 500 protection
2. **VIX term structure**: Whether short-term fear exceeds long-term fear (backwardation)
3. **Implied-Realised spread**: Whether options are pricing more volatility than is actually occurring

**How the signal works:**
1. Calculate the **VIX component**: `(20 - vix) / 20`, mapping VIX 20 → neutral, VIX 10 → +0.5, VIX 40 → -1.0
2. Calculate the **term structure component**: `(VIX3M - VIX) / VIX`. Positive = contango (normal, calm). Negative = backwardation (panic).
3. Combine: `regime_score = 0.6 * vix_component + 0.4 * ts_component`
4. Convert to signal: `signal = regime_score * 100`
5. Amplify extremes: VIX > 35 → floor signal at -80. VIX < 12 → floor signal at +60.

**Regime classification:**
- **Calm** (VIX < 20): Green light for risk-taking
- **Elevated** (VIX 20-30): Proceed with caution
- **Crisis** (VIX > 30 or term structure in backwardation): Reduce exposure

**Why it matters in simple terms:** The VIX is the market's "fear gauge." But the VIX level alone isn't enough — what matters is the *shape* of the volatility curve. In normal markets, longer-term volatility expectations are higher than short-term (contango). When the curve inverts (backwardation), it means traders are more scared of *right now* than of the future — classic panic behaviour. This combination of VIX level + term structure correctly identified every major equity drawdown since 2008.

### 6.3 Alternative Data Signals

These are **stock-specific signals** that provide insight about individual companies from non-traditional data sources.

#### Insider Transaction Signal

**Data source:** SEC EDGAR — Form 4 filings (free, no API key required)

**What it is:** Tracks when company insiders (CEOs, CFOs, directors, 10%+ shareholders) buy or sell their own company's stock. By law, they must report these transactions to the SEC within 2 business days.

**How the signal works:**
1. Fetch recent Form 4 filings from SEC EDGAR for each stock
2. Count buys vs. sells: `buy_ratio = buy_count / total_filing_count`
3. Calculate a **cluster score**: normalised filing count over the period. Many filings in a short window = coordinated insider activity.
4. Calculate **net sentiment**: `(buy_ratio - 0.5) * 200` → maps to -100 (all sells) to +100 (all buys)
5. Blend with cluster confidence: `signal = net_sentiment * (0.5 + 0.5 * cluster_confidence)`
6. Signal confidence scales with cluster strength: isolated single filings have low confidence; multiple insiders buying in the same week have high confidence.

**Why it matters in simple terms:** Insider buying is one of the most studied signals in finance. Meta-analyses by Jeng, Metrick & Zeckhauser (2003) show that stocks with insider buying outperform by 7-10% annually. The key insight is that insiders buy for only one reason: they believe the stock will go up. They sell for many reasons (diversification, taxes, estate planning), so selling is less informative.

**Cluster buying** — when multiple insiders buy in a short window — is an even stronger signal. If the CEO, CFO, and two directors all buy within the same week, they collectively know something about the company's prospects that the market doesn't.

**Structural uncorrelation:** Insiders often buy *against* the price trend. They buy when the stock has been beaten down (low momentum) because they know the fundamentals are better than the price reflects. This makes insider buying negatively correlated with momentum — the perfect diversifier.

#### Short Interest Signal

**Data source:** Yahoo Finance — shortPercentOfFloat, sharesShort, shortRatio

**What it is:** The percentage of a stock's tradable shares that have been borrowed and sold short by institutional investors. High short interest means professional investors are betting the stock will decline.

**How the signal works:**
1. Fetch short interest metrics for each stock
2. Score by severity:
   - < 2% short float: Normal, score 0 (neutral)
   - 2-5%: Elevated, score -20 to -40
   - 5-10%: High, score -40 to -70
   - > 10%: Extreme, score -70 to -100
3. Cross-sectional ranking: compare each stock's short interest to the universe average
4. Final signal: `70% absolute score + 30% cross-sectional z-score * 15`
5. Fixed confidence of 0.7 (short interest data is only reported bi-weekly)

**Why it matters in simple terms:** Short sellers are typically sophisticated institutional investors (hedge funds, prop desks) who do extensive research before shorting. When short interest is very high, it means these informed investors have collectively decided the stock is overvalued or heading for trouble. This is information that retail investors and even many long-only institutions don't have.

**Two-edged sword:** Very high short interest (>20% of float) can also set up "short squeezes" where rising prices force short sellers to buy back shares, creating a self-reinforcing rally. The system accounts for this by limiting the maximum bearish signal at -100 and letting the momentum/sentiment signals provide the squeeze context.

#### Seasonality Signal

**Data source:** Built-in calendar data (no external API needed)

**What it is:** A signal based on well-documented calendar patterns in equity returns. Certain months, and certain periods within months, have historically and persistently shown above- or below-average returns.

**Monthly bias table (historical S&P 500 averages, 1950-2024):**

| Month | Bias | Note |
|-------|------|------|
| January | +1.2% | "January effect" — especially strong for small caps |
| February | -0.2% | Weak |
| March | +1.0% | Moderate |
| April | +1.5% | One of the strongest months |
| May | -0.1% | "Sell in May" — start of weak period |
| June | -0.2% | Weak |
| July | +0.8% | Mid-summer bounce |
| August | -0.5% | Often volatile |
| September | -1.0% | **Worst month** historically |
| October | +0.5% | Turnaround, but often volatile |
| November | +1.5% | One of the strongest months |
| December | +1.3% | "Santa Claus rally" |

**How the signal works:**
1. Look up the current month's historical bias
2. Scale to signal range: `base_signal = monthly_bias / 0.015 * 60` (max ±60 from monthly)
3. Add **end-of-month boost** (+15) in the last 3 trading days (window dressing by fund managers)
4. Add **end-of-quarter boost** (+10) at the end of March, June, September, December
5. Signal is capped at [-100, +100]
6. Confidence is low: 0.3 (seasonality is weak but consistent)

**Why it matters in simple terms:** Seasonality is the purest form of diversification for a signal system. It's based on calendar dates, which have zero correlation with stock prices, sentiment, fundamentals, or any other signal. While weak on its own, it provides a small but reliable baseline signal that slightly tilts the system toward historically favourable periods. Most importantly, it's *always available* — even when API data is missing, the calendar always works.

### 6.4 Fundamental Regime Signals

These are **stock-specific signals** that capture aspects of company fundamentals that traditional factor scores miss.

#### Earnings Revisions Signal

**Data source:** Yahoo Finance — forward EPS estimates, trailing EPS

**What it is:** Measures whether analysts are revising their earnings estimates upward or downward. Rising estimates predict outperformance; falling estimates predict underperformance.

**How the signal works:**
1. For each stock, compare forward EPS to trailing EPS: `revision = (forward_eps - trailing_eps) / |trailing_eps|`
2. Rank all stocks cross-sectionally by revision magnitude
3. Compute z-score relative to the universe
4. Signal: `z_score * 30`, clamped to [-100, +100]
5. Confidence: 0.5 (this is a proxy using available data rather than direct revision data)

**Why it matters in simple terms:** Earnings revisions capture **forward-looking** information that backward-looking factors miss. A stock can have terrible trailing momentum (price has been falling) but positive earnings revisions (analysts are raising estimates). This divergence often precedes a price recovery. Chan, Jegadeesh & Lakonishok (1996) showed that earnings momentum is one of the most powerful predictors of stock returns.

**Structural uncorrelation with price momentum:** Price momentum looks at *past* returns. Earnings revisions look at *future* expectations. A stock can have negative momentum but positive revisions (analysts see improvement), or positive momentum but negative revisions (the rally is running out of fundamental support). This makes the two signals complementary rather than redundant.

#### Accruals Quality Signal

**Data it is based on:** Profit margin, ROE, debt-to-equity from Yahoo Finance

**What it is:** A proxy for the "accruals anomaly" discovered by Sloan (1996). When a company's reported earnings significantly exceed its operating cash flow (high accruals), the earnings are lower quality and future returns tend to be poor. Low accruals (cash earnings match reported earnings) indicate high-quality earnings.

**How the signal works:**
1. Compute an earnings quality proxy: `quality = profit_margin / |ROE|` — measures how efficiently reported earnings translate to margins
2. Apply a debt penalty: if debt_to_equity > 1.0, subtract `min(0.3, (D/E - 1.0) * 0.1)` — high leverage amplifies accruals risk
3. Negative profit margins get a fixed penalty of -0.5
4. Rank all stocks cross-sectionally by this quality proxy
5. Signal: `z_score * 25`, clamped to [-100, +100]
6. Confidence: 0.4 (lower confidence because this is a rough proxy)

**Why it matters in simple terms:** Some companies "manage" their earnings through accounting choices — recognising revenue early, deferring expenses, capitalising costs. These practices inflate reported earnings above what the business is actually generating in cash. The accruals anomaly shows that stocks with high accruals (big gap between reported and cash earnings) tend to underperform over the following year as the accounting tricks catch up with reality.

**Structural uncorrelation:** The accruals signal is uncorrelated with both momentum (past price performance says nothing about accounting quality) and value (a cheap stock can have either good or bad earnings quality). It adds a dimension that neither factor captures: the *reliability* of the financial numbers that value and quality scores are built on.

---

## 7. The Macro Risk Overlay

The Macro Risk Overlay is the "master fuse box" that sits above all agents and all strategies. It doesn't decide *what* to buy or sell — it decides *how much* to buy or sell. When multiple uncorrelated signals agree that risk is elevated, it scales down every agent's position sizes. When signals confirm safety, it allows slightly larger positions.

### How It Works

```
All Macro Data Sources
        │
        ▼
┌─────────────────────────────────────────┐
│         Build Signal Snapshot            │
│  credit_spread  ✓  signal: -45           │
│  vol_regime     ✓  signal: -30           │
│  yield_curve    ✓  signal: +10           │
│  seasonality    ✓  signal: +48 (April)   │
│  insider_bread  ✓  signal: +20           │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│     Compute Weighted Composite           │
│  (re-normalise weights for available     │
│   signals; missing signals excluded)     │
│                                          │
│  credit:   -45 * 0.30 = -13.50          │
│  vol:      -30 * 0.30 =  -9.00          │
│  yield:    +10 * 0.20 =  +2.00          │
│  season:   +48 * 0.10 =  +4.80          │
│  insider:  +20 * 0.10 =  +2.00          │
│  ─────────────────────────               │
│  composite = -13.70                      │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│     Convert to Risk Scale Factor         │
│                                          │
│  composite = -13.70                      │
│  → bearish regime                        │
│  → scale = 1.0 + (-13.70/100) * 0.75    │
│  → scale = 0.8972                        │
│                                          │
│  All positions reduced by ~10%           │
└─────────────────────────────────────────┘
```

### Signal Weights

| Signal | Weight | Rationale |
|--------|--------|-----------|
| **Credit Spread** | 30% | Most reliable leading indicator of equity risk |
| **Volatility Regime** | 30% | Real-time measure of fear and panic |
| **Yield Curve** | 20% | Longer-term recession predictor |
| **Seasonality** | 10% | Weak but always available |
| **Insider Breadth** | 10% | Aggregate insider conviction across market |

### The Asymmetric Scale

The risk scale factor is deliberately **asymmetric** — it cuts risk more aggressively than it adds risk:

```
Composite: -100  -75  -50  -25   0   +25  +50  +75  +100
Scale:      0.25 0.44 0.63 0.81  1.0  1.06 1.13 1.19 1.25
```

- At composite -100 (maximum danger): positions reduced by **75%** (scale 0.25)
- At composite +100 (maximum safety): positions increased by only **25%** (scale 1.25)

**Why asymmetric?** Because losses are mathematically asymmetric. A 50% loss requires a 100% gain to recover. Cutting risk aggressively when danger signals appear protects more capital than the small upside cost of being slightly too conservative in good times.

### Minimum Signal Requirement

The overlay requires at least **2 of 5 signals** to be available before it acts. If only one signal (or none) is available, the overlay returns a neutral scale of 1.0 (no adjustment). This prevents a single noisy data source from triggering portfolio-wide changes.

Since the seasonality signal is always available (it's calendar-based), the overlay really just needs one additional data source to activate.

### Regime Labels

Based on the composite score, the overlay assigns a human-readable regime label:

| Composite Score | Label | What it means |
|----------------|-------|---------------|
| < -40 | `high_risk` | Multiple signals confirm danger — maximum risk reduction |
| -40 to -15 | `elevated_risk` | Some concern — moderate risk reduction |
| -15 to +30 | `normal` | Business as usual — no adjustment |
| > +30 | `low_risk` | All signals confirm safety — slight risk increase |

### Warning System

The overlay generates human-readable warnings for extreme conditions:

- Credit spread signal < -50: *"Credit spreads widening significantly — credit markets pricing risk"*
- Vol regime signal < -50: *"Elevated volatility regime — VIX elevated or term structure inverted"*
- Yield curve signal < -30: *"Yield curve flat or inverted — recession risk elevated"*
- Composite < -60: *"CRITICAL: Multiple macro signals confirm high risk — position sizes reduced to minimum"*
- Composite > +40: *"Macro conditions favourable — all signals confirm low risk environment"*

### Graceful Degradation

Every data source can fail — the FRED API can go down, Yahoo Finance can throttle requests, SEC EDGAR can be slow. The overlay handles this gracefully:

1. Each signal has an `available` flag. If data fetching fails, the signal is marked unavailable.
2. Only available signals are included in the composite calculation.
3. Weights are **re-normalised** among available signals so they still sum to 1.0.
4. If fewer than 2 signals are available, the overlay returns neutral (1.0).
5. Seasonality is always available as a fallback (it's purely calendar-based).

This means the system never goes blind — even if all external APIs fail, it has at least one signal (seasonality) and returns a mild directional tilt based on the current month.

---

## 8. Risk Management

Every strategy passes through multiple layers of risk management before any trades are placed. These are applied automatically, regardless of what the strategy's signals suggest.

### 8.1 Position-Level Risk Controls

**Maximum position size:** Each position is capped at a strategy-specific maximum (typically 5-10% of portfolio). Even if a signal is extremely strong (+100), the position won't exceed this cap.

| Strategy | Max Position | Rationale |
|----------|-------------|-----------|
| Momentum | 5% | Diversified, many positions |
| Quality Value | 5% | Concentrated but conservative |
| Quality Momentum | 5% | Balanced approach |
| Dividend Growth | 5% | Income diversification |
| Trend Following | 10% | Fewer positions, higher conviction |
| Short-Term Reversal | 3% | Many small positions |
| Statistical Arbitrage | 5% | Pairs require balance |
| Volatility Premium | 5% | Low-vol stocks, moderate sizing |

**Stop-losses:** Set automatically using ATR (Average True Range) multiples:
- Long positions: `stop = entry_price - ATR * multiplier`
- Short positions: `stop = entry_price + ATR * multiplier`
- Multiplier ranges from 1.5x (tight, for reversal) to 3.0x (wide, for dividends)

**Take-profit targets:** Set using ATR multiples (typically 3x ATR for longs, creating a 1.5:1 reward-to-risk ratio with 2x ATR stops).

**Position aging:** Each position has a maximum holding period. When a position exceeds this horizon, it's automatically exited. This prevents "zombie positions" that are neither stopped out nor profitable enough to exit.

### 8.2 Portfolio-Level Risk Controls

**Sector concentration:** No more than 30% of the portfolio can be in any single sector. If a strategy wants to buy 8 tech stocks at 5% each (40% tech), all tech positions are proportionally scaled down to fit within the 30% cap.

**Gross exposure:** Total long weight + total short weight cannot exceed the strategy's leverage limit (1.0x for most strategies, 1.5x for trend following). If exceeded, all positions are scaled down proportionally.

**Correlation guard:** Before finalising positions, the system checks pairwise return correlations using the last 60 days of price history. If a new position's correlation with any existing position exceeds 0.7, it's dropped. Positions are processed in signal-strength order, so the strongest signals are kept and weaker but correlated candidates are filtered out.

### 8.3 Volatility-Based Sizing

Most strategies use **volatility-scaled position sizing**. The idea is simple: give each position an equal chance to contribute to portfolio risk, regardless of how volatile the underlying stock is.

```
weight = (target_portfolio_volatility / stock_annualised_volatility) * base_weight
```

A stock with 40% annualised volatility in a portfolio targeting 15% gets its weight reduced to `15/40 = 0.375x` the base weight. A stock with 10% volatility gets `15/10 = 1.5x` the base weight (still capped at max position size).

This creates a natural **risk parity** effect — every position contributes roughly the same amount of risk to the portfolio, preventing one volatile stock from dominating.

### 8.4 Hysteresis (Anti-Churn)

Strategies apply **hysteresis bands** to prevent unnecessary trading. Currently-held positions get a "stickiness bonus" to their signal strength:

- The bonus is added to the signal when comparing held positions against new candidates
- A new candidate must outperform the incumbent by more than the hysteresis band to replace it
- Direction flips (long to short) require extra conviction: the new signal must exceed 2x the band

Band widths vary by strategy:
- Short-Term Reversal: 3.0 (low, because turnover is expected)
- Trend Following: 5.0 (moderate)
- Statistical Arbitrage: 4.0 (moderate)
- Volatility Premium: 6.0 (high, because it's a slow strategy)
- Cross-Sectional Factor: 5.0 (moderate)

### 8.5 Drawdown Circuit Breaker

Before any strategy runs, the engine checks if the agent's portfolio has hit its maximum drawdown limit (default: 20%). If unrealised losses as a percentage of allocated capital exceed this threshold:

1. Normal strategy execution is **halted entirely**
2. **Sell orders are generated for all open positions** (full liquidation)
3. The regime is set to `circuit_breaker`
4. The agent won't trade again until manually re-enabled

This is the nuclear option — it protects against catastrophic losses when everything else has failed.

### 8.6 Cash Constraint

The engine checks available cash before recommending new positions. If new buy recommendations would exceed the agent's cash balance:

1. Only **new entries** are affected (existing positions are not touched)
2. New entry weights are **proportionally scaled down** to fit within available cash
3. The system logs the scaling factor for transparency

This prevents the system from recommending trades the agent can't afford.

---

## 9. The Execution Pipeline

Here's the complete sequence of events from data collection to trade execution, in the order they actually happen:

### 9.1 Nightly Data Pipeline

These jobs run sequentially in the background (typically overnight):

```
1. market_data_job     → Fetches prices, fundamentals, technicals for all stocks
2. sentiment_job       → Runs FinBERT on news, fetches StockTwits, computes velocity
3. macro_data_job      → Fetches FRED data, VIX regime, insider filings, short interest
4. factor_scoring_job  → Calculates 5-factor scores for all stocks
5. strategy_execution  → Runs all agents through the engine
```

### 9.2 Strategy Execution Steps (per agent)

When `strategy_execution_job` runs, it calls `StrategyEngine.execute_for_agent()` for each active agent. Here's what happens inside:

**Step 0: Safety checks**
- Drawdown circuit breaker: Is the portfolio down more than the max? If yes, liquidate everything and stop.
- Rebalance frequency gate: Has this agent already rebalanced recently? If yes, skip this run.

**Step 1: Resolve configuration**
- Map agent's strategy type (e.g., "momentum") to a strategy preset
- Apply agent-specific overrides (universe, sentiment weight, risk parameters)

**Step 2: Gather data**
- Market data: prices, fundamentals, moving averages, ATR (from database or pre-fetched)
- Sentiment data: news_sentiment, social_sentiment, velocity (from database)

**Step 3: Enrich sentiment with temporal features**
- The `TemporalSentimentAnalyzer` queries the `sentiment_history` table for the last 30 days
- Computes streak, trend slope, persistence, and breakout flags for each stock
- These features power Layers 6 and 7 of the integration engine

**Step 4: Run sentiment-factor integration**
- The `SentimentFactorIntegrator` runs all 7 layers
- Produces an `integrated_composite` score (0-100) for each stock
- These scores are injected into market_data so the strategy can use them for ranking

**Step 5: Execute strategy**
- The strategy-level sentiment overlay is **disabled** (set to `SentimentMode.DISABLED`) because the 7-layer integrator already handles sentiment
- The strategy's signal generators produce raw signals
- The strategy's portfolio constructor converts signals to position recommendations
- The strategy's risk management pass applies position caps, sector limits, stops, and correlation filters

**Step 6: Post-processing**
- **Cash constraint**: Scale down new entries to fit within available cash
- **Macro Risk Overlay**: Compute the overlay from credit spreads, VIX, yield curve, seasonality, and insider breadth. Multiply ALL position weights by the `risk_scale_factor` (0.25 to 1.25).

**Step 7: Position diffing**
- Compare recommended positions against current holdings
- Generate order actions: buy (new entry), sell (exit), increase, decrease, or hold
- Compute current weights from shares * price / allocated_capital

**Step 8-10: Safety exits**
- Stop-loss check: Any held position whose price has breached its stop generates a sell action
- Take-profit check: Any held position that has reached its target generates a sell action
- Position aging: Any position held longer than its max horizon generates a sell action
- These override any hold/increase recommendations from the strategy

**Step 11: Trade thesis generation**
- Each buy/increase action is enriched with a human-readable trade thesis
- Includes strategy name, integrated score, signal strength, regime, weight, entry price, stop, target, and time horizon
- This powers the UI's trade explanation feature

### 9.3 Order Flow

```
ExecutionResult (positions + order actions)
        │
        ▼
   Broker Layer (Alpaca)
        │
        ├── Buy orders  → Market/limit orders via Alpaca API
        ├── Sell orders → Market orders via Alpaca API
        └── Hold/decrease → Adjust or no action
```

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| **Agent** | A user-created autonomous trading bot that follows a specific strategy |
| **ATR** | Average True Range — measures daily price volatility over 14 days |
| **Backwardation** | When short-term VIX exceeds long-term VIX (VIX > VIX3M). Signals panic. |
| **Circuit Breaker** | Automatic portfolio liquidation when drawdown exceeds the configured maximum |
| **Composite Score** | Weighted combination of factor scores; basis for stock ranking |
| **Contango** | When long-term VIX exceeds short-term VIX (VIX3M > VIX). Normal, calm market state. |
| **Convergence** | When factor signals and sentiment signals agree in direction |
| **Cross-Sectional** | Comparing stocks relative to each other (ranking), as opposed to time-series (absolute) |
| **Drawdown** | Peak-to-trough decline in portfolio value, expressed as a percentage |
| **Factor** | A measurable stock characteristic (momentum, value, quality, etc.) that predicts returns |
| **FRED** | Federal Reserve Economic Data — free API for macroeconomic data |
| **Gross Exposure** | Total long weight + total short weight. Measures total portfolio activity. |
| **Hysteresis** | A "stickiness" band that prevents unnecessary position changes from small signal fluctuations |
| **Integrated Composite** | The final 0-100 score after blending factors + sentiment through 7 layers |
| **Market Neutral** | A portfolio where total long exposure equals total short exposure (zero net market beta) |
| **Net Exposure** | Total long weight - total short weight. Measures directional market bet. |
| **OAS** | Option-Adjusted Spread — the yield premium of corporate bonds over treasuries |
| **Overlay** | A system that modifies position sizes without changing position direction |
| **Percentile Rank** | Where a stock falls in the universe distribution (0 = worst, 100 = best) |
| **Regime** | The current market state (risk-on, neutral, risk-off) detected from aggregate sentiment |
| **Risk Parity** | Sizing positions so each contributes equal risk to the portfolio |
| **Risk Scale Factor** | The multiplier (0.25 to 1.25) from the Macro Risk Overlay applied to all positions |
| **Signal** | A normalised (-100 to +100) data point about a stock from any source |
| **Spread** | The difference between two related values (e.g., 10Y yield - 2Y yield) |
| **Time-Series** | Analysing a single stock over time (e.g., "is the stock trending up?") |
| **VIX** | CBOE Volatility Index — measures expected S&P 500 volatility over the next 30 days |
| **Z-Score** | Number of standard deviations from the mean. Z=2 means 2 standard deviations above average. |

---

*This document was generated from the AgentFund codebase. For implementation details, see the source files in `backend/core/strategies/`, `backend/core/sentiment_integration.py`, `backend/core/macro_risk_overlay.py`, and `backend/core/engine.py`.*
