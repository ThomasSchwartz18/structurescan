"""Static configuration: tickers and timeframes to screen."""

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
