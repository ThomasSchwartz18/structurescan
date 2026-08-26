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

const TIMEFRAME_ORDER = ["1D", "4H", "1H", "15min"];

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
        ["daily-trend", "daily-rsi", "h4-structure", "h1-structure", "alignment", "support", "resistance"].forEach(
          (cls) => {
            trMain.querySelector(`.cell-${cls}`).textContent = "-";
          }
        );
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

  document.getElementById("refresh-button").addEventListener("click", () => {
    watchlist.refresh();
    openPositions.refresh();
    journal.refresh();
  });

  watchlist.refresh();
  openPositions.refresh();
  journal.refresh();
});
