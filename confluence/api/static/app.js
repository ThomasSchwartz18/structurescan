// Confluence frontend. Vanilla JS, no build step: the app is a handful of
// tables plus fetch calls, which doesn't warrant a framework/bundler.

const STRUCTURE_LABELS = {
  higher_highs_higher_lows: "HH/HL",
  lower_highs_lower_lows: "LH/LL",
  mixed: "mixed",
  insufficient_data: "n/a",
};

const ALIGNMENT_LABELS = {
  aligned_bullish: "Aligned (bullish)",
  aligned_bearish: "Aligned (bearish)",
  conflict: "Conflict",
};

const MA_STACK_LABELS = {
  bullish: "Bullish",
  bearish: "Bearish",
  mixed: "Mixed",
  insufficient_data: "n/a",
};

const DIRECTION_LABELS = { long: "Long", short: "Short" };

const MA20_STATE_LABELS = { extended: "Extended", normal: "Normal", insufficient_data: "n/a" };
const VOLUME_STATE_LABELS = { confirmed: "Confirmed", weak: "Weak", insufficient_data: "n/a" };
const RSI_DIVERGENCE_LABELS = { none: "None", bullish: "Bullish", bearish: "Bearish" };

const TIMEFRAME_ORDER = ["1D", "4H", "1H", "15min"];

// Default interval shown when a ticker's chart first loads (TradingView
// minute-based codes: "60" = 1H). The embedded widget's own toolbar lets
// the viewer change timeframe/indicators interactively from there — this
// only sets the starting point, not a real-time link to the rest of the app.
const TRADINGVIEW_DEFAULT_INTERVAL = "60";

// Renders TradingView's free "Advanced Chart" widget (no API key) for one
// symbol into `container`. This is a pure display addition: it doesn't
// feed data back into any of Confluence's own indicator calculations.
// Dynamically-inserted <script src> tags only execute when created via
// the DOM API (as here) — assigning via innerHTML would leave them inert.
function renderTradingViewChart(container, symbol) {
  container.innerHTML = "";

  const widgetContainer = document.createElement("div");
  widgetContainer.className = "tradingview-widget-container";
  widgetContainer.style.height = "100%";
  widgetContainer.style.width = "100%";

  const widgetInner = document.createElement("div");
  widgetInner.className = "tradingview-widget-container__widget";
  widgetInner.style.height = "100%";
  widgetInner.style.width = "100%";
  widgetContainer.appendChild(widgetInner);

  const script = document.createElement("script");
  script.type = "text/javascript";
  script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.async = true;
  script.textContent = JSON.stringify({
    autosize: true,
    symbol: `BINANCE:${symbol}`,
    interval: TRADINGVIEW_DEFAULT_INTERVAL,
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "en",
    allow_symbol_change: false,
    support_host: "https://www.tradingview.com",
  });
  widgetContainer.appendChild(script);

  container.appendChild(widgetContainer);
}

function stateClass(kind, value) {
  if (kind === "ma_stack") {
    if (value === "bullish") return "state-bullish";
    if (value === "bearish") return "state-bearish";
    if (value === "mixed") return "state-mixed";
    return "state-flat";
  }
  if (kind === "structure") {
    if (value === "higher_highs_higher_lows") return "state-bullish";
    if (value === "lower_highs_lower_lows") return "state-bearish";
    if (value === "mixed") return "state-mixed";
    return "state-flat";
  }
  if (kind === "alignment") {
    if (value === "aligned_bullish") return "state-bullish";
    if (value === "aligned_bearish") return "state-bearish";
    if (value === "conflict") return "state-mixed";
    return "state-flat";
  }
  if (kind === "direction") {
    return value === "long" ? "state-bullish" : "state-bearish";
  }
  if (kind === "ma20_state") {
    return value === "extended" ? "state-mixed" : "state-flat";
  }
  if (kind === "volume_state") {
    if (value === "confirmed") return "state-bullish";
    if (value === "weak") return "state-mixed";
    return "state-flat";
  }
  if (kind === "rsi_divergence") {
    if (value === "bullish") return "state-bullish";
    if (value === "bearish") return "state-bearish";
    return "state-flat";
  }
  return "state-flat";
}

function badge(kind, value, label) {
  const span = document.createElement("span");
  span.className = `badge ${stateClass(kind, value)}`;
  span.textContent = label;
  return span;
}

function formatMoney(value, { showSign = false } = {}) {
  if (value === null || value === undefined) return "n/a";
  const abs = Math.abs(value);
  const decimals = abs < 1 ? 4 : abs < 100 ? 3 : 2;
  const sign = value < 0 ? "-" : showSign && value > 0 ? "+" : "";
  return `${sign}$${abs.toFixed(decimals)}`;
}

function formatPrice(value) {
  return formatMoney(value);
}

function formatSwing(ref) {
  if (!ref) return "n/a";
  return formatPrice(ref.price);
}

function formatDateTime(iso) {
  if (!iso) return "n/a";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "n/a";
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatPercent(value) {
  if (value === null || value === undefined) return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

// Distance-from-MA is already a percentage value (not a 0-1 fraction),
// unlike formatPercent's win-rate usage above, so this signs it directly
// rather than multiplying by 100.
function formatSignedPercent(value) {
  if (value === null || value === undefined) return "n/a";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatRatio(value, { suffix = "x", decimals = 2 } = {}) {
  if (value === null || value === undefined) return "n/a";
  return `${value.toFixed(decimals)}${suffix}`;
}

function formatRR(value) {
  if (value === null || value === undefined) return "n/a";
  return `${value.toFixed(1)}:1`;
}

function formatCount(value) {
  if (value === null || value === undefined) return "n/a";
  return String(value);
}

// Gas fees are denominated in the chain's native currency (ETH), not
// dollars -- formatMoney's "$" prefix would be wrong here.
function formatGas(value) {
  if (value === null || value === undefined) return "n/a";
  return `${value.toFixed(5)} ETH`;
}

function pnlSpan(value, { showSign = true } = {}) {
  const span = document.createElement("span");
  if (value === null || value === undefined) {
    span.className = "pnl flat";
    span.textContent = "n/a";
    return span;
  }
  const cls = value > 0 ? "positive" : value < 0 ? "negative" : "flat";
  span.className = `pnl ${cls}`;
  span.textContent = formatMoney(value, { showSign });
  return span;
}

function reasoningSpan(text) {
  const span = document.createElement("span");
  span.className = "reasoning-text";
  span.textContent = text;
  span.title = text;
  return span;
}

function rsiCell(state) {
  const wrap = document.createElement("span");
  if (state.rsi === null || state.rsi === undefined) {
    wrap.textContent = "n/a";
    return wrap;
  }
  const value = document.createElement("span");
  value.textContent = state.rsi.toFixed(1);
  wrap.appendChild(value);
  wrap.appendChild(document.createTextNode(" "));
  const zone = document.createElement("span");
  const extended = state.rsi_zone === "overbought" || state.rsi_zone === "oversold";
  zone.className = "rsi-zone" + (extended ? " extended" : "");
  zone.textContent = `(${state.rsi_zone.replace("_", " ")})`;
  wrap.appendChild(zone);
  return wrap;
}

function ma20DistCell(state) {
  const wrap = document.createElement("span");
  if (state.ma20_distance_pct === null || state.ma20_distance_pct === undefined) {
    wrap.textContent = "n/a";
    return wrap;
  }
  wrap.appendChild(document.createTextNode(formatSignedPercent(state.ma20_distance_pct) + " "));
  wrap.appendChild(badge("ma20_state", state.ma20_state, MA20_STATE_LABELS[state.ma20_state] ?? state.ma20_state));
  return wrap;
}

function volumeCell(state) {
  const wrap = document.createElement("span");
  if (state.volume_ratio === null || state.volume_ratio === undefined) {
    wrap.textContent = "n/a";
    return wrap;
  }
  wrap.appendChild(document.createTextNode(formatRatio(state.volume_ratio) + " "));
  wrap.appendChild(badge("volume_state", state.volume_state, VOLUME_STATE_LABELS[state.volume_state] ?? state.volume_state));
  return wrap;
}

function priceVsMaText(state) {
  return state.price_vs_ma
    ? Object.entries(state.price_vs_ma)
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map(([period, rel]) => `SMA${period}: ${rel === "insufficient_data" ? "n/a" : rel}`)
        .join(", ")
    : "n/a";
}

// Scoped to one table (fixes the previous version's bug: an unscoped
// `document.querySelectorAll("th[data-sort-key]")` would have wired every
// table's headers together once a second sortable table existed).
class SortController {
  constructor(tableSelector, onChange) {
    this.headers = document.querySelectorAll(`${tableSelector} thead th[data-sort-key]`);
    this.sortKey = null;
    this.sortDir = 1;
    this.onChange = onChange;
    this.headers.forEach((th) => {
      th.addEventListener("click", () => this.setKey(th.dataset.sortKey));
    });
  }

  setKey(key) {
    if (this.sortKey === key) {
      this.sortDir *= -1;
    } else {
      this.sortKey = key;
      this.sortDir = 1;
    }
    this.headers.forEach((th) => {
      th.classList.remove("sorted-asc", "sorted-desc");
      if (th.dataset.sortKey === this.sortKey) {
        th.classList.add(this.sortDir === 1 ? "sorted-asc" : "sorted-desc");
      }
    });
    this.onChange();
  }

  apply(rows, valueFn) {
    if (!this.sortKey) return rows;
    const copy = [...rows];
    const key = this.sortKey;
    const dir = this.sortDir;
    copy.sort((a, b) => {
      const va = valueFn(a, key);
      const vb = valueFn(b, key);
      if (typeof va === "string" || typeof vb === "string") {
        return String(va).localeCompare(String(vb)) * dir;
      }
      return (va - vb) * dir;
    });
    return copy;
  }
}

// --- Watchlist -------------------------------------------------------

class WatchlistApp {
  constructor(tradeModal) {
    this.tradeModal = tradeModal;
    this.tbody = document.getElementById("watchlist-body");
    this.emptyState = document.getElementById("empty-state");
    this.statusLine = document.getElementById("status-line");
    this.mockBanner = document.getElementById("mock-banner");
    this.btcContext = document.getElementById("btc-context");
    this.btcContextValue = document.getElementById("btc-context-value");
    this.refreshButton = document.getElementById("refresh-button");
    this.addForm = document.getElementById("add-ticker-form");
    this.tickerInput = document.getElementById("ticker-input");
    this.rowTemplate = document.getElementById("row-template");
    this.detailTimeframeTemplate = document.getElementById("detail-timeframe-template");

    this.rows = [];
    this.expandedSymbol = null;
    this.sorter = new SortController("#watchlist-table", () => this.render());

    this.addForm.addEventListener("submit", (event) => this.onAddSubmit(event));
  }

  setStatus(text) {
    this.statusLine.textContent = text;
  }

  setBusy(busy) {
    this.addForm.querySelector("button").disabled = busy;
  }

  async refresh() {
    this.setStatus("Fetching...");
    try {
      const resp = await fetch("/api/watchlist");
      if (!resp.ok) throw new Error(`server returned ${resp.status}`);
      const data = await resp.json();
      this.rows = data.tickers;
      this.mockBanner.hidden = data.data_source !== "mock";
      this.renderBtcContext(data.btc_context);
      this.render();
      const failed = this.rows.filter((r) => !r.ok).length;
      const timestamp = new Date().toLocaleTimeString();
      this.setStatus(
        failed ? `Last updated ${timestamp} — ${failed} ticker(s) failed to fetch.` : `Last updated ${timestamp}.`
      );
    } catch (err) {
      this.setStatus(`Refresh failed: ${err.message}`);
    }
  }

  renderBtcContext(btcContext) {
    if (!btcContext) {
      this.btcContext.hidden = true;
      return;
    }
    this.btcContext.hidden = false;
    this.btcContextValue.className = `badge ${stateClass("ma_stack", btcContext.ma_stack)}`;
    this.btcContextValue.textContent = MA_STACK_LABELS[btcContext.ma_stack] ?? btcContext.ma_stack;
  }

  async onAddSubmit(event) {
    event.preventDefault();
    const symbol = this.tickerInput.value.trim();
    if (!symbol) return;
    this.setBusy(true);
    this.setStatus(`Adding ${symbol.toUpperCase()}...`);
    try {
      const resp = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol }),
      });
      if (!resp.ok) throw new Error(`server returned ${resp.status}`);
      const data = await resp.json();
      this.rows = data.tickers;
      this.tickerInput.value = "";
      this.render();
      this.setStatus(`Added ${symbol.toUpperCase()}.`);
    } catch (err) {
      this.setStatus(`Add failed: ${err.message}`);
    } finally {
      this.setBusy(false);
    }
  }

  async removeTicker(symbol) {
    this.setBusy(true);
    this.setStatus(`Removing ${symbol}...`);
    try {
      const resp = await fetch(`/api/watchlist/${encodeURIComponent(symbol)}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(`server returned ${resp.status}`);
      const data = await resp.json();
      this.rows = data.tickers;
      if (this.expandedSymbol === symbol) this.expandedSymbol = null;
      this.render();
      this.setStatus(`Removed ${symbol}.`);
    } catch (err) {
      this.setStatus(`Remove failed: ${err.message}`);
    } finally {
      this.setBusy(false);
    }
  }

  sortValue(row, key) {
    const d1 = row.ok ? row.timeframes["1D"] : null;
    const h4 = row.ok ? row.timeframes["4H"] : null;
    const h1 = row.ok ? row.timeframes["1H"] : null;
    switch (key) {
      case "symbol":
        return row.symbol;
      case "current_price":
        return row.ok ? row.current_price : -Infinity;
      case "daily_trend":
        return row.ok ? d1.ma_stack : "";
      case "daily_rsi":
        return row.ok && d1.rsi !== null ? d1.rsi : -Infinity;
      case "h4_structure":
        return row.ok ? h4.structure : "";
      case "h1_structure":
        return row.ok ? h1.structure : "";
      case "alignment":
        return row.ok ? row.alignment : "";
      case "support":
        return row.ok && d1.nearest_swing_low ? d1.nearest_swing_low.price : -Infinity;
      case "resistance":
        return row.ok && d1.nearest_swing_high ? d1.nearest_swing_high.price : -Infinity;
      case "rr_ratio":
        return row.ok && row.rr_ratio !== null ? row.rr_ratio : -Infinity;
      case "ma20_dist":
        return row.ok && d1.ma20_distance_pct !== null ? Math.abs(d1.ma20_distance_pct) : -Infinity;
      case "extension_ratio":
        return row.ok && d1.extension_ratio !== null ? d1.extension_ratio : -Infinity;
      case "volume_ratio":
        return row.ok && d1.volume_ratio !== null ? d1.volume_ratio : -Infinity;
      case "rsi_divergence":
        return row.ok ? d1.rsi_divergence : "";
      case "since_high":
        return row.ok && d1.candles_since_swing_high !== null ? d1.candles_since_swing_high : Infinity;
      case "since_low":
        return row.ok && d1.candles_since_swing_low !== null ? d1.candles_since_swing_low : Infinity;
      default:
        return "";
    }
  }

  render() {
    this.tbody.innerHTML = "";
    const rows = this.sorter.apply(this.rows, (row, key) => this.sortValue(row, key));
    this.emptyState.hidden = rows.length > 0;

    for (const row of rows) {
      const fragment = this.rowTemplate.content.cloneNode(true);
      const trMain = fragment.querySelector(".ticker-row");
      const trDetail = fragment.querySelector(".detail-row");

      trMain.querySelector(".cell-symbol").textContent = row.symbol;
      trMain.querySelector(".cell-remove .remove-button").addEventListener("click", (event) => {
        event.stopPropagation();
        this.removeTicker(row.symbol);
      });

      if (!row.ok) {
        trMain.querySelector(".cell-price").textContent = "n/a";
        const symbolCell = trMain.querySelector(".cell-symbol");
        const errEl = document.createElement("div");
        errEl.className = "error-text";
        errEl.textContent = `error: ${row.error}`;
        symbolCell.appendChild(errEl);
        [
          "daily-trend", "daily-rsi", "h4-structure", "h1-structure", "alignment", "support", "resistance",
          "rr-ratio", "ma20-dist", "extension-ratio", "volume-ratio", "rsi-divergence", "since-high", "since-low",
        ].forEach((cls) => {
          trMain.querySelector(`.cell-${cls}`).textContent = "-";
        });
        this.tbody.appendChild(trMain);
        this.tbody.appendChild(trDetail);
        continue;
      }

      const d1 = row.timeframes["1D"];
      const h4 = row.timeframes["4H"];
      const h1 = row.timeframes["1H"];

      trMain.querySelector(".cell-price").textContent = formatPrice(row.current_price);
      trMain.querySelector(".cell-daily-trend").appendChild(badge("ma_stack", d1.ma_stack, MA_STACK_LABELS[d1.ma_stack] ?? d1.ma_stack));
      trMain.querySelector(".cell-daily-rsi").appendChild(rsiCell(d1));
      trMain
        .querySelector(".cell-h4-structure")
        .appendChild(badge("structure", h4.structure, STRUCTURE_LABELS[h4.structure] ?? h4.structure));
      trMain
        .querySelector(".cell-h1-structure")
        .appendChild(badge("structure", h1.structure, STRUCTURE_LABELS[h1.structure] ?? h1.structure));
      trMain
        .querySelector(".cell-alignment")
        .appendChild(badge("alignment", row.alignment, ALIGNMENT_LABELS[row.alignment] ?? row.alignment));
      trMain.querySelector(".cell-support").textContent = formatSwing(d1.nearest_swing_low);
      trMain.querySelector(".cell-resistance").textContent = formatSwing(d1.nearest_swing_high);
      trMain.querySelector(".cell-rr-ratio").textContent = formatRR(row.rr_ratio);
      trMain.querySelector(".cell-ma20-dist").appendChild(ma20DistCell(d1));
      trMain.querySelector(".cell-extension-ratio").textContent = formatRatio(d1.extension_ratio);
      trMain.querySelector(".cell-volume-ratio").appendChild(volumeCell(d1));
      trMain
        .querySelector(".cell-rsi-divergence")
        .appendChild(badge("rsi_divergence", d1.rsi_divergence, RSI_DIVERGENCE_LABELS[d1.rsi_divergence] ?? d1.rsi_divergence));
      trMain.querySelector(".cell-since-high").textContent = formatCount(d1.candles_since_swing_high);
      trMain.querySelector(".cell-since-low").textContent = formatCount(d1.candles_since_swing_low);

      const expanded = this.expandedSymbol === row.symbol;
      trDetail.hidden = !expanded;
      if (expanded) {
        trMain.classList.add("expanded");
        this.populateDetail(trDetail, row);
      }

      trMain.addEventListener("click", () => {
        this.expandedSymbol = expanded ? null : row.symbol;
        this.render();
      });

      this.tbody.appendChild(trMain);
      this.tbody.appendChild(trDetail);
    }
  }

  populateDetail(trDetail, row) {
    renderTradingViewChart(trDetail.querySelector(".detail-chart"), row.symbol);

    const logButton = trDetail.querySelector(".log-trade-button");
    logButton.addEventListener("click", (event) => {
      event.stopPropagation();
      this.tradeModal.open(row.symbol, row.current_price);
    });

    const container = trDetail.querySelector(".detail-content");
    container.innerHTML = "";
    for (const label of TIMEFRAME_ORDER) {
      const state = row.timeframes[label];
      if (!state) continue;
      const fragment = this.detailTimeframeTemplate.content.cloneNode(true);
      fragment.querySelector(".detail-timeframe__title").textContent = label;
      fragment.querySelector(".detail-ma-stack").appendChild(badge("ma_stack", state.ma_stack, MA_STACK_LABELS[state.ma_stack] ?? state.ma_stack));
      fragment.querySelector(".detail-rsi").appendChild(rsiCell(state));
      fragment
        .querySelector(".detail-structure")
        .appendChild(badge("structure", state.structure, STRUCTURE_LABELS[state.structure] ?? state.structure));
      fragment.querySelector(".detail-price-vs-ma").textContent = priceVsMaText(state);
      fragment.querySelector(".detail-swing-high").textContent = formatSwing(state.nearest_swing_high);
      fragment.querySelector(".detail-swing-low").textContent = formatSwing(state.nearest_swing_low);
      fragment.querySelector(".detail-ma20-dist").appendChild(ma20DistCell(state));
      fragment.querySelector(".detail-atr").textContent = state.atr === null ? "n/a" : formatPrice(state.atr);
      fragment.querySelector(".detail-extension-ratio").textContent = formatRatio(state.extension_ratio);
      fragment.querySelector(".detail-volume").appendChild(volumeCell(state));
      fragment
        .querySelector(".detail-rsi-divergence")
        .appendChild(badge("rsi_divergence", state.rsi_divergence, RSI_DIVERGENCE_LABELS[state.rsi_divergence] ?? state.rsi_divergence));
      fragment.querySelector(".detail-since-high").textContent = formatCount(state.candles_since_swing_high);
      fragment.querySelector(".detail-since-low").textContent = formatCount(state.candles_since_swing_low);
      container.appendChild(fragment);
    }
  }
}

// --- Paper trading: open positions ------------------------------------

class OpenPositionsView {
  constructor({ onChanged }) {
    this.onChanged = onChanged;
    this.tbody = document.getElementById("open-positions-body");
    this.emptyState = document.getElementById("open-positions-empty");
    this.countBadge = document.getElementById("open-count-badge");
    this.rowTemplate = document.getElementById("open-position-row-template");
    this.rows = [];
    this.sorter = new SortController("#open-positions-table", () => this.render());
  }

  async refresh() {
    try {
      const resp = await fetch("/api/paper/trades/open");
      if (!resp.ok) throw new Error(`server returned ${resp.status}`);
      this.rows = await resp.json();
    } catch (err) {
      this.rows = [];
    }
    this.render();
    this.countBadge.hidden = this.rows.length === 0;
    this.countBadge.textContent = String(this.rows.length);
  }

  sortValue(row, key) {
    switch (key) {
      case "symbol":
        return row.symbol;
      case "direction":
        return row.direction;
      case "entry_price":
        return row.entry_price;
      case "size":
        return row.size;
      case "current_price":
        return row.current_price ?? -Infinity;
      case "unrealized_pnl":
        return row.unrealized_pnl ?? -Infinity;
      case "stop_loss":
        return row.stop_loss ?? -Infinity;
      case "take_profit":
        return row.take_profit ?? -Infinity;
      case "opened_at":
        return row.opened_at;
      default:
        return "";
    }
  }

  async closePosition(id, symbol) {
    if (!window.confirm(`Close the open ${symbol} position at the current market price? This can't be undone.`)) {
      return;
    }
    try {
      const resp = await fetch(`/api/paper/trades/${id}/close`, { method: "POST" });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `server returned ${resp.status}`);
      }
      await this.onChanged();
    } catch (err) {
      window.alert(`Could not close position: ${err.message}`);
    }
  }

  render() {
    this.tbody.innerHTML = "";
    const rows = this.sorter.apply(this.rows, (row, key) => this.sortValue(row, key));
    this.emptyState.hidden = rows.length > 0;

    for (const row of rows) {
      const fragment = this.rowTemplate.content.cloneNode(true);
      const tr = fragment.querySelector("tr");

      tr.querySelector(".cell-symbol").textContent = row.symbol;
      tr.querySelector(".cell-direction").appendChild(badge("direction", row.direction, DIRECTION_LABELS[row.direction]));
      tr.querySelector(".cell-entry").textContent = formatPrice(row.entry_price);
      tr.querySelector(".cell-size").textContent = row.size;
      tr.querySelector(".cell-stop-loss").textContent = formatPrice(row.stop_loss);
      tr.querySelector(".cell-take-profit").textContent = formatPrice(row.take_profit);
      tr.querySelector(".cell-opened").textContent = formatDateTime(row.opened_at);
      tr.querySelector(".cell-reasoning").appendChild(reasoningSpan(row.reasoning));

      if (row.price_error) {
        tr.querySelector(".cell-current-price").textContent = "error";
        tr.querySelector(".cell-current-price").title = row.price_error;
        tr.querySelector(".cell-unrealized-pnl").textContent = "n/a";
      } else {
        tr.querySelector(".cell-current-price").textContent = formatPrice(row.current_price);
        tr.querySelector(".cell-unrealized-pnl").appendChild(pnlSpan(row.unrealized_pnl));
      }

      tr.querySelector(".close-position-button").addEventListener("click", () => this.closePosition(row.id, row.symbol));

      this.tbody.appendChild(tr);
    }
  }
}

// --- Paper trading: journal + stats ------------------------------------

class JournalView {
  constructor() {
    this.tbody = document.getElementById("journal-body");
    this.emptyState = document.getElementById("journal-empty");
    this.rowTemplate = document.getElementById("journal-row-template");
    this.rows = [];
    this.sorter = new SortController("#journal-table", () => this.render());
  }

  async refresh() {
    try {
      const [tradesResp, statsResp] = await Promise.all([
        fetch("/api/paper/trades/closed"),
        fetch("/api/paper/stats"),
      ]);
      this.rows = tradesResp.ok ? await tradesResp.json() : [];
      if (statsResp.ok) this.renderStats(await statsResp.json());
    } catch (err) {
      this.rows = [];
    }
    this.render();
  }

  renderStats(stats) {
    document.getElementById("stat-equity").textContent = formatPrice(stats.equity);
    const totalPnlEl = document.getElementById("stat-total-pnl");
    totalPnlEl.textContent = "";
    totalPnlEl.appendChild(pnlSpan(stats.realized_pnl_total));
    document.getElementById("stat-win-rate").textContent = formatPercent(stats.win_rate);
    const avgWinEl = document.getElementById("stat-avg-win");
    avgWinEl.textContent = "";
    avgWinEl.appendChild(pnlSpan(stats.avg_win, { showSign: false }));
    const avgLossEl = document.getElementById("stat-avg-loss");
    avgLossEl.textContent = "";
    avgLossEl.appendChild(pnlSpan(stats.avg_loss, { showSign: false }));
    document.getElementById("stat-closed-count").textContent = String(stats.closed_count);
  }

  sortValue(row, key) {
    switch (key) {
      case "symbol":
        return row.symbol;
      case "direction":
        return row.direction;
      case "entry_price":
        return row.entry_price;
      case "exit_price":
        return row.exit_price ?? -Infinity;
      case "size":
        return row.size;
      case "realized_pnl":
        return row.realized_pnl ?? -Infinity;
      case "opened_at":
        return row.opened_at;
      case "closed_at":
        return row.closed_at ?? "";
      default:
        return "";
    }
  }

  render() {
    this.tbody.innerHTML = "";
    const rows = this.sorter.apply(this.rows, (row, key) => this.sortValue(row, key));
    this.emptyState.hidden = rows.length > 0;

    for (const row of rows) {
      const fragment = this.rowTemplate.content.cloneNode(true);
      const tr = fragment.querySelector("tr");

      tr.querySelector(".cell-symbol").textContent = row.symbol;
      tr.querySelector(".cell-direction").appendChild(badge("direction", row.direction, DIRECTION_LABELS[row.direction]));
      tr.querySelector(".cell-entry").textContent = formatPrice(row.entry_price);
      tr.querySelector(".cell-exit").textContent = formatPrice(row.exit_price);
      tr.querySelector(".cell-size").textContent = row.size;
      tr.querySelector(".cell-pnl").appendChild(pnlSpan(row.realized_pnl));
      tr.querySelector(".cell-opened").textContent = formatDateTime(row.opened_at);
      tr.querySelector(".cell-closed").textContent = formatDateTime(row.closed_at);
      tr.querySelector(".cell-reasoning").appendChild(reasoningSpan(row.reasoning));

      this.tbody.appendChild(tr);
    }
  }
}

// --- Trade entry modal ---------------------------------------------------

class TradeModal {
  constructor(onLogged) {
    this.onLogged = onLogged;
    this.dialog = document.getElementById("trade-modal");
    this.form = document.getElementById("trade-form");
    this.symbolLabel = document.getElementById("trade-modal-symbol");
    this.errorEl = document.getElementById("trade-modal-error");
    this.submitButton = document.getElementById("trade-modal-submit");
    this.symbol = null;

    document.getElementById("trade-modal-cancel").addEventListener("click", () => this.dialog.close());
    this.form.addEventListener("submit", (event) => this.onSubmit(event));
  }

  open(symbol, currentPrice) {
    this.symbol = symbol;
    this.symbolLabel.textContent = symbol;
    this.form.reset();
    document.getElementById("trade-entry-price").value = currentPrice ?? "";
    this.errorEl.hidden = true;
    this.dialog.showModal();
  }

  async onSubmit(event) {
    event.preventDefault();
    const data = new FormData(this.form);
    const stopLoss = data.get("stop_loss");
    const takeProfit = data.get("take_profit");
    const payload = {
      symbol: this.symbol,
      direction: data.get("direction"),
      entry_price: Number(data.get("entry_price")),
      size: Number(data.get("size")),
      stop_loss: stopLoss ? Number(stopLoss) : null,
      take_profit: takeProfit ? Number(takeProfit) : null,
      reasoning: data.get("reasoning"),
    };

    this.submitButton.disabled = true;
    try {
      const resp = await fetch("/api/paper/trades", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `server returned ${resp.status}`);
      }
      this.dialog.close();
      await this.onLogged();
    } catch (err) {
      this.errorEl.textContent = err.message;
      this.errorEl.hidden = false;
    } finally {
      this.submitButton.disabled = false;
    }
  }
}

// --- Morning report -------------------------------------------------

class ReportView {
  constructor() {
    this.button = document.getElementById("generate-report-button");
    this.statusLine = document.getElementById("report-status");
    this.list = document.getElementById("report-list");
    this.emptyState = document.getElementById("report-empty");
    this.cardTemplate = document.getElementById("report-card-template");

    this.button.addEventListener("click", () => this.generate());
  }

  async generate() {
    this.button.disabled = true;
    this.statusLine.textContent = "Generating...";
    try {
      const resp = await fetch("/api/report");
      if (!resp.ok) throw new Error(`server returned ${resp.status}`);
      const data = await resp.json();
      this.render(data);
      const timestamp = new Date().toLocaleTimeString();
      const failedNote = data.failed_symbols.length
        ? ` — ${data.failed_symbols.length} ticker(s) could not be scored.`
        : "";
      this.statusLine.textContent = `Generated ${timestamp}.${failedNote}`;
    } catch (err) {
      this.statusLine.textContent = `Report failed: ${err.message}`;
    } finally {
      this.button.disabled = false;
    }
  }

  render(data) {
    this.list.innerHTML = "";
    this.emptyState.hidden = data.scores.length > 0;

    for (const score of data.scores) {
      const fragment = this.cardTemplate.content.cloneNode(true);
      fragment.querySelector(".report-card__symbol").textContent = score.symbol;
      fragment.querySelector(".report-card__count").textContent =
        `meets ${score.met_count}/${score.total_count} of your defined criteria`;

      const list = fragment.querySelector(".report-card__criteria");
      for (const criterion of score.criteria) {
        const li = document.createElement("li");
        const icon = document.createElement("span");
        icon.className = `report-criterion-icon ${criterion.met ? "met" : "unmet"}`;
        icon.textContent = criterion.met ? "✓" : "–";
        const label = document.createElement("span");
        label.className = criterion.met ? "" : "report-criterion-label unmet";
        label.textContent = criterion.label;
        li.appendChild(icon);
        li.appendChild(label);
        list.appendChild(li);
      }

      this.list.appendChild(fragment);
    }
  }
}

// --- Wallet-scan annotation modal ---------------------------------------

class AnnotateModal {
  constructor(onAnnotated) {
    this.onAnnotated = onAnnotated;
    this.dialog = document.getElementById("annotate-modal");
    this.form = document.getElementById("annotate-form");
    this.symbolLabel = document.getElementById("annotate-modal-symbol");
    this.summaryEl = document.getElementById("annotate-modal-summary");
    this.errorEl = document.getElementById("annotate-modal-error");
    this.submitButton = document.getElementById("annotate-modal-submit");
    this.snapshotPicker = document.getElementById("snapshot-picker");
    this.snapshotOptionTemplate = document.getElementById("snapshot-option-template");
    this.trade = null;

    document.getElementById("annotate-modal-cancel").addEventListener("click", () => this.dialog.close());
    this.form.addEventListener("submit", (event) => this.onSubmit(event));
  }

  async open(trade) {
    this.trade = trade;
    this.symbolLabel.textContent = trade.token_symbol;
    const exitText = trade.exit_price !== null ? formatPrice(trade.exit_price) : "still open";
    const pnlText = trade.realized_pnl !== null ? formatMoney(trade.realized_pnl, { showSign: true }) : "n/a";
    this.summaryEl.textContent =
      `${formatPrice(trade.entry_price)} → ${exitText} · size ${trade.size.toFixed(4)} · P&L ${pnlText}`;
    this.form.reset();
    this.errorEl.hidden = true;
    this.snapshotPicker.textContent = "Loading nearby snapshots...";
    this.dialog.showModal();

    const pair = `${trade.token_symbol}USDT`;
    try {
      const url = `/api/snapshots/${encodeURIComponent(pair)}/nearby?around=${encodeURIComponent(trade.entry_timestamp)}&count=5`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`server returned ${resp.status}`);
      const data = await resp.json();
      this.renderSnapshotOptions(data.snapshots);
    } catch (err) {
      this.snapshotPicker.innerHTML = "";
      const p = document.createElement("p");
      p.className = "snapshot-picker-empty";
      p.textContent = "Could not load nearby snapshots.";
      this.snapshotPicker.appendChild(p);
    }
  }

  renderSnapshotOptions(snapshots) {
    this.snapshotPicker.innerHTML = "";
    if (!snapshots.length) {
      const p = document.createElement("p");
      p.className = "snapshot-picker-empty";
      p.textContent = "No criteria snapshots captured yet for this ticker.";
      this.snapshotPicker.appendChild(p);
      return;
    }
    for (const snap of snapshots) {
      const fragment = this.snapshotOptionTemplate.content.cloneNode(true);
      fragment.querySelector("input").value = snap.id;
      fragment.querySelector(".snapshot-option__time").textContent = formatDateTime(snap.captured_at);
      const facts = [];
      if (snap.daily_ma_stack) facts.push(`MA: ${snap.daily_ma_stack}`);
      if (snap.daily_rsi !== null && snap.daily_rsi !== undefined) facts.push(`RSI: ${snap.daily_rsi.toFixed(1)}`);
      if (snap.alignment) facts.push(snap.alignment.replace(/_/g, " "));
      if (snap.rr_ratio !== null && snap.rr_ratio !== undefined) facts.push(`R:R ${snap.rr_ratio.toFixed(1)}:1`);
      fragment.querySelector(".snapshot-option__facts").textContent = facts.join(" · ");
      this.snapshotPicker.appendChild(fragment);
    }
  }

  async onSubmit(event) {
    event.preventDefault();
    const data = new FormData(this.form);
    const linkedId = data.get("linked_snapshot_id");
    const payload = {
      reasoning: data.get("reasoning"),
      linked_snapshot_id: linkedId ? Number(linkedId) : null,
    };

    this.submitButton.disabled = true;
    try {
      const resp = await fetch(`/api/wallet/trades/${this.trade.id}/annotate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `server returned ${resp.status}`);
      }
      this.dialog.close();
      await this.onAnnotated();
    } catch (err) {
      this.errorEl.textContent = err.message;
      this.errorEl.hidden = false;
    } finally {
      this.submitButton.disabled = false;
    }
  }
}

// --- Wallet-scan journal (Needs Review / Logged) ------------------------

class WalletJournalView {
  constructor(annotateModal) {
    this.annotateModal = annotateModal;
    this.scanForm = document.getElementById("wallet-scan-form");
    this.scanStatus = document.getElementById("wallet-scan-status");

    this.needsReviewBody = document.getElementById("needs-review-body");
    this.needsReviewEmpty = document.getElementById("needs-review-empty");
    this.needsReviewRowTemplate = document.getElementById("needs-review-row-template");
    this.needsReviewCountBadge = document.getElementById("needs-review-count-badge");

    this.loggedBody = document.getElementById("wallet-logged-body");
    this.loggedEmpty = document.getElementById("wallet-logged-empty");
    this.loggedRowTemplate = document.getElementById("wallet-logged-row-template");
    this.criteriaBreakdown = document.getElementById("wallet-criteria-breakdown");

    this.needsReviewRows = [];
    this.loggedRows = [];
    this.needsReviewSorter = new SortController("#needs-review-table", () => this.renderNeedsReview());
    this.loggedSorter = new SortController("#wallet-logged-table", () => this.renderLogged());

    this.scanForm.addEventListener("submit", (event) => this.onScanSubmit(event));
  }

  async refresh() {
    await Promise.all([this.refreshNeedsReview(), this.refreshLogged(), this.refreshStats()]);
  }

  async refreshNeedsReview() {
    try {
      const resp = await fetch("/api/wallet/needs-review");
      this.needsReviewRows = resp.ok ? await resp.json() : [];
    } catch (err) {
      this.needsReviewRows = [];
    }
    this.renderNeedsReview();
    this.needsReviewCountBadge.hidden = this.needsReviewRows.length === 0;
    this.needsReviewCountBadge.textContent = String(this.needsReviewRows.length);
  }

  async refreshLogged() {
    try {
      const resp = await fetch("/api/wallet/logged");
      this.loggedRows = resp.ok ? await resp.json() : [];
    } catch (err) {
      this.loggedRows = [];
    }
    this.renderLogged();
  }

  async refreshStats() {
    try {
      const resp = await fetch("/api/wallet/stats");
      if (resp.ok) this.renderStats(await resp.json());
    } catch (err) {
      // leave the stats bar showing whatever it last showed
    }
  }

  renderStats(stats) {
    const totalPnlEl = document.getElementById("wallet-stat-total-pnl");
    totalPnlEl.innerHTML = "";
    totalPnlEl.appendChild(pnlSpan(stats.total_realized_pnl));

    document.getElementById("wallet-stat-gas").textContent = formatGas(stats.total_gas_fees);
    document.getElementById("wallet-stat-win-rate").textContent = formatPercent(stats.win_rate);

    const avgWinEl = document.getElementById("wallet-stat-avg-win");
    avgWinEl.innerHTML = "";
    avgWinEl.appendChild(pnlSpan(stats.avg_win, { showSign: false }));

    const avgLossEl = document.getElementById("wallet-stat-avg-loss");
    avgLossEl.innerHTML = "";
    avgLossEl.appendChild(pnlSpan(stats.avg_loss, { showSign: false }));

    document.getElementById("wallet-stat-logged-count").textContent = String(stats.logged_count);

    this.criteriaBreakdown.innerHTML = "";
    for (const bucket of stats.by_criteria) {
      const div = document.createElement("div");
      div.className = "criteria-bucket";
      const label = document.createElement("span");
      label.className = "criteria-bucket__label";
      label.textContent = `${bucket.met_count}/${bucket.total_count} met`;
      div.appendChild(label);
      div.appendChild(document.createTextNode(`${bucket.trade_count} trade(s), ${formatPercent(bucket.win_rate)} win rate, `));
      div.appendChild(pnlSpan(bucket.total_pnl));
      this.criteriaBreakdown.appendChild(div);
    }
  }

  sortValue(row, key) {
    switch (key) {
      case "token_symbol":
        return row.token_symbol;
      case "entry_price":
        return row.entry_price;
      case "exit_price":
        return row.exit_price ?? -Infinity;
      case "size":
        return row.size;
      case "realized_pnl":
        return row.realized_pnl ?? -Infinity;
      case "gas_fee_total":
        return row.gas_fee_total;
      case "criteria_met_count":
        return row.criteria_met_count ?? -Infinity;
      case "entry_timestamp":
        return row.entry_timestamp;
      default:
        return "";
    }
  }

  renderNeedsReview() {
    this.needsReviewBody.innerHTML = "";
    const rows = this.needsReviewSorter.apply(this.needsReviewRows, (row, key) => this.sortValue(row, key));
    this.needsReviewEmpty.hidden = rows.length > 0;

    for (const row of rows) {
      const fragment = this.needsReviewRowTemplate.content.cloneNode(true);
      fragment.querySelector(".cell-token").textContent = row.token_symbol;
      fragment.querySelector(".cell-entry").textContent = formatPrice(row.entry_price);
      fragment.querySelector(".cell-exit").textContent = row.exit_price !== null ? formatPrice(row.exit_price) : "open";
      fragment.querySelector(".cell-size").textContent = row.size.toFixed(4);
      fragment.querySelector(".cell-pnl").appendChild(pnlSpan(row.realized_pnl));
      fragment.querySelector(".cell-gas").textContent = formatGas(row.gas_fee_total);
      fragment.querySelector(".cell-entered").textContent = formatDateTime(row.entry_timestamp);
      fragment.querySelector(".annotate-button").addEventListener("click", () => this.annotateModal.open(row));
      this.needsReviewBody.appendChild(fragment);
    }
  }

  renderLogged() {
    this.loggedBody.innerHTML = "";
    const rows = this.loggedSorter.apply(this.loggedRows, (row, key) => this.sortValue(row, key));
    this.loggedEmpty.hidden = rows.length > 0;

    for (const row of rows) {
      const fragment = this.loggedRowTemplate.content.cloneNode(true);
      fragment.querySelector(".cell-token").textContent = row.token_symbol;
      fragment.querySelector(".cell-entry").textContent = formatPrice(row.entry_price);
      fragment.querySelector(".cell-exit").textContent = row.exit_price !== null ? formatPrice(row.exit_price) : "open";
      fragment.querySelector(".cell-size").textContent = row.size.toFixed(4);
      fragment.querySelector(".cell-pnl").appendChild(pnlSpan(row.realized_pnl));
      fragment.querySelector(".cell-gas").textContent = formatGas(row.gas_fee_total);
      fragment.querySelector(".cell-criteria").textContent =
        row.criteria_met_count !== null ? `${row.criteria_met_count}/${row.criteria_total_count}` : "n/a";
      fragment.querySelector(".cell-entered").textContent = formatDateTime(row.entry_timestamp);
      fragment.querySelector(".cell-reasoning").appendChild(reasoningSpan(row.reasoning || ""));
      this.loggedBody.appendChild(fragment);
    }
  }

  async onScanSubmit(event) {
    event.preventDefault();
    const data = new FormData(this.scanForm);
    const address = data.get("address").trim();
    const chain = data.get("chain").trim() || "ethereum";
    if (!address) return;

    this.scanStatus.textContent = "Scanning...";
    try {
      const resp = await fetch("/api/wallet/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address, chain }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `server returned ${resp.status}`);
      }
      const result = await resp.json();
      await this.refresh();
      this.scanStatus.textContent = `Found ${result.trade_records_found} trade(s), ${result.new_trades_ingested} new.`;
    } catch (err) {
      this.scanStatus.textContent = `Scan failed: ${err.message}`;
    }
  }
}

// --- Tabs + bootstrap ---------------------------------------------------

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-button");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.hidden = panel.id !== `tab-${button.dataset.tab}`;
      });
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();

  const openPositions = new OpenPositionsView({
    onChanged: async () => {
      await openPositions.refresh();
      await journal.refresh();
    },
  });
  const journal = new JournalView();
  const tradeModal = new TradeModal(async () => {
    await openPositions.refresh();
  });
  const watchlist = new WatchlistApp(tradeModal);
  new ReportView(); // on-demand only (per its own "Generate Report" button) — not part of the global refresh

  const annotateModal = new AnnotateModal(async () => {
    await walletJournal.refresh();
  });
  const walletJournal = new WalletJournalView(annotateModal);

  document.getElementById("refresh-button").addEventListener("click", () => {
    watchlist.refresh();
    openPositions.refresh();
    journal.refresh();
    walletJournal.refresh();
  });

  watchlist.refresh();
  openPositions.refresh();
  journal.refresh();
  walletJournal.refresh();
});
