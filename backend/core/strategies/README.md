# AgentFund Strategy Framework

A modular, extensible quantitative strategy framework with sentiment integration.

## Overview

The strategy framework provides:
- **9 pre-configured strategies** (4 original + 5 advanced)
- **Modular signal generators** that can be composed into custom strategies
- **5 sentiment integration modes** for enhanced signal quality
- **Risk management** with position sizing and stop-loss support

## Available Strategies

### Original Strategies (Beginner-Friendly)

| Strategy | Type | Description |
|----------|------|-------------|
| Momentum | Factor | Pure price momentum with trend following |
| Quality Value | Factor | Value investing with quality filters |
| Quality Momentum | Factor | Momentum stocks filtered by quality metrics |
| Dividend Growth | Factor | Dividend-paying stocks with growth potential |

### Advanced Strategies (Power User)

| Strategy | Type | Description |
|----------|------|-------------|
| Trend Following | Time-Series | Systematic trend capture across timeframes |
| Short-Term Reversal | Mean Reversion | Profits from short-term price overreactions |
| Statistical Arbitrage | Pairs/Relative | Market-neutral relative value strategies |
| Volatility Premium | Vol Selling | Harvests volatility risk premium |

---

## Strategy Details & Benefits

### 1. Momentum Strategy

**What it does:** Buys stocks with strong recent price performance, expecting trends to continue.

**Benefits:**
- Strong historical risk-adjusted returns across markets and time periods
- Works across asset classes (equities, commodities, currencies)
- Simple to understand and explain to stakeholders
- Captures behavioral biases (underreaction, herding)

**Sentiment Enhancement (FILTER mode):**
- Only enters momentum positions when sentiment is positive
- Avoids "momentum crashes" where crowded trades reverse sharply
- Sentiment acts as a timing filter to reduce drawdowns

```python
from core.strategies import momentum_strategy

config = momentum_strategy(
    universe=my_stocks,
    lookback_days=252,
    top_percentile=10,
    sentiment_mode=SentimentMode.FILTER
)
```

---

### 2. Quality Value Strategy

**What it does:** Combines value metrics (P/E, P/B) with quality filters (ROE, debt ratios) to find undervalued, high-quality companies.

**Benefits:**
- Margin of safety from buying below intrinsic value
- Quality filter avoids "value traps" (cheap stocks that stay cheap)
- Strong long-term compounding potential
- Lower volatility than pure value strategies

**Sentiment Enhancement (CONFIRMATION mode):**
- Requires sentiment to not be deteriorating before entry
- Helps identify turnaround opportunities (improving sentiment + cheap price)
- Avoids catching falling knives where sentiment is collapsing

```python
from core.strategies import quality_value_strategy

config = quality_value_strategy(
    universe=my_stocks,
    value_weight=0.5,
    quality_weight=0.5,
    sentiment_mode=SentimentMode.CONFIRMATION
)
```

---

### 3. Quality Momentum Strategy

**What it does:** Combines momentum (price trends) with quality metrics to find trending stocks that are fundamentally sound.

**Benefits:**
- Momentum provides timing signal
- Quality filter provides fundamental safety
- Avoids low-quality "lottery ticket" stocks that spike and crash
- Better risk-adjusted returns than pure momentum

**Sentiment Enhancement (ALPHA mode):**
- Sentiment becomes a third factor in the signal blend
- Sentiment velocity confirms momentum is sustainable
- Triple confirmation: price momentum + quality + positive sentiment

```python
from core.strategies import quality_momentum_strategy

config = quality_momentum_strategy(
    universe=my_stocks,
    momentum_weight=0.4,
    quality_weight=0.4,
    sentiment_weight=0.2,
    sentiment_mode=SentimentMode.ALPHA
)
```

---

### 4. Dividend Growth Strategy

**What it does:** Invests in dividend-paying stocks with consistent dividend growth and strong fundamentals.

**Benefits:**
- Regular income generation through dividends
- Dividend compounding over time (reinvestment)
- Defensive characteristics in down markets
- Quality companies tend to have sustainable dividends

**Sentiment Enhancement (FILTER mode):**
- Avoids dividend stocks with deteriorating sentiment
- Protects against dividend cuts (often preceded by negative news)
- Sentiment filter catches management issues before dividend announcements

```python
from core.strategies import dividend_growth_strategy

config = dividend_growth_strategy(
    universe=my_stocks,
    min_yield=0.02,
    quality_weight=0.5,
    sentiment_mode=SentimentMode.FILTER
)
```

---

### 5. Trend Following Strategy

**What it does:** Systematic strategy that goes long in uptrends and short (or flat) in downtrends using moving average crossovers.

**Benefits:**
- "Crisis alpha" - tends to profit during market crashes
- Uncorrelated to traditional long-only strategies
- Systematic and emotionless execution
- Works across multiple asset classes

**Sentiment Enhancement (RISK_ADJUSTMENT mode):**
- Reduces position size when sentiment diverges from price trend
- If trend is up but sentiment is negative, smaller position
- Protects against trend reversals that sentiment detects early

```python
from core.strategies import trend_following_strategy

config = trend_following_strategy(
    universe=my_stocks,
    short_window=20,
    long_window=60,
    sentiment_mode=SentimentMode.RISK_ADJUSTMENT
)
```

---

### 6. Short-Term Reversal Strategy

**What it does:** Bets that short-term price movements will reverse, buying recent losers and selling recent winners.

**Benefits:**
- High Sharpe ratio potential from capturing mean reversion
- Market-neutral when properly constructed
- Profits from short-term noise and overreaction
- Works best in liquid, efficient markets

**Sentiment Enhancement (CONFIRMATION mode):**
- Only trades reversals where sentiment is also reverting
- If price dropped but sentiment is improving, stronger buy signal
- Avoids reversals that are actually the start of a new trend

```python
from core.strategies import short_term_reversal_strategy

config = short_term_reversal_strategy(
    universe=my_stocks,
    lookback_days=5,
    zscore_threshold=2.0,
    sentiment_mode=SentimentMode.CONFIRMATION
)
```

---

### 7. Statistical Arbitrage Strategy

**What it does:** Identifies pairs or groups of related stocks and trades their relative value divergences.

**Benefits:**
- Market-neutral (hedged against broad market moves)
- Captures relative value opportunities
- Low correlation to market direction
- Can profit in any market environment

**Sentiment Enhancement (ALPHA mode):**
- Sentiment divergence between pairs adds to spread signal
- If fundamentally similar stocks have diverging sentiment, trade the spread
- Sentiment provides additional edge beyond pure price statistics

```python
from core.strategies import statistical_arbitrage_strategy

config = statistical_arbitrage_strategy(
    universe=my_stocks,
    zscore_entry=2.0,
    zscore_exit=0.5,
    sentiment_mode=SentimentMode.ALPHA
)
```

---

### 8. Volatility Premium Strategy

**What it does:** Harvests the volatility risk premium by systematically selling volatility (or avoiding high-vol periods).

**Benefits:**
- Earns persistent volatility risk premium
- Lower drawdowns than buy-and-hold
- Defensive characteristics
- Profits from volatility mean reversion

**Sentiment Enhancement (FILTER mode):**
- Exits positions when extreme negative sentiment signals volatility spike
- Sentiment often leads volatility (fear precedes vol expansion)
- Protects against tail events that sentiment detects early

```python
from core.strategies import volatility_premium_strategy

config = volatility_premium_strategy(
    universe=my_stocks,
    vol_lookback=20,
    vol_target=0.15,
    sentiment_mode=SentimentMode.FILTER
)
```

---

## Sentiment Integration Modes

The framework supports 5 modes for integrating sentiment into any strategy:

| Mode | Description | Best For |
|------|-------------|----------|
| `DISABLED` | No sentiment integration | Backtesting, pure quant strategies |
| `FILTER` | Only trade when sentiment confirms | Risk reduction, avoiding drawdowns |
| `ALPHA` | Sentiment as additional signal factor | Multi-factor strategies |
| `RISK_ADJUSTMENT` | Adjust position size by sentiment | Trend following, position sizing |
| `CONFIRMATION` | Require sentiment alignment | Reversal strategies, entry timing |

### Usage Example

```python
from core.strategies import SentimentMode, SentimentConfig

# Configure sentiment integration
sentiment_config = SentimentConfig(
    mode=SentimentMode.ALPHA,
    weight=0.3,                    # 30% weight in signal blend
    min_score=-50,                 # Minimum acceptable sentiment
    lookback_days=7,               # Sentiment lookback window
    sources=["news", "social"],    # Data sources to use
)
```

---

## Quick Start

### Using Presets

```python
from core.strategies import get_preset, list_presets, StrategyRegistry

# List available presets
print(list_presets())
# ['momentum', 'quality_value', 'quality_momentum', 'dividend_growth',
#  'trend_following', 'short_term_reversal', 'statistical_arbitrage',
#  'volatility_premium']

# Get a preset configuration
config = get_preset("momentum", universe=["AAPL", "MSFT", "GOOGL"])

# Create strategy instance
strategy = StrategyRegistry.create(config)

# Execute strategy
output = await strategy.execute(
    market_data=market_data,
    sentiment_data=sentiment_data,
    current_positions=[]
)

print(output.signals)      # Generated signals
print(output.positions)    # Recommended positions
```

### Creating Custom Strategies

```python
from core.strategies import (
    BaseStrategy,
    StrategyConfig,
    StrategyType,
    SignalCombiner,
    TimeSeriesMomentumSignal,
    QualitySignal,
    NewsSentimentSignal,
)

# Compose signals
signals = [
    (TimeSeriesMomentumSignal(lookback_days=126), 0.4),
    (QualitySignal(), 0.4),
    (NewsSentimentSignal(), 0.2),
]
combiner = SignalCombiner(signals)

# Create custom config
config = StrategyConfig(
    name="My Custom Strategy",
    strategy_type=StrategyType.CUSTOM,
    universe=my_universe,
    signal_generators=[combiner],
    sentiment=SentimentConfig(mode=SentimentMode.ALPHA, weight=0.2),
)

# Instantiate and run
strategy = StrategyRegistry.create(config)
output = await strategy.execute(market_data, sentiment_data, [])
```

---

## Signal Generators

Available signal generators for building custom strategies:

### Price/Momentum Signals
- `TimeSeriesMomentumSignal` - Absolute momentum (trend following)
- `CrossSectionalMomentumSignal` - Relative momentum (cross-sectional ranking)

### Fundamental Signals
- `ValueSignal` - P/E, P/B, EV/EBITDA metrics
- `QualitySignal` - ROE, debt ratios, earnings stability
- `DividendYieldSignal` - Dividend yield and growth

### Sentiment Signals
- `NewsSentimentSignal` - News article sentiment analysis
- `SocialSentimentSignal` - Social media sentiment
- `SentimentVelocitySignal` - Rate of sentiment change

### Statistical Signals
- `RealizedVolatilitySignal` - Historical volatility measurement
- `ShortTermReversalSignal` - Mean reversion signals
- `ZScoreSignal` - Statistical deviation from mean

### Combining Signals

```python
from core.strategies import SignalCombiner

combiner = SignalCombiner([
    (TimeSeriesMomentumSignal(), 0.5),
    (QualitySignal(), 0.3),
    (NewsSentimentSignal(), 0.2),
])

# Generates blended signal from all components
signals = await combiner.generate(symbols, market_data)
```

---

## Architecture

```
core/strategies/
├── __init__.py          # Public API exports
├── base.py              # Base classes and abstractions
├── signals.py           # Signal generator implementations
├── implementations.py   # Strategy implementations
├── presets.py           # Pre-configured strategy presets
└── README.md            # This documentation
```

### Key Abstractions

- **SignalGenerator**: Produces normalized signals (-100 to +100)
- **BaseStrategy**: Abstract base with execute() pipeline
- **StrategyRegistry**: Factory for creating strategy instances
- **StrategyConfig**: Configuration dataclass for strategies
