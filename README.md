# Confluence

**Confluence** is a technical screening tool for a personal crypto
watchlist. It scans a configurable list of tickers across multiple
timeframes and surfaces objective technical facts — trend alignment, RSI
zone, MA structure, nearest swing high/low.

> **Confluence reports facts, not opinions.** It never outputs buy/sell
> recommendations, entry/exit signals, or any other trading instruction —
> only observed technical state (moving-average stacking, RSI value/zone,
> swing structure, and whether timeframes agree or disagree with each
> other). What you do with that information is entirely up to you. Nothing
> in this tool is financial advice.

Read-only for now. Trade execution and wallet connection are an explicit
future phase — see [Architecture](#architecture) for why the stack is
already built to support that later without a rewrite.

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

## Status

**Currently running on mock data, clearly labeled as such in the UI.**
The web app (FastAPI + browser UI), the screening pipeline, and the data
layer's provider abstraction are all built and covered by 72 unit tests.
`MockDataProvider` generates realistic, deterministic synthetic OHLCV so
every visual state (aligned bullish, aligned bearish, conflict) can be
exercised without live market access. A real Binance-backed data source
exists too (used by the legacy terminal/Tkinter tools — see below) but
isn't yet wired into the web app; see [Roadmap](#roadmap).

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

**Web app** (primary interface) — starts a local FastAPI server and
serves the watchlist UI in your browser:

```bash
python -m confluence.api
```

Then open **http://127.0.0.1:8000**. Add/remove tickers, click a row to
expand its per-timeframe breakdown, click a column header to sort, and
use Refresh to re-pull data. Your watchlist is saved to
`tickers.local.json` (gitignored, per-user) and reloaded next time.

Try the curated demo tickers to see each state: `XRPUSDT` / `HYPEUSD`
(clean bullish alignment), `SOLUSDT` (clean bearish alignment), `ADAUSDT`
/ `DOGEUSDT` (conflicting timeframes).

<details>
<summary>Legacy terminal / Tkinter tools (Binance-backed, pre-web-pivot)</summary>

These were the original interface before the project moved to a web
stack. They still work and still hit live Binance data, but aren't the
primary way to use Confluence going forward.

```bash
python -m confluence.ui.app        # Tkinter desktop window
python -m confluence.main          # terminal table, refreshes on a loop
python -m confluence.main 30       # ...with a custom refresh interval (seconds)
python -m confluence.verify XRPUSDT 1D   # spot-check indicator values for one symbol/timeframe
```

</details>

Ticker list and timeframe settings live in
[`confluence/config.py`](confluence/config.py).

## Architecture

```
confluence/
├── config.py            # tickers, timeframes, indicator settings
├── watchlist.py         # persists the user's ticker list (shared by every frontend)
├── data/
│   ├── binance_client.py    # Binance public REST client (klines)
│   ├── fetch.py               # fetch+enrich orchestration (Binance-direct, and provider-based)
│   └── providers/
│       ├── base.py             # DataProvider interface (+ DataProviderError)
│       └── mock_provider.py    # MockDataProvider: deterministic synthetic OHLCV
├── indicators/
│   ├── ta.py               # SMA, Wilder-smoothed RSI(14)
│   ├── swings.py            # objective swing high/low detection
│   └── enrich.py            # attaches indicator columns to raw OHLCV
├── screening/
│   └── analysis.py          # MA stack / RSI zone / structure / alignment logic
├── api/                  # FastAPI web app (primary interface)
│   ├── app.py               # app factory, mounts static/ + routes
│   ├── schemas.py            # dataclass -> JSON response models
│   ├── routes/watchlist.py    # GET/POST/DELETE /api/watchlist, GET /api/meta
│   └── static/                # HTML/CSS/vanilla JS frontend, no build step
├── output/
│   └── dashboard.py         # terminal table rendering (rich) — legacy
├── ui/
│   └── app.py               # Tkinter desktop UI — legacy
├── main.py               # terminal entrypoint — legacy
└── verify.py             # manual single-symbol spot-check script — legacy
```

### Why FastAPI + a browser UI instead of a native desktop app

A future phase of this project adds wallet connection (MetaMask) for
trade execution — out of scope for this build, but the architecture is
chosen with it in mind now to avoid a rebuild later. A browser-based
frontend can talk to MetaMask natively (`window.ethereum`); a native
desktop window (Tkinter/Qt) can't without significant extra plumbing.
Building on a local web stack from the start means the eventual wallet
integration is additive, not a rewrite. The current Tkinter/terminal
tools predate this decision and are kept working but are not where new
frontend work happens.

### The DataProvider abstraction

Everything downstream of data fetching — indicators, screening, the API
layer — talks only to the `DataProvider` interface
([`confluence/data/providers/base.py`](confluence/data/providers/base.py)),
never to a concrete data source:

```python
class DataProvider(ABC):
    def get_ohlcv(self, symbol, timeframe, limit) -> pd.DataFrame: ...
    def get_current_price(self, symbol) -> float: ...
```

`MockDataProvider` implements it today. A future `RealDataProvider`
(likely wrapping the already-built `confluence/data/binance_client.py`)
implements the same interface and swaps in at the one line in
[`confluence/api/routes/watchlist.py`](confluence/api/routes/watchlist.py)
that constructs the provider — no changes anywhere else.

### Mock data

`MockDataProvider` generates a seeded geometric random walk per
symbol/timeframe, anchored so the series always ends at the ticker's
configured current price. It's deterministic (stable across refreshes
within the same candle period) and realistic-looking (proper OHLC
geometry, plausible RSI ranges), but every response is clearly labeled
`"data_source": "mock"` and the UI shows a persistent "MOCK DATA" banner
so it's never mistaken for a live signal.

Design principles:

- **Facts only, enforced by tests.** The screening layer never produces
  buy/sell/long/short language. Dedicated tests scan both the rendered
  terminal dashboard and the web frontend's static assets for that
  vocabulary and fail if it appears.
- **Objective swing points.** Swing highs/lows are detected as local
  extremes over a configurable window (a "fractal"), not drawn manually —
  so reference levels are reproducible and free of hindsight bias.
- **RSI matches TradingView.** RSI uses Wilder's original SMA-seeded
  recursive smoothing, the same method TradingView's built-in RSI uses —
  not a plain rolling-mean approximation.
- **Partial failure isolation.** A bad ticker or a failed request for one
  symbol doesn't take down the rest of the screen; it's reported inline as
  an error row, in both the terminal dashboard and the web UI.

## Testing

```bash
python -m pytest
```

All 72 tests run against synthetic or mocked data — no network access
required. Coverage includes:

- RSI validated against a hand-computed example (to catch smoothing/seeding
  bugs, not just "does it run")
- Edge cases: all-gains, all-losses, and too-short input series
- Swing detection validated against hand-verified fractal positions
- Screening logic: MA stack, RSI zone, structure, and alignment
  classification
- `MockDataProvider`: schema/shape, OHLC geometry, deterministic seeding,
  trend direction, and correct exclusion of the still-forming candle
- The FastAPI watchlist API (via `TestClient`): fetching, adding,
  removing tickers, and error isolation
- The web frontend's static assets, served correctly and scanned for
  forbidden trading-action language
- Binance client parsing and unclosed-candle handling, via mocked HTTP
  responses (legacy path)
- The Tkinter UI's widget wiring, threaded fetch/queue handling, ticker
  add/remove, and input validation (legacy path)

The web UI itself was also verified by actually running the server and
loading the page in a real (Playwright-driven) browser — clicking
through sorting, row expansion, add/remove, and each alignment state —
not just by the automated test suite above.

## Known issues

Live verification against Binance hasn't been done yet in this
development environment — its network resets TLS connections to every
crypto exchange API tested (Binance.com, Binance.US, Kraken, Coinbase)
while general internet access works fine, consistent with a firewall
policy rather than a code issue. This only affects the legacy
Binance-backed path (`confluence.data.binance_client`); the web app runs
entirely on mock data and is unaffected. Once Binance is reachable, run
`python -m confluence.verify XRPUSDT 1D` and compare the printed
RSI(14)/SMA(20/50/100/200) values against TradingView for a few closed
daily candles to confirm.

## Roadmap

- [ ] `RealDataProvider` wrapping `binance_client.py`, wired into the web
      app in place of `MockDataProvider`
- [ ] Live verification against TradingView once network access allows it
- [ ] Wallet connection (MetaMask) and trade execution — explicit future
      phase, not started
- [ ] Config file (JSON/YAML) for default timeframes/indicator settings
- [ ] Packaged/distributable build

## Disclaimer

Confluence is an informational technical-analysis tool. It does not
provide investment, trading, or financial advice, and nothing it outputs
should be construed as a recommendation to buy, sell, or hold any asset.
