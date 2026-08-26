# Setup: going from mocked to live

This walks through everything you need once you're on your own
network/computer to move Confluence from "fully mocked" to "as live as
it currently gets." It assumes you're comfortable with Python but
haven't used this specific stack (FastAPI, SQLite, vanilla-JS frontend)
before.

**Read this first, honestly:** two of the four things you might expect
to "switch on" here are fully built and just need you to flip a
setting. One (live market data) needs *no API key at all* — that
surprised me too when I built it. One (real wallet scanning) is **not
implemented yet** — only its interface and a mock exist. This doc says
exactly which is which as we go, rather than describing a finished
system that isn't there.

| Feature | Status |
|---|---|
| Screener market data | ✅ Built. `RealDataProvider` wraps Binance's public API. No API key needed — just flip `CONFLUENCE_DATA_PROVIDER=real`. |
| TradingView charts | ✅ Already live today, even on mock data — see [Known issues](README.md#known-issues) in the README. Nothing to set up. |
| Wallet transaction scan | ⚠️ Interface + `MockWalletProvider` only. A `RealWalletProvider` needs to be built — see [Wallet scan](#5-wallet-scan-not-yet-implemented) below for what that would take. |
| Paper trading, criteria snapshots, morning report | ✅ Fully local — nothing to configure, they already use whichever DataProvider is active. |

---

## 1. Prerequisites

- Python 3.11+
- Git
- A terminal (this doc uses PowerShell syntax where it matters; the
  underlying commands work the same in bash)

## 2. Install and run

```powershell
git clone https://github.com/ThomasSchwartz18/structurescan.git
cd structurescan

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

python -m confluence.api
```

Open **http://127.0.0.1:8000**. If you see the watchlist table with a
"MOCK DATA" banner, everything installed correctly — you're running
exactly what's been built and tested throughout this project, on
synthetic data.

Run the test suite (no network needed, this should always pass
regardless of what's live or mocked):

```powershell
python -m pytest
```

## 3. Market data: Binance (no API key needed)

This is the one that'll surprise you if you expected an API key step:
**Binance's public market-data REST API doesn't require authentication.**
`confluence/data/binance_client.py` calls `GET /api/v3/klines` and
`GET /api/v3/ticker/price` directly — no key, no signing, nothing to
generate on Binance's site. All you need is network access to
`api.binance.com`.

(We evaluated CoinGecko too, but never built an integration for it —
Confluence only ever talks to Binance for market data. If you'd rather
use CoinGecko, that's a new `DataProvider` implementation, not a config
flip; the interface in `confluence/data/providers/base.py` is what
you'd implement against.)

### 3.1 Check you can actually reach Binance

Development on this project happened on a network that resets TLS
connections to every crypto exchange API (see the README's
[Known issues](README.md#known-issues)) — so this was never verified
against live data. Check your own network first:

```powershell
curl.exe -s -o NUL -w "HTTP %{http_code}`n" https://api.binance.com/api/v3/ping
```

You want `HTTP 200`. If you get a connection error or a timeout, that's
a network/firewall/regional-restriction issue on your end, unrelated to
Confluence's code — try a different network or a VPN before continuing.

### 3.2 Switch the provider

Copy the example env file and edit it:

```powershell
copy .env.example .env
```

In `.env`, set:

```
CONFLUENCE_DATA_PROVIDER=real
```

That's the entire switch. `confluence/api/provider.py` reads this at
startup and picks `RealDataProvider` instead of `MockDataProvider` —
nothing else in the app (screening, paper trading, snapshots, the
morning report) needs to change, because they all only ever talk to the
`DataProvider` interface, never to Binance directly.

Restart the app (`Ctrl+C`, then `python -m confluence.api` again — `.env`
is only read at startup) and reload the page. The "MOCK DATA" banner
should be gone, and `GET /api/meta` should report
`{"data_source": "real"}`.

### 3.3 Verify it's actually correct, not just "not mocked"

The banner disappearing proves the switch worked; it doesn't prove the
numbers are right. Run the spot-check script and compare by hand:

```powershell
python -m confluence.verify XRPUSDT 1D
```

This prints RSI(14) and SMA(20/50/100/200) for XRPUSDT's last several
closed daily candles. Open XRPUSDT on TradingView, set the timeframe to
1D, and compare:

- The **closing prices** for the last few candles should match exactly
  (same market, same data).
- **RSI(14)** should match TradingView's default RSI closely (both use
  Wilder's smoothing — see `confluence/indicators/ta.py`'s docstring for
  why this matters; a naive rolling-average RSI would NOT match).
- **SMA 20/50/100/200** should match exactly — a simple moving average
  has no ambiguity in its calculation.

If prices match but RSI is off by more than a rounding difference,
something's wrong with the indicator calculation, not the data source —
that would be worth flagging.

Once you're confident it's correct, add real tickers to your watchlist
from the UI and let it run. The curated demo tickers (XRPUSDT, HYPEUSD,
SOLUSDT, ADAUSDT, DOGEUSDT) were tuned specifically for `MockDataProvider`
and mean nothing under `RealDataProvider` beyond being tickers you can
watch like any other — `HYPEUSD` in particular may not even exist on
Binance as a real trading pair; check before relying on it.

## 4. Switching back to mock data

Set `CONFLUENCE_DATA_PROVIDER=mock` in `.env` (or delete the line, or
delete `.env` entirely — mock is the default) and restart the app. Mock
and real data live in the same watchlist/paper-trading/snapshot storage,
so switching back and forth doesn't corrupt anything, but be aware your
paper trades and snapshots from one mode will look nonsensical viewed
under the other (e.g. a paper trade opened against a mock price won't
line up with a real price for the same symbol).

## 5. Wallet scan: not yet implemented

Be clear-eyed about this section: **there is no `RealWalletProvider` in
this codebase.** `confluence/wallet/providers/base.py` defines the
`WalletProvider` interface (mirroring `DataProvider`), and
`confluence/wallet/providers/mock_provider.py` implements it with
synthetic swap transactions. That's what's actually running today when
you use the Wallet tab. Building the real one is future work — this
section is a head start on that, not a switch to flip.

### 5.1 What a RealWalletProvider would need

Per `WalletProvider.get_transactions(address, chain, limit)`, it needs
to turn a public wallet address into a list of `RawTransaction` objects
(token in/out, amounts, gas fee, timestamp, tx hash — see
`confluence/wallet/providers/base.py`). The natural way to do that
without running your own node is a block explorer API:

- **Etherscan** (Ethereum) — free tier, register at
  https://etherscan.io/apis to get an API key.
- Other chains have their own explorer APIs with a similar shape
  (BscScan, PolygonScan, etc., all under the same Etherscan-family API
  if you use the multi-chain key).

`.env.example` already reserves the variable name for this:

```
ETHERSCAN_API_KEY=your-key-here
```

No code reads this yet — it's there so the name is stable once you (or
I, in a future session) build `RealWalletProvider`.

### 5.2 Finding your MetaMask public address (NOT your private key)

**Confluence's wallet scan is read-only by design and only ever needs
your public wallet address — never your private key or seed phrase.**
Nothing in this codebase has a code path that could accept, store, or
use a private key or seed phrase for anything, now or in the design for
later; `WalletProvider.get_transactions()` takes an `address: str` and
that's the only wallet-related input anywhere in the interface.

To find your public address in MetaMask:

1. Open the MetaMask extension.
2. Click the account name/avatar at the top.
3. Click the address shown (starts with `0x...`) to copy it, or use the
   "Copy address" option in the account menu.

That's the value you'd paste into the Wallet tab's address field. If
anything ever asks you for your seed phrase (12 or 24 words) or a
private key to use this feature, that is **not** this app working as
designed — stop and don't enter it.

### 5.3 Sketch of what building RealWalletProvider would involve

Not a full spec, just the shape, so it's clear what "later" means:

1. A new `confluence/wallet/providers/real_provider.py` implementing
   `WalletProvider`, calling Etherscan's `txlist`/`tokentx` endpoints
   (or the equivalent "get transactions for address" call) with
   `ETHERSCAN_API_KEY`.
2. Decoding which transactions are DEX swaps (vs. plain transfers,
   contract calls, etc.) and extracting token-in/token-out/amounts —
   Etherscan's raw tx list won't hand you this directly; you'd likely
   need the `tokentx` (ERC-20 transfer) endpoint and pair up the two
   transfers that happen inside one swap transaction.
3. Wiring it into `confluence/api/wallet_provider.py` behind an env var,
   the same pattern as `confluence/api/provider.py` for market data.
4. `confluence/wallet/normalize.py` (the entry/exit pairing logic)
   should work unchanged — it only cares about the `RawTransaction`
   shape, not where the transactions came from.

## 6. Troubleshooting

**`ModuleNotFoundError` after `pip install -r requirements.txt`**
Confirm the venv is actually activated — your prompt should start with
`(.venv)`. If it doesn't, re-run `.venv\Scripts\activate` (Windows) or
`source .venv/bin/activate` (macOS/Linux) before installing.

**`Address already in use` / port 8000 busy on startup**
Something else (often a previous run that didn't shut down cleanly) is
already listening on 8000. Find and stop it:
```powershell
netstat -ano | findstr :8000
taskkill /F /PID <pid-from-above>
```

**Watchlist rows show `ok: false` with a connection error, after
switching to `real`**
That's `RealDataProvider` correctly reporting it couldn't reach
Binance — check §3.1 above. This is the app working as designed
(isolating one bad fetch instead of crashing), not a bug.

**`.env` changes don't seem to take effect**
`.env` is only read once, at process startup (`confluence/config.py`
calls `load_dotenv()` at import time). Restart `python -m confluence.api`
after any `.env` edit.

**RSI/SMA values don't match TradingView at all (not just rounding)**
First confirm the *closing prices* match — if those don't match, you're
either looking at a different symbol/exchange pairing on TradingView
(Confluence pulls from Binance specifically) or a different timeframe.
If prices match but indicators don't, that's worth reporting — RSI is
validated against a hand-computed example in `tests/test_ta.py`, so a
real mismatch there would be a genuine bug.

**Paper trading / journal / snapshots look empty after switching
providers**
That's expected the first time — each SQLite file
(`paper_trades.local.db`, `snapshots.local.db`, `wallet_journal.local.db`)
and `tickers.local.json` persist independently of which DataProvider is
active. Nothing is deleted when you switch; a fresh install (or first
run) simply starts empty.

**I want to start over completely**
Every piece of local state is a single gitignored file in the repo
root: `tickers.local.json`, `paper_trades.local.db`,
`snapshots.local.db`, `wallet_journal.local.db`. Delete whichever ones
you want reset and restart the app — each one recreates itself
(defaults / empty schema) on next use.
