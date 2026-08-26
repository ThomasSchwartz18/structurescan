# Confluence

**Confluence** is a desktop screening tool that monitors a configurable list
of tickers and flags when multiple technical conditions line up — or
conflict — across timeframes.

> **Confluence reports facts, not opinions.** It never outputs buy/sell
> recommendations, entry/exit signals, or any other trading instruction —
> only observed technical state (moving-average stacking, RSI value/zone,
> swing structure, and whether timeframes agree or disagree with each
> other). What you do with that information is entirely up to you. Nothing
> in this tool is financial advice.

## What it does

For each configured ticker, across four timeframes (1D, 4H, 1H, 15min),
Confluence pulls OHLCV candles and reports:

| Category | What's shown |
|---|---|
| **Moving averages** | SMA 20/50/100/200, and whether they're stacked bullish, bearish, or mixed |
| **Momentum** | RSI(14) value and zone (oversold / neutral / overbought) |
| **Structure** | Higher-highs/higher-lows vs. lower-highs/lower-lows, based on objectively detected swing points — not hand-drawn lines |
| **Reference levels** | Nearest confirmed swing high/low as a factual support/resistance reference |
| **Timeframe alignment** | Whether all four timeframes describe the same technical state, or conflict with each other |

Data comes from Binance's public market-data REST API (no API key required).

## Status

The core pipeline — data fetch → indicators → screening logic → dashboard
(terminal table and a Tkinter desktop UI) — is built and covered by 41
unit tests. Live verification against a real market and TradingView is
still pending; see [Known issues](#known-issues).

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/ThomasSchwartz18/structurescan.git
cd structurescan

python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

## Usage

**Desktop UI** — add/remove tickers, set the refresh interval, toggle
auto-refresh, all from a window:

```bash
python -m confluence.ui.app
```

Your ticker list is saved to `tickers.local.json` (gitignored, per-user)
and reloaded next time you open the app.

**Terminal dashboard** — refreshes in place every 60 seconds by default:

```bash
python -m confluence.main
```

Pass a custom refresh interval (in seconds):

```bash
python -m confluence.main 30
```

Spot-check indicator values for a single symbol/timeframe (useful for
eyeballing RSI/SMA against a charting tool):

```bash
python -m confluence.verify XRPUSDT 1D
```

Ticker list and timeframe settings live in
[`confluence/config.py`](confluence/config.py).

## Architecture

```
confluence/
├── config.py            # tickers, timeframes, indicator settings
├── data/
│   ├── binance_client.py  # Binance public REST client (klines)
│   └── fetch.py            # multi-timeframe / multi-ticker orchestration
├── indicators/
│   ├── ta.py               # SMA, Wilder-smoothed RSI(14)
│   ├── swings.py            # objective swing high/low detection
│   └── enrich.py            # attaches indicator columns to raw OHLCV
├── screening/
│   └── analysis.py          # MA stack / RSI zone / structure / alignment logic
├── output/
│   └── dashboard.py         # terminal table rendering (rich)
├── ui/
│   ├── app.py               # Tkinter desktop UI
│   └── state.py              # persists the user's ticker list between sessions
├── main.py               # terminal entrypoint: fetch → screen → render, on a loop
└── verify.py             # manual single-symbol spot-check script
```

Design principles:

- **Facts only, enforced by tests.** The screening layer never produces
  buy/sell/long/short language. A dedicated test scans rendered dashboard
  output for that vocabulary and fails the build if it appears.
- **Objective swing points.** Swing highs/lows are detected as local
  extremes over a configurable window (a "fractal"), not drawn manually —
  so reference levels are reproducible and free of hindsight bias.
- **RSI matches TradingView.** RSI uses Wilder's original SMA-seeded
  recursive smoothing, the same method TradingView's built-in RSI uses —
  not a plain rolling-mean approximation.
- **Partial failure isolation.** A bad ticker or a failed request for one
  symbol doesn't take down the rest of the screen; it's reported inline as
  an error row.

## Testing

```bash
python -m pytest
```

All 41 tests run against synthetic or mocked data — no network access
required. Coverage includes:

- RSI validated against a hand-computed example (to catch smoothing/seeding
  bugs, not just "does it run")
- Edge cases: all-gains, all-losses, and too-short input series
- Swing detection validated against hand-verified fractal positions
- Screening logic: MA stack, RSI zone, structure, and alignment
  classification
- Binance client parsing and unclosed-candle handling, via mocked HTTP
  responses
- End-to-end wiring from a mocked fetch through to the rendered table
- A guardrail test asserting the dashboard never emits trading-action
  language
- The Tkinter UI's widget wiring, threaded fetch/queue handling, ticker
  add/remove, and input validation

## Known issues

Live verification against Binance hasn't been done yet in this
development environment — its network resets TLS connections to every
crypto exchange API tested (Binance.com, Binance.US, Kraken, Coinbase)
while general internet access works fine, consistent with a firewall
policy rather than a code issue. Once Binance is reachable, run
`python -m confluence.verify XRPUSDT 1D` and compare the printed
RSI(14)/SMA(20/50/100/200) values against TradingView for a few closed
daily candles to confirm.

## Roadmap

- [ ] Live verification against TradingView once network access allows it
- [ ] Sortable/color-coded UI table columns
- [ ] Config file (JSON/YAML) for default timeframes/indicator settings
- [ ] Packaged/distributable build (e.g. PyInstaller)

## Disclaimer

Confluence is an informational technical-analysis tool. It does not
provide investment, trading, or financial advice, and nothing it outputs
should be construed as a recommendation to buy, sell, or hold any asset.
