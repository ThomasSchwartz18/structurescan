// Confluence watchlist frontend. Vanilla JS, no build step: the app is
// one table plus a handful of fetch calls, which doesn't warrant a
// framework/bundler for v1.

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
  return "state-flat";
}

function badge(kind, value, label) {
  const span = document.createElement("span");
  span.className = `badge ${stateClass(kind, value)}`;
  span.textContent = label;
  return span;
}

function formatPrice(value) {
  if (value === null || value === undefined) return "n/a";
  const decimals = value < 1 ? 4 : value < 100 ? 3 : 2;
  return `$${value.toFixed(decimals)}`;
}

function formatSwing(ref) {
  if (!ref) return "n/a";
  return formatPrice(ref.price);
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
  return TIMEFRAME_ORDER.length && state.price_vs_ma
    ? Object.entries(state.price_vs_ma)
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map(([period, rel]) => `SMA${period}: ${rel === "insufficient_data" ? "n/a" : rel}`)
        .join(", ")
    : "n/a";
}

class WatchlistApp {
  constructor() {
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
    this.sortKey = null;
    this.sortDir = 1;
    this.expandedSymbol = null;

    this.refreshButton.addEventListener("click", () => this.refresh());
    this.addForm.addEventListener("submit", (event) => this.onAddSubmit(event));
    document.querySelectorAll("th[data-sort-key]").forEach((th) => {
      th.addEventListener("click", () => this.onSortClick(th.dataset.sortKey));
    });
  }

  async init() {
    await this.refresh();
  }

  setStatus(text) {
    this.statusLine.textContent = text;
  }

  setBusy(busy) {
    this.refreshButton.disabled = busy;
    this.addForm.querySelector("button").disabled = busy;
  }

  async refresh() {
    this.setBusy(true);
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
    } finally {
      this.setBusy(false);
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

  onSortClick(key) {
    if (this.sortKey === key) {
      this.sortDir *= -1;
    } else {
      this.sortKey = key;
      this.sortDir = 1;
    }
    document.querySelectorAll("th[data-sort-key]").forEach((th) => {
      th.classList.remove("sorted-asc", "sorted-desc");
      if (th.dataset.sortKey === key) {
        th.classList.add(this.sortDir === 1 ? "sorted-asc" : "sorted-desc");
      }
    });
    this.render();
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

  sortedRows() {
    if (!this.sortKey) return this.rows;
    const rows = [...this.rows];
    rows.sort((a, b) => {
      const va = this.sortValue(a, this.sortKey);
      const vb = this.sortValue(b, this.sortKey);
      if (typeof va === "string" || typeof vb === "string") {
        return String(va).localeCompare(String(vb)) * this.sortDir;
      }
      return (va - vb) * this.sortDir;
    });
    return rows;
  }

  render() {
    this.tbody.innerHTML = "";
    const rows = this.sortedRows();
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
        this.populateDetail(trDetail.querySelector(".detail-content"), row);
      }

      trMain.addEventListener("click", () => {
        this.expandedSymbol = expanded ? null : row.symbol;
        this.render();
      });

      this.tbody.appendChild(trMain);
      this.tbody.appendChild(trDetail);
    }
  }

  populateDetail(container, row) {
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

document.addEventListener("DOMContentLoaded", () => {
  const app = new WatchlistApp();
  app.init();
});
