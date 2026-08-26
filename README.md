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

Read-only for now. Trade execution is an explicit future phase — see
[Architecture](#architecture) for why the stack is already built to
support that later without a rewrite.

**Going live?** See [SETUP.md](SETUP.md) for the full walkthrough —
switching market data from mock to real needs no API key at all, which
[SETUP.md](SETUP.md) explains up front rather than making you hunt for
a key that doesn't exist.

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
| **20-MA distance** | % distance of price from its own 20-MA, flagged "extended" beyond a configurable threshold (default 5%) |
| **ATR(14) / extension ratio** | Average True Range per timeframe, and distance-from-recent-swing-low normalized by ATR, so volatility is comparable across tickers with different typical ranges |
| **Volume vs. average** | Latest candle's volume vs. its trailing 20-candle average, flagged "confirmed" or "weak" |
| **RSI divergence** | Bullish (price LL, RSI HL) or bearish (price HH, RSI LH) divergence over the two most recent confirmed swing points, or "none" |
| **Risk/reward ratio** | Distance to nearest resistance ÷ distance to nearest support, from daily swing levels |
| **Swing freshness** | Candles elapsed since the most recent confirmed swing high/low |
| **BTC daily trend reference** | Always-visible header badge showing BTC's own daily MA-stack trend, independent of your watchlist |

Every ticker's detail view also embeds a live **TradingView chart** (the
free "Advanced Chart" widget, no API key) defaulting to 1H with the full
interactive TradingView toolbar — purely a display addition, it doesn't
feed into any of Confluence's own calculations.

A **"Generate Report"** view ranks your whole watchlist by how many of
six fixed criteria each ticker currently meets (timeframe alignment, RSI
neutral, not extended from the 20-MA, volume confirming, no RSI
divergence against the daily trend, R:R above 1.5:1) — reported as
"X meets 5/6 of your defined criteria: [...]", ranked highest-first.
Every card is styled identically regardless of rank; nothing here says
which ticker to act on.

On top of the screener, Confluence has a **paper trading journal**: log a
virtual trade (direction, entry, size, stop-loss/take-profit, and your
reasoning) against a $10,000 virtual account, track open positions'
unrealized P&L against live provider prices, close them manually, and
review win rate / average win vs. loss over your closed trade history. No
real funds or exchange connection — it's practice for executing on what
the screener shows you, with a record you can review later.

Every time the watchlist refreshes, Confluence saves a **criteria
snapshot** per ticker (throttled to at most once an hour per ticker,
30-day retention) — a frozen copy of everything the screener said at
that moment, so "what did this say about XRPUSDT around 10am" is a
lookup, not a memory test.

A **wallet-scan journal** (read-only — no signing, no private key or
seed phrase anywhere in it) scans a public wallet address for swap
history, normalizes it into trade records (direction, entry/exit price,
gas fee, realized P&L), and lands new trades in a **Needs Review** queue.
From there you attach your own reasoning and optionally link the nearest
criteria snapshot for that ticker — pulled up by timestamp so you pick
from real history instead of typing anything from memory. Once
annotated, a trade moves to **Logged**, and the stats summary breaks
down win rate/P&L by how many report criteria were met at entry, so you
can eventually see whether higher-alignment trades actually performed
better. Only `MockWalletProvider` exists today; see
[SETUP.md](SETUP.md#5-wallet-scan-not-yet-implemented) for what a real
one would take.

## Status

**Currently running on mock data by default, clearly labeled as such in
the UI** (the embedded TradingView charts are the one exception — those
show real live market data, since that's a separate, independent
widget). The web app (FastAPI + browser UI), the screening pipeline, the
extended criteria, the morning report, the paper trading journal,
criteria snapshots, the wallet-scan journal (on mock wallet data), and
the data layer's provider abstractions are all built and covered by 209
unit tests. `MockDataProvider` generates realistic, deterministic
synthetic OHLCV so every visual state (aligned bullish, aligned bearish,
conflict) can be exercised without live market access.

`RealDataProvider` (Binance's public API, no API key) is also fully
built and unit-tested, and is one environment variable away from being
the active provider — see [SETUP.md](SETUP.md). It hasn't been verified
against *live* data yet, though: this development environment's network
resets TLS connections to every crypto exchange API tested (see
[Known issues](#known-issues)), so that verification is a "once you're
on your own network" step, not a "not built yet" one. Wallet scanning is
the one piece still mock-only end to end — only `MockWalletProvider`
exists; see [SETUP.md](SETUP.md#5-wallet-scan-not-yet-implemented).

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

Runs entirely on mock data with no further setup. To go live (market
data, or eventually wallet scanning), see [SETUP.md](SETUP.md) — it
covers the `.env` file, exactly which API keys are (and aren't) needed,
and how to verify the switch actually worked.

## Usage

**Web app** (primary interface) — starts a local FastAPI server and
serves the watchlist UI in your browser:

```bash
python -m confluence.api
```

Then open **http://127.0.0.1:8000**. Five tabs:

- **Watchlist** — add/remove tickers, click a row to expand its
  per-timeframe breakdown (including a live TradingView chart) and
  criteria columns, click a column header to sort, use Refresh to re-pull
  data. A BTC daily-trend badge is always visible in the header,
  independent of what's on your watchlist. Your watchlist is saved to
  `tickers.local.json` (gitignored, per-user) and reloaded next time.
- **Open Positions** — from a ticker's expanded detail view, "Log paper
  trade" opens a form (direction, entry price pre-filled from the current
  price, size, optional stop-loss/take-profit, and a required reasoning
  note). Open trades here show live unrealized P&L; Close records the
  current price as exit — manual only, mirroring a real demo account with
  no partial exits.
- **Journal** — closed trades with entry/exit/P&L/reasoning, sortable by
  date or outcome, plus a stats summary (equity, total P&L, win rate,
  average win/loss).
- **Report** — click "Generate Report" to rank your watchlist by criteria
  met (see [What it does](#what-it-does)). On-demand only; nothing
  auto-generates it, so it's exactly where a future scheduler would hook
  in without changing this view.
- **Wallet** — scan a public address for swap history (read-only; never
  asks for a private key or seed phrase). New trades land in **Needs
  Review**; "Annotate" opens your reasoning plus a picker of the nearest
  criteria snapshots for that ticker, then the trade moves to **Logged**
  with a stats summary broken down by criteria met at entry.

Trade records live in `paper_trades.local.db`, criteria snapshots in
`snapshots.local.db`, and wallet journal trades in
`wallet_journal.local.db` (all SQLite, gitignored, per-user).

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
│   ├── binance_client.py    # Binance public REST client (klines, ticker price) — no API key
│   ├── fetch.py               # fetch+enrich orchestration (Binance-direct, and provider-based)
│   └── providers/
│       ├── base.py             # DataProvider interface (+ DataProviderError)
│       ├── mock_provider.py    # MockDataProvider: deterministic synthetic OHLCV
│       └── real_provider.py    # RealDataProvider: wraps binance_client — no API key needed
├── indicators/
│   ├── ta.py               # SMA, Wilder-smoothed RSI(14), ATR(14)
│   ├── swings.py            # objective swing high/low detection
│   └── enrich.py            # attaches indicator + ATR + volume-average columns to raw OHLCV
├── screening/
│   ├── analysis.py          # MA stack / RSI zone / structure / alignment + extended criteria
│   └── report.py             # morning report: criteria matching + ranking, UI-agnostic on purpose
├── snapshots/             # criteria snapshot history
│   ├── db.py                 # SQLite schema + connection (snapshots.local.db)
│   └── store.py                # save (throttled + pruned), nearby-in-time lookup, reconstruction
├── paper/                # paper trading: virtual account + trade journal
│   ├── db.py                # SQLite schema + connection (paper_trades.local.db)
│   └── store.py               # open/close trades, journal queries, P&L/stats math
├── wallet/                # wallet-scan journal — READ-ONLY, no signing anywhere in this tree
│   ├── providers/
│   │   ├── base.py             # WalletProvider interface (+ RawTransaction, WalletProviderError)
│   │   └── mock_provider.py    # MockWalletProvider: deterministic sample swap history
│   ├── normalize.py           # pairs entry/exit swaps (FIFO) into WalletTradeRecord
│   ├── db.py                  # SQLite schema + connection (wallet_journal.local.db)
│   └── store.py                 # ingest (idempotent), Needs Review -> Logged, criteria-bucketed stats
├── api/                  # FastAPI web app (primary interface)
│   ├── app.py               # app factory, mounts static/ + routes
│   ├── provider.py           # the shared DataProvider instance — mock/real via CONFLUENCE_DATA_PROVIDER
│   ├── wallet_provider.py     # the shared WalletProvider instance (mock only today)
│   ├── schemas.py            # dataclass -> JSON response models (screener)
│   ├── routes/
│   │   ├── watchlist.py        # GET/POST/DELETE /api/watchlist, GET /api/meta, BTC context, snapshot capture
│   │   ├── report.py            # GET /api/report
│   │   ├── snapshots.py          # GET /api/snapshots/{symbol}/nearby
│   │   ├── wallet.py              # /api/wallet/scan, needs-review, logged, annotate, stats
│   │   └── paper.py             # /api/paper/trades (open/close/list), /api/paper/stats
│   └── static/                # HTML/CSS/vanilla JS frontend, no build step (incl. TradingView embed)
├── output/
│   └── dashboard.py         # terminal table rendering (rich) — legacy
├── ui/
│   └── app.py               # Tkinter desktop UI — legacy
├── main.py               # terminal entrypoint — legacy
└── verify.py             # manual single-symbol spot-check script (also used to verify RealDataProvider — see SETUP.md)
```

### Why FastAPI + a browser UI instead of a native desktop app

A future phase of this project adds wallet *connection* (MetaMask) for
trade *execution* — out of scope for this build, but the architecture is
chosen with it in mind now to avoid a rebuild later. A browser-based
frontend can talk to MetaMask natively (`window.ethereum`); a native
desktop window (Tkinter/Qt) can't without significant extra plumbing.
Building on a local web stack from the start means the eventual wallet
integration is additive, not a rewrite. The current Tkinter/terminal
tools predate this decision and are kept working but are not where new
frontend work happens.

Note the distinction from what's built today: the wallet-scan journal
(above) only ever *reads* public transaction history — it has nothing to
do with MetaMask connection or signing, and doesn't need `window.ethereum`
at all. "Wallet connection" in this section refers specifically to the
future execution phase.

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

`MockDataProvider` and `RealDataProvider` (wrapping
`confluence/data/binance_client.py`, no API key) both implement it today.
[`confluence/api/provider.py`](confluence/api/provider.py) picks between
them based on the `CONFLUENCE_DATA_PROVIDER` environment variable — see
[SETUP.md](SETUP.md) — with no changes needed anywhere else. Both the
screener and paper trading import that same shared instance, so they
always agree on price.

The wallet-scan feature has the identical shape one layer over: a
`WalletProvider` interface
([`confluence/wallet/providers/base.py`](confluence/wallet/providers/base.py))
with `MockWalletProvider` implemented and a `RealWalletProvider` (reading
a public address's history from a block explorer API) designed for but
not yet built — see [SETUP.md](SETUP.md#5-wallet-scan-not-yet-implemented).

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
  vocabulary — including report-specific anti-patterns the user
  explicitly called out ("focus on X", "best setup today", "top pick") —
  and fail if it appears.
- **The morning report is UI-agnostic by design.** `generate_report()` in
  `confluence/screening/report.py` takes already-built `TickerReport`
  objects and returns plain data — no FastAPI/HTTP dependency at all —
  so a future scheduler can call it directly on a timer with no changes
  to this module, only something new choosing to call it.
- **Divergence/alignment criteria don't get to invent a direction.**
  Where a report criterion is inherently directional ("no bearish
  divergence if considering a long..."), it's evaluated against the
  ticker's own observed daily MA-stack direction rather than asking the
  user which way they're leaning — the report never introduces a
  direction of its own.
- **Objective swing points.** Swing highs/lows are detected as local
  extremes over a configurable window (a "fractal"), not drawn manually —
  so reference levels are reproducible and free of hindsight bias.
- **RSI matches TradingView.** RSI uses Wilder's original SMA-seeded
  recursive smoothing, the same method TradingView's built-in RSI uses —
  not a plain rolling-mean approximation.
- **Partial failure isolation.** A bad ticker or a failed request for one
  symbol doesn't take down the rest of the screen; it's reported inline as
  an error row, in both the terminal dashboard and the web UI.
- **P&L is derived, never a stored running balance.** Realized P&L is
  computed once at close time from (entry, exit, size, direction) and
  stored on that trade row; account equity is always `starting_balance +
  sum(realized P&L of closed trades)`, computed fresh on every request —
  never a mutable balance field that could drift out of sync. Unrealized
  P&L for open trades is computed fresh from whatever price the
  DataProvider returns, every time it's asked for.
- **Closing a paper trade is deliberately manual and irreversible**,
  mirroring a real demo account with no partial exits: there's no
  "undo," and no automatic stop-loss/take-profit execution — those fields
  are recorded for your own reference, not enforced by the system.
- **Wallet scanning is read-only by construction, not by convention.**
  `WalletProvider.get_transactions(address, ...)` is the only method in
  its interface — there is no path anywhere in this feature that accepts,
  stores, or could use a private key or seed phrase, now or in the
  design for a real implementation.
- **The wallet-trade FIFO matcher is a documented simplification, not a
  claim of correctness for every real wallet's history.** It pairs the
  oldest unmatched entry with the next exit for the same token and
  assumes the exit closes exactly that entry's size — same-day partial
  fills or split lots aren't modeled. See the module docstring in
  `confluence/wallet/normalize.py`.
- **Criteria snapshots are a JSON blob of the same dataclasses the API
  already serializes**, not a separately-maintained wide table — saved
  via `dataclasses.asdict()` + `json.dumps(..., default=str)`, so
  capturing a new field the screener computes never requires a schema
  migration here.

## Testing

```bash
python -m pytest
```

All 209 tests run against synthetic or mocked data — no network access
required. Coverage includes:

- RSI and ATR validated against hand-computed examples (to catch
  smoothing/seeding bugs, not just "does it run")
- Edge cases: all-gains, all-losses, and too-short input series
- Swing detection validated against hand-verified fractal positions
- Screening logic: MA stack, RSI zone, structure, and alignment
  classification, plus the extended criteria (20-MA distance, volume
  ratio, RSI divergence direction, R:R ratio, swing freshness) each
  checked against hand-picked scenarios, not just smoke-tested
- Morning report: every criterion checked independently (including the
  R:R "strictly above" boundary and the divergence-direction proxy for
  bullish/bearish/mixed daily stacks), ranking order, and alphabetical
  tie-breaking
- `MockDataProvider`: schema/shape, OHLC geometry, deterministic seeding,
  trend direction, and correct exclusion of the still-forming candle
- The FastAPI watchlist/report APIs (via `TestClient`): fetching, adding,
  removing tickers, BTC reference context, and error isolation
- Paper trading: open/close validation, P&L sign correctness for both
  long and short, win/loss/breakeven classification, stats math (win
  rate, avg win/loss) including the zero-closed-trades edge case, and the
  full API flow (open → appears with live P&L → close → appears in
  journal → stats reflect it) via `TestClient`
- The web frontend's static assets, served correctly and scanned for
  forbidden trading-action language — scoped so the screener's own
  descriptive labels can never say "buy"/"sell"/"long"/"short"/etc, while
  the paper trading journal (which legitimately needs "long"/"short"/
  "entry"/"exit" to record the *user's own* decisions) isn't falsely
  flagged for using that vocabulary
- Binance client parsing (klines and ticker price) and unclosed-candle
  handling, via mocked HTTP responses, plus `RealDataProvider`'s
  timeframe-label translation and error wrapping
- The mock/real provider selection logic (`select_provider()`), tested
  directly rather than via import-time side effects, plus an end-to-end
  check (outside the suite) that flipping `CONFLUENCE_DATA_PROVIDER`
  actually changes `/api/meta`'s `data_source` and that a real fetch
  failure degrades gracefully (per-ticker error, not a crash)
- Criteria snapshots: throttled capture, retention pruning, nearest-in-
  time lookup, and a round-trip test that saves a *real* `MockDataProvider`
  report, reconstructs it from storage, and confirms re-scoring it
  against the morning report criteria gives identical results
- Wallet-scan normalization: entry/exit pairing (including FIFO ordering
  across shuffled/interleaved input), orphan exits and token-to-token
  swaps correctly ignored, and a check against `MockWalletProvider`'s
  actual output; the wallet journal's ingest idempotency, annotation
  flow, and criteria-bucketed stats breakdown; the full API flow (scan →
  Needs Review → annotate with a linked snapshot → Logged → stats) via
  `TestClient`
- The Tkinter UI's widget wiring, threaded fetch/queue handling, ticker
  add/remove, and input validation (legacy path)

The web UI itself was also verified by actually running the server and
loading the page in a real (Playwright-driven) browser — clicking
through sorting, row expansion, add/remove, each alignment state, the
full paper trading flow (log a trade, watch it appear with live P&L,
close it, confirm it lands in the journal with updated stats), the new
criteria columns and detail fields against known-good values computed
independently in a Python shell first, the morning report tab, the
embedded TradingView chart (which really did load live XRP price data,
confirming TradingView's CDN is reachable even in an environment where
every crypto exchange API is blocked — see Known issues), and the full
wallet-scan flow (scan a demo address, confirm the Needs Review queue,
open the annotation modal, confirm the nearby-snapshot picker showed a
*real* snapshot with facts matching that ticker's actual screener state,
save it, confirm it moved to Logged with the correct criteria-met count
and updated stats) — not just by the automated test suite above. Those
live passes caught real bugs a test suite alone wouldn't have: a CSS
`white-space: nowrap` inheritance issue that made most of the expanded
detail view invisible, a watchlist-persistence bug where saving an empty
ticker list silently reverted to defaults, and a modal-styling bug where
the new annotation dialog's CSS rules were scoped only to the older trade
dialog's ID, so it rendered in the browser's unstyled default (white,
light-themed) appearance instead of the app's dark theme until the
selectors were broadened.

## Known issues

Live verification against Binance hasn't been done yet in this
development environment — its network resets TLS connections to every
crypto exchange API tested (Binance.com, Binance.US, Kraken, Coinbase)
while general internet access works fine, consistent with a firewall
policy rather than a code issue. This affects both the legacy
Binance-backed terminal/Tkinter path and the now-built `RealDataProvider`
equally; the web app defaults to mock data and is unaffected either way.
Confirmed with `RealDataProvider` selected: the app doesn't crash, HTTP
200, `data_source` correctly reports `"real"`, and the fetch failure
surfaces as a clear per-ticker error — the graceful-degradation design
already works, only the live numbers themselves are unverified. See
[SETUP.md](SETUP.md) for the exact steps once you're on a network that
can reach Binance, including how to verify the numbers, not just the
connection.

The embedded TradingView charts pull real live data from TradingView's
own CDN (`s3.tradingview.com` / `tradingview-widget.com`), which is a
different host than the exchange APIs above and was confirmed reachable
in this same blocked-network environment — so the chart works today even
though live Binance data doesn't yet. If a chart doesn't load in your
environment, that's a network/firewall question for those specific
TradingView hosts, unrelated to the rest of the app.

## Roadmap

- [ ] Live verification of `RealDataProvider` against TradingView once
      network access allows it (see [SETUP.md](SETUP.md))
- [ ] `RealWalletProvider` (Etherscan or similar, read-only) — see
      [SETUP.md](SETUP.md#5-wallet-scan-not-yet-implemented) for the shape
- [ ] Wallet *connection* (MetaMask) and **real** trade execution —
      explicit future phase, not started, and distinct from the read-only
      wallet-scan journal above (paper trading is practice for this, not
      a step toward it)
- [ ] Editable starting balance / reset-account control in the UI
      (currently set via `PAPER_STARTING_BALANCE` in `config.py`)
- [ ] Morning report criteria thresholds (20-MA extension %, R:R minimum)
      editable in the UI — currently `config.py` constants, applied
      identically for everyone rather than truly "your defined criteria"
- [ ] Scheduled/automatic morning report generation (the module is
      already built to support this — see the "UI-agnostic by design"
      note above — just needs something to call it on a timer)
- [ ] True scheduled criteria-snapshot capture independent of watchlist
      refresh — today a snapshot is only taken when someone loads/refreshes
      the watchlist (throttled to hourly per ticker), so a ticker nobody
      checks for a day won't accumulate history for that day
- [ ] Config file (JSON/YAML) for default timeframes/indicator settings
- [ ] Packaged/distributable build

## Disclaimer

Confluence is an informational technical-analysis tool. It does not
provide investment, trading, or financial advice, and nothing it outputs
should be construed as a recommendation to buy, sell, or hold any asset.
