"""Static configuration: tickers and timeframes to screen.

Loads a .env file (if present) before anything else here reads an
environment variable — see SETUP.md for what goes in it. A missing .env
is not an error; every setting below still has a mock-friendly default.
"""

from dotenv import load_dotenv

load_dotenv()

# Binance kline interval codes: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
TIMEFRAMES = {
    "1D": "1d",
    "4H": "4h",
    "1H": "1h",
    "15min": "15m",
}

DEFAULT_TICKERS = [
    "XRPUSDT",
]

# Candle history pulled per request. Must comfortably exceed the longest
# indicator lookback (SMA200) plus room for swing-point detection.
CANDLE_LIMIT = 300

RSI_PERIOD = 14
SMA_PERIODS = (20, 50, 100, 200)

# Candles required on each side of a bar for it to confirm as a swing
# high/low (see confluence/indicators/swings.py).
SWING_ORDER = 3

RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Paper trading: starting balance for the virtual account.
PAPER_STARTING_BALANCE = 10_000.0

# --- Extended screening criteria ---

ATR_PERIOD = 14

# abs(% distance of price from its own 20-MA) beyond which price is
# flagged "extended" (a mean-reversion note, not a signal to act).
MA20_EXTENDED_THRESHOLD_PCT = 5.0

# Trailing candles averaged for the volume-vs-average comparison.
VOLUME_LOOKBACK = 20

# Reference symbol for the always-visible BTC daily trend context row.
BTC_REFERENCE_SYMBOL = "BTCUSDT"

# Morning report criteria thresholds.
REPORT_RR_RATIO_MIN = 1.5

# --- Criteria snapshots ---

# How long a snapshot stays before it's pruned.
SNAPSHOT_RETENTION_DAYS = 30

# A new snapshot for a symbol is only saved if the most recent one is
# older than this — keeps "capture on every screener refresh" from
# spamming the DB when the user just clicks Refresh repeatedly.
SNAPSHOT_CAPTURE_INTERVAL_MINUTES = 60

# --- Wallet transaction scan ---

# Token symbols treated as "base"/quote currencies when pairing swaps
# into entries and exits (see confluence/wallet/normalize.py). A swap
# into one of these is an exit; a swap out of one of these is an entry.
WALLET_BASE_CURRENCIES = {"USDT", "USDC", "DAI", "ETH"}

DEFAULT_WALLET_CHAIN = "ethereum"
