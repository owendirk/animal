# Animal Coin Trend Research

Systematic trend-following research for an **animal coin / meme-adjacent crypto futures basket** using Binance USD-M futures 4h kline data.

The research universe:

| Name | Binance USD-M Symbol |
|---|---|
| DOGE | `DOGEUSDT` |
| SHIB | `1000SHIBUSDT` |
| PEPE | `1000PEPEUSDT` |
| BONK | `1000BONKUSDT` |
| WIF | `WIFUSDT` |
| POPCAT | `POPCATUSDT` |
| PENGU | `PENGUUSDT` |
| UNI | `UNIUSDT` |

> Note: UNI is only loosely animal/meme-adjacent. It should be treated as a control or benchmark candidate in later research, not necessarily as a pure animal coin.

---

## Repository Contents

```text
animal.py
animal001.ipynb
animal0012.ipynb
```

### `animal.py`

Downloads Binance Vision USD-M futures daily 4h kline ZIP files, unzips them, and combines each symbol into its own CSV.

Run:

```bash
python animal.py --start 2019-09-01 --outdir animal_4h_csv
```

Expected output:

```text
animal_4h_csv/
    DOGEUSDT_4h.csv
    POPCATUSDT_4h.csv
    PENGUUSDT_4h.csv
    1000PEPEUSDT_4h.csv
    WIFUSDT_4h.csv
    1000SHIBUSDT_4h.csv
    1000BONKUSDT_4h.csv
    UNIUSDT_4h.csv
```

### `animal001.ipynb`

Baseline research notebook.

Focus:

- animal index construction
- equal-weight vs inverse-volatility basket construction
- statistical trendiness tests
- EWMA trend-following baseline
- long/flat trend strategy
- forecast-scaled trend strategy
- p-value tests
- year-by-year robustness
- leave-one-coin-out dependency checks

### `animal0012.ipynb`

Improved research notebook.

Focus:

- equal-weight signal vs inverse-volatility signal
- capped equal-weight execution
- trend ensemble
- breadth filters
- volume confirmation
- DOGE leader filters
- component-level top-N trend
- robustness grids
- p-values
- year-by-year checks
- leave-one-coin-out checks

---

# Research Summary

## 1. Animal Index Construction

The first notebook built an animal/meme basket from DOGE, SHIB, PEPE, BONK, WIF, POPCAT, PENGU, and UNI.

Two primary index methods were tested:

1. Equal-weight index
2. Inverse-volatility index

### Key Finding

The equal-weight index strongly outperformed the inverse-volatility index.

Approximate `animal001` results:

| Index | CAGR | Sharpe-like |
|---|---:|---:|
| Equal-weight | ~130% | ~1.23 |
| Inverse-volatility | ~35% | ~0.77 |

### Interpretation

Inverse-volatility weighting is usually useful for controlling risk, but in meme coins it can remove exposure to the high-volatility assets that produce the largest right-tail returns.

In this universe, volatility is both risk and the source of upside convexity.

Working interpretation:

```text
Use equal-weight or capped equal-weight for signal/exposure.
Use portfolio-level volatility targeting for risk control.
Avoid relying only on inverse-volatility weighting.
```

---

## 2. Evidence of Trendiness

`animal001.ipynb` tested whether past returns predict future returns using statistical tests such as:

- HAC OLS
- Spearman correlation
- horizon-based trendiness tests

### Key Finding

The animal basket showed evidence of trendiness, especially across the 3-day to 30-day lookback / forward-return horizons.

Several tests produced candidate evidence with:

```text
p < 0.05
```

One notable area was the 30-day lookback vs 3-day forward horizon on the inverse-volatility index, which showed strong correlation.

### Interpretation

The animal coin basket appears to have systematic trend-following properties. It is not merely random noise, although this evidence still requires out-of-sample validation.

---

## 3. Baseline Trend Strategy Performance

`animal001.ipynb` tested multi-speed EWMA trend-following using:

```text
16 / 64
32 / 128
64 / 256
```

The main comparison was:

1. Buy-and-hold inverse-volatility basket
2. Long/flat trend strategy
3. Forecast-scaled trend strategy

Approximate results:

| Metric | Buy-and-Hold Inv-Vol | Trend Long/Flat | Trend Forecast-Scaled |
|---|---:|---:|---:|
| Sharpe-like | ~0.78 | ~1.33 | ~1.47 |
| Max Drawdown | ~-87.5% | ~-38.1% | ~-19.8% |
| CAGR | ~35.5% | ~50.7% | ~37.5% |

### Main Finding

The trend strategies dramatically reduced drawdown while improving risk-adjusted returns.

The most important result was risk transformation:

```text
Raw animal exposure:
    high return, very high volatility, catastrophic drawdowns

Trend-filtered animal exposure:
    still strong return, much lower drawdown, better risk-adjusted profile
```

The forecast-scaled strategy reduced max drawdown to around -20%, compared with nearly -90% for buy-and-hold.

---

## 4. Year-by-Year Robustness

The trend strategy performed especially well during weak or crashing markets.

Approximate findings from `animal001.ipynb`:

| Year / Regime | Buy-and-Hold | Trend Strategy Behavior |
|---|---:|---|
| 2021 bull market | very strong positive returns | captured a large part of the upside |
| 2022 bear market | around -34% | much smaller loss |
| 2024 bull market | very strong positive returns | captured meaningful upside |
| 2025 crash year | around -72% | stayed defensive and finished roughly flat to positive |

### Interpretation

The trend strategy behaves like a regime switch:

```text
Risk-on meme season:
    participates in upside

Bear / crash regime:
    reduces exposure and protects capital
```

This is the core edge found in the baseline notebook.

---

## 5. Critical Vulnerability: DOGE Dependency

`animal001.ipynb` included leave-one-coin-out tests.

### Key Finding

Removing DOGE materially reduced performance.

Approximate observation:

```text
Full basket trend Sharpe: ~1.5
Without DOGE:            ~0.78
```

### Interpretation

DOGE is not just one component. It appears to act as a sector leader or meme-beta indicator.

This is a vulnerability, but also a useful signal.

Research implication:

```text
DOGE should be treated as a leader/regime feature.
Do not ignore DOGE dependency.
Do not assume the strategy is equally strong without DOGE.
```

---

# `animal0012` Findings

`animal0012.ipynb` tested improvements suggested by the baseline results.

## 1. Equal-Weight Signal and Execution Won

The signal/execution experiment compared combinations such as:

- equal-weight signal -> equal-weight execution
- equal-weight signal -> capped equal-weight execution
- equal-weight signal -> inverse-vol execution
- inverse-vol signal -> inverse-vol execution

### Key Finding

Equal-weight signal and equal-weight/capped equal-weight execution were best.

Approximate result from the deep dive:

```text
EW Signal + EW Execution Sharpe-like: ~1.51
```

### Interpretation

Simple weighting worked better than complex inverse-volatility weighting.

Reason:

Meme-coin returns are highly fat-tailed. Inverse-volatility weighting can reduce exposure to the strongest movers too early.

Working conclusion:

```text
Signal:    equal-weight animal index
Execution: equal-weight or capped equal-weight basket
Risk:      portfolio-level volatility targeting
```

---

## 2. Trend Ensemble Improved Robustness

`animal0012.ipynb` added a trend ensemble using multiple trend definitions:

1. EWMA crossover
2. Time-series momentum
3. Donchian / channel breakout
4. Rolling regression slope / trend t-stat
5. Drawdown recovery trend

### Key Finding

The ensemble approach produced a denser cluster of good-performing configurations than a single EWMA setup.

The strongest configurations often used:

```text
Forecast: ensemble mean
Entry threshold: around 10.0
```

### Interpretation

This reduces dependence on one moving-average pair and better captures different meme-market trend shapes:

- smooth trends
- explosive breakouts
- recovery rallies
- broad sector momentum

---

## 3. Breadth Filter Was Important

A major improvement came from requiring basket participation.

Strong configurations commonly used:

```text
breadth_pct_positive_7d > 0.50
```

### Interpretation

The animal basket trend is more reliable when at least half the basket is participating.

This helps avoid buying a DOGE-only or single-coin pump where the broader meme sector is weak.

---

## 4. DOGE Leader Filter Was Important

Top configurations frequently used:

```text
DOGE trend positive
```

### Interpretation

DOGE appears to act as the macro/leader signal for the meme sector.

Useful rule:

```text
Only take animal basket trend exposure when DOGE trend is positive.
```

This converts DOGE dependency into a regime filter rather than treating it only as a weakness.

---

## 5. Crash Protection Was the Biggest Edge

The most important `animal0012` finding was resilience during the 2025 crash.

Approximate deep-dive results:

| Year | Buy & Hold Capped EW | Best Filtered Trend | Delta |
|---|---:|---:|---:|
| 2021 | +439.2% | +375.4% | -63.8% |
| 2022 | -34.3% | -10.8% | +23.5% |
| 2025 | -73.0% | +11.9% | +84.9% |

### Interpretation

The strategy gives up some upside in extreme bull markets but avoids catastrophic drawdowns during crashes.

This makes the strategy function like a volatility tail-hedge or regime filter.

---

## 6. Drawdown Reduction

The raw capped/equal-weight animal index had extremely high volatility and drawdowns.

Approximate finding:

```text
Raw Equal/Capped Animal Basket:
    max drawdown: ~-87% to -88%
    annualized volatility: ~140%

Best ensemble-filtered trend configs:
    max drawdown: ~-19% to -23%
```

### Interpretation

Without a trend filter, the animal index is difficult to hold as a portfolio allocation.

With a trend filter, the same universe becomes more tradable.

---

## 7. Turnover Is the Main Live-Trading Challenge

The best filtered strategies had annual turnover around:

```text
~95x annual turnover
```

### Interpretation

Execution quality matters.

The strategy must survive:

- fees
- spread
- slippage
- Binance futures fee tier assumptions
- liquidity differences across symbols
- bad fills during high-volatility meme moves

This is the main research-to-live gap.

---

# Current Recommended Strategy Candidate

Based on `animal001.ipynb` and `animal0012.ipynb`, the current research champion is:

```text
Signal index:
    Equal-weight animal index

Forecast:
    Full trend ensemble mean

Entry threshold:
    forecast > 10.0

Filters:
    breadth_pct_positive_7d > 0.50
    DOGE trend positive

Execution:
    Capped equal-weight basket

Max component weight:
    25% per coin

Risk:
    Portfolio-level volatility targeting

Costs:
    Must survive at least 10 bps base cost
    Should be tested at 25 bps and 50 bps
```

---

# Interpretation

The research suggests that animal/meme coins can be transformed from:

```text
high-return but near-uninvestable drawdown profile
```

into:

```text
systematic trend-following exposure with much better risk control
```

The strategy appears to work primarily by:

1. Participating during broad meme risk-on regimes
2. Avoiding or reducing exposure during bear/crash regimes
3. Using DOGE as a sector leader
4. Requiring breadth confirmation
5. Using equal-weight exposure to preserve right-tail upside

The edge is less about forecasting every 4h bar and more about regime switching.

---

# What Is Supported vs Not Proven

## Supported by current research

- Equal-weight exposure is better than inverse-volatility for this universe.
- The basket has measurable trendiness.
- Trend-following reduces catastrophic drawdowns.
- Ensemble trend signals are more robust than single EWMA-only signals.
- Breadth confirmation improves signal quality.
- DOGE is a useful meme-sector leader signal.
- Best configurations are not isolated to one exact parameter.

## Not proven yet

- True out-of-sample profitability after train-only parameter selection.
- Live execution feasibility with realistic spreads and slippage.
- Actual funding-rate impact.
- Performance under delisting / symbol availability changes.
- Whether the same edge persists after the research period.

---

# Next Research Step

The next required notebook is:

```text
animal0013.ipynb
```

Purpose:

```text
Walk-forward validation with train-selected filters.
```

It should test:

1. Fixed champion strategy out-of-sample
2. Train-selected strategy out-of-sample
3. 18-month train / 3-month test / 30-day purge
4. Cost stress at 10, 25, 50, and 100 bps
5. Parameter stability
6. Fold-by-fold performance
7. OOS p-values
8. OOS crash protection

---

# Future Research Roadmap

## `animal0013.ipynb`

Walk-forward train-selected filters.

Goal:

```text
Prove the current discovery was not just in-sample curve fitting.
```

## `animal0014.ipynb`

Funding, mark price, open interest.

Goal:

```text
Replace flat cost assumptions with real futures market mechanics.
```

## `animal0015.ipynb`

Execution and slippage model.

Goal:

```text
Estimate realistic fills, spread cost, liquidity constraints, and turnover drag.
```

## `animal0016.ipynb`

Paper trading / replay simulation.

Goal:

```text
Test live-style signal generation and execution without capital risk.
```

---

# How to Run

Install dependencies:

```bash
python -m pip install pandas numpy matplotlib scipy statsmodels scikit-learn requests
```

Download/update Binance Vision data:

```bash
python animal.py --start 2019-09-01 --outdir animal_4h_csv
```

Run the baseline notebook:

```bash
jupyter notebook animal001.ipynb
```

Run the improved notebook:

```bash
jupyter notebook animal0012.ipynb
```

Run walk-forward validation once ready:

```bash
jupyter notebook animal0013.ipynb
```

---

# Final Notes

This is not financial advice and should not be treated as a live trading system.

The current research is promising, but the strategy must pass:

- walk-forward validation
- funding-rate adjustment
- execution/slippage modeling
- paper trading
- live monitoring and risk controls

before any real deployment.
