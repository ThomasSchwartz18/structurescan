"""Tkinter desktop UI for Confluence.

Reuses the exact same screening pipeline and cell-formatting helpers as
the terminal dashboard (confluence.output.dashboard) so the two surfaces
never drift apart or disagree on what a value means.

Network fetches run on a background thread; the main thread only ever
touches Tk widgets, polling a queue for results. This keeps the window
responsive during a slow/failed request instead of freezing.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from confluence.config import CANDLE_LIMIT, TIMEFRAMES
from confluence.main import build_reports
from confluence.output.dashboard import COLUMNS, format_alignment, format_rsi, format_structure, format_swing
from confluence.watchlist import load_tickers, save_tickers

DEFAULT_REFRESH_SECONDS = 60
MIN_REFRESH_SECONDS = 10

DATA_COLUMNS = COLUMNS[1:]  # everything except "Symbol", which is the tree's own #0 column
PLACEHOLDER_ROW = ["fetching..."] + ["-"] * (len(DATA_COLUMNS) - 1)


class ConfluenceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Confluence — Technical State Screen")
        self.geometry("1250x520")
        self.minsize(900, 400)

        self.tickers: list[str] = load_tickers()
        self.refresh_seconds = DEFAULT_REFRESH_SECONDS
        self._queue: queue.Queue = queue.Queue()
        self._fetch_in_progress = False
        self._auto_refresh_enabled = tk.BooleanVar(value=True)
        self._auto_refresh_job: str | None = None

        self._build_widgets()
        self._populate_ticker_rows()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.after(150, self._poll_queue)
        self.refresh_now()
        self._schedule_auto_refresh()

    # ---------------------------------------------------------- widgets --

    def _build_widgets(self) -> None:
        controls = ttk.Frame(self, padding=8)
        controls.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(controls, text="Add ticker:").pack(side=tk.LEFT)
        self.ticker_entry = ttk.Entry(controls, width=14)
        self.ticker_entry.pack(side=tk.LEFT, padx=(4, 4))
        self.ticker_entry.bind("<Return>", lambda _event: self._add_ticker())
        ttk.Button(controls, text="Add", command=self._add_ticker).pack(side=tk.LEFT)
        ttk.Button(controls, text="Remove Selected", command=self._remove_selected).pack(
            side=tk.LEFT, padx=(4, 16)
        )

        ttk.Label(controls, text="Refresh every (s):").pack(side=tk.LEFT)
        self.refresh_entry = ttk.Spinbox(controls, from_=MIN_REFRESH_SECONDS, to=3600, width=6)
        self.refresh_entry.set(str(DEFAULT_REFRESH_SECONDS))
        self.refresh_entry.pack(side=tk.LEFT, padx=(4, 4))
        ttk.Button(controls, text="Apply", command=self._apply_refresh_interval).pack(
            side=tk.LEFT, padx=(0, 16)
        )

        ttk.Checkbutton(
            controls,
            text="Auto-refresh",
            variable=self._auto_refresh_enabled,
            command=self._schedule_auto_refresh,
        ).pack(side=tk.LEFT)
        ttk.Button(controls, text="Refresh Now", command=self.refresh_now).pack(side=tk.LEFT, padx=(8, 0))

        table_frame = ttk.Frame(self)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=DATA_COLUMNS, show="tree headings")
        self.tree.heading("#0", text="Symbol")
        self.tree.column("#0", width=100, anchor=tk.W)
        for col in DATA_COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=130, anchor=tk.CENTER, stretch=False)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        status = ttk.Frame(self, padding=(8, 4))
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(status, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Label(
            status,
            text="Descriptive technical state only — not a recommendation.",
            foreground="#666666",
        ).pack(side=tk.RIGHT)

    def _populate_ticker_rows(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for symbol in self.tickers:
            self.tree.insert("", tk.END, iid=symbol, text=symbol, values=PLACEHOLDER_ROW)

    # ------------------------------------------------- ticker management --

    def _add_ticker(self) -> None:
        raw = self.ticker_entry.get().strip().upper()
        self.ticker_entry.delete(0, tk.END)
        if not raw:
            return
        if raw in self.tickers:
            messagebox.showinfo("Confluence", f"{raw} is already in the list.")
            return
        self.tickers.append(raw)
        save_tickers(self.tickers)
        self.tree.insert("", tk.END, iid=raw, text=raw, values=PLACEHOLDER_ROW)
        self.refresh_now()

    def _remove_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        for symbol in selected:
            self.tree.delete(symbol)
            if symbol in self.tickers:
                self.tickers.remove(symbol)
        save_tickers(self.tickers)

    # ------------------------------------------------------------ refresh --

    def _apply_refresh_interval(self) -> None:
        try:
            value = int(self.refresh_entry.get())
        except ValueError:
            messagebox.showerror("Confluence", "Refresh interval must be a whole number of seconds.")
            return
        if value < MIN_REFRESH_SECONDS:
            messagebox.showerror("Confluence", f"Minimum refresh interval is {MIN_REFRESH_SECONDS}s.")
            return
        self.refresh_seconds = value
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self) -> None:
        if self._auto_refresh_job is not None:
            self.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None
        if self._auto_refresh_enabled.get():
            self._auto_refresh_job = self.after(self.refresh_seconds * 1000, self._auto_refresh_tick)

    def _auto_refresh_tick(self) -> None:
        self.refresh_now()
        self._schedule_auto_refresh()

    def refresh_now(self) -> None:
        if self._fetch_in_progress or not self.tickers:
            return
        self._fetch_in_progress = True
        self.status_var.set("Fetching...")
        threading.Thread(target=self._fetch_worker, args=(list(self.tickers),), daemon=True).start()

    def _fetch_worker(self, symbols: list[str]) -> None:
        try:
            reports = build_reports(symbols, timeframes=TIMEFRAMES, limit=CANDLE_LIMIT)
            self._queue.put(("result", reports))
        except Exception as exc:  # unexpected failure outside per-symbol isolation
            self._queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "result":
                    self._apply_reports(payload)
                elif kind == "error":
                    self.status_var.set(f"Fetch failed: {payload}")
                self._fetch_in_progress = False
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _apply_reports(self, reports: dict) -> None:
        error_count = 0
        for symbol, report in reports.items():
            if not self.tree.exists(symbol):
                continue  # removed from the list while the fetch was in flight
            if isinstance(report, Exception):
                error_count += 1
                values = [f"error: {report}"] + ["-"] * (len(DATA_COLUMNS) - 1)
            else:
                d1 = report.timeframes.get("1D")
                h4 = report.timeframes.get("4H")
                h1 = report.timeframes.get("1H")
                m15 = report.timeframes.get("15min")
                values = [
                    d1.ma_stack if d1 else "n/a",
                    format_rsi(d1) if d1 else "n/a",
                    format_structure(d1.structure) if d1 else "n/a",
                    format_structure(h4.structure) if h4 else "n/a",
                    format_structure(h1.structure) if h1 else "n/a",
                    format_structure(m15.structure) if m15 else "n/a",
                    format_swing(d1.nearest_swing_low) if d1 else "n/a",
                    format_swing(d1.nearest_swing_high) if d1 else "n/a",
                    format_alignment(report.alignment),
                ]
            self.tree.item(symbol, values=values)

        timestamp = datetime.now().strftime("%H:%M:%S")
        if error_count:
            self.status_var.set(f"Last updated {timestamp} — {error_count} ticker(s) failed to fetch.")
        else:
            self.status_var.set(f"Last updated {timestamp}.")

    def _on_close(self) -> None:
        save_tickers(self.tickers)
        self.destroy()


def main() -> None:
    app = ConfluenceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
