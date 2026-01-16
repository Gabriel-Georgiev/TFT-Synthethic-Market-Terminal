import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from config import MIN_GAMES_PER_COMP
from engine.market_store import (
    get_latest_base_traits_sorted,
    get_variants_for_base_on_latest_day,
    series_for_symbol,
)
from engine.watchlist import load_watchlist, toggle_watch


class MarketApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TFT Synthetic Market Terminal")
        self.geometry("1570x780")

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10))
        style.configure("List.TLabel", font=("Segoe UI", 11, "bold"))

        # Data
        self.base_rows = []          # full list [(base_sym, close, games)]
        self.filtered_rows = []      # rows shown
        self.variant_rows = []       # [(variant_sym, close, games)]

        self.selected_base = None
        self.selected_symbol = None

        # Watchlist
        self.watchlist = load_watchlist()
        self.watch_button = None

        # Sorting state
        self.sort_by = "price"       # "symbol" / "price" / "conf"
        self.sort_desc = True

        # Hover
        self.current_points = []     # [(day, close, games), ...]
        self.hover_annot = None
        self.corner_text = None

        self._build_layout()
        self._load_data_and_render(auto_select=True)

    def _confidence_label(self, games):
        if games is None:
            return "UNK"
        if games >= 80:
            return "HIGH"
        if games >= 40:
            return "MED"
        return "LOW"

    def _open_help(self):
        win = tk.Toplevel(self)
        win.title("Help — Synthetic Market")
        win.geometry("920x520")

        txt = tk.Text(win, wrap="word", padx=12, pady=12)
        txt.pack(fill="both", expand=True)

        help_text = """
1. What am I looking at?

    - The table lists synthetic instruments built from TFT traits.
    - A "continuous future" is the aggregated instrument for a trait (e.g. /BILGEWATER:XCOMP).
    - "Contracts" are the variants (e.g. /BILGEWATER3:XCOMP, /BILGEWATER5:XCOMP).
    - Selecting an instrument plots its daily close series.

2. Price (Synthetic Close)

    - Each instrument has a synthetic 'close' price (0..100 in the current implementation).
    - Current project formula:
        price = 50*win_rate + 30*top4_rate + 20*pick_rate
    - Note: In this UI we currently display only the final close price.

3. Confidence

    - Confidence is derived from the number of games/boards used in the calculation:
        HIGH: games >= 80
        MED : 40 <= games < 80
        LOW : 20 <= games < 40
        UNK : unknown (older history didn’t store games)

4. Watchlist

    - Use the ☆/★ button to pin an instrument.
    - Watchlisted instruments are shown first in the table.

5. Extensibility
    - Right now only the XCOMP exchange is shown.
    - The design supports adding more exchanges later (e.g., items, champions, etc.).
"""
        txt.insert("1.0", help_text.strip())
        txt.configure(state="disabled")

    def _build_layout(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        # LEFT
        left = ttk.Frame(self, padding=12)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(5, weight=1)

        header_row = ttk.Frame(left)
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.columnconfigure(0, weight=1)

        ttk.Label(header_row, text="List of all supported instruments", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(header_row, text="?", width=3, command=self._open_help).grid(
            row=0, column=1, sticky="e"
        )

        ttk.Label(left, text="", style="Sub.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 10))

        search_row = ttk.Frame(left)
        search_row.grid(row=2, column=0, sticky="ew")
        search_row.columnconfigure(1, weight=1)

        ttk.Label(search_row, text="Search:", style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        self.search_var = tk.StringVar(value="")
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)

        ttk.Label(left, text="Continuous futures", style="List.TLabel").grid(
            row=3, column=0, sticky="w", pady=(10, 4)
        )

        table_frame = ttk.Frame(left)
        table_frame.grid(row=5, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("symbol", "price", "conf"),
            show="headings",
            selectmode="browse",
            height=18,
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.heading("symbol", text="Instrument", command=lambda: self._sort_table("symbol"))
        self.tree.heading("price", text="Price", command=lambda: self._sort_table("price"))
        self.tree.heading("conf", text="Confidence", command=lambda: self._sort_table("conf"))

        self.tree.column("symbol", width=230, anchor="w")
        self.tree.column("price", width=90, anchor="center")
        self.tree.column("conf", width=90, anchor="center")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self.left_info = ttk.Label(left, text=f"Min games filter = {MIN_GAMES_PER_COMP}", style="Sub.TLabel")
        self.left_info.grid(row=6, column=0, sticky="w", pady=(10, 0))

        right = ttk.Frame(self, padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)

        top = ttk.Frame(right)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Instrument", style="List.TLabel").grid(row=0, column=0, sticky="w")
        self.instrument_title = ttk.Label(top, text="—", style="Header.TLabel")
        self.instrument_title.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.watch_button = ttk.Button(top, text="☆ Watch", command=self._toggle_watch_current)
        self.watch_button.grid(row=0, column=2, sticky="e", padx=(10, 0))

        contract_row = ttk.Frame(right)
        contract_row.grid(row=1, column=0, sticky="ew", pady=(10, 6))
        contract_row.columnconfigure(1, weight=1)

        ttk.Label(contract_row, text="Contract:", style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        self.contract_var = tk.StringVar(value="(continuous)")
        self.contract_menu = ttk.Combobox(
            contract_row, textvariable=self.contract_var, state="readonly", values=["(continuous)"]
        )
        self.contract_menu.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.contract_menu.bind("<<ComboboxSelected>>", self._on_contract_selected)

        self.stats_label = ttk.Label(
            right,
            text="Hover on the chart to see exact close price.",
            style="Sub.TLabel",
        )
        self.stats_label.grid(row=2, column=0, sticky="w", pady=(0, 8))

        self.fig = Figure(figsize=(10, 5.8))
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Daily Chart")
        self.ax.set_ylabel("Price")
        self.ax.grid(True, alpha=0.3)

        self.corner_text = self.ax.text(
            0.01, 0.99, "",
            transform=self.ax.transAxes,
            va="top", ha="left",
            fontsize=10
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().grid(row=4, column=0, sticky="nsew")

        self.hover_annot = self.ax.annotate(
            "",
            xy=(0, 0),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray", alpha=0.85),
        )
        self.hover_annot.set_visible(False)

        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)

    def _toggle_watch_current(self):
        if not self.selected_base:
            return
        now_watched = toggle_watch(self.selected_base)
        self.watchlist = load_watchlist()
        self._update_watch_button()

        self._refresh_table_preserve_selection(self.selected_base)

    def _update_watch_button(self):
        if not self.watch_button:
            return
        if self.selected_base and self.selected_base in self.watchlist:
            self.watch_button.config(text="★ Watched")
        else:
            self.watch_button.config(text="☆ Watch")

    def _refresh_table_preserve_selection(self, symbol_to_select: str | None):

        self._apply_sort()
        self._render_table(self.filtered_rows)

        if symbol_to_select:
            for iid in self.tree.get_children():
                vals = self.tree.item(iid, "values")
                if vals and vals[0] == symbol_to_select:
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    break


    def _load_data_and_render(self, auto_select: bool):
        self.base_rows = get_latest_base_traits_sorted(min_games=MIN_GAMES_PER_COMP)
        if not self.base_rows:
            self.left_info.config(text="No data. Run collect_daily.py (or lower MIN_GAMES_PER_COMP).")
            self._render_table([])
            self._clear_chart("No data")
            return

        self.filtered_rows = list(self.base_rows)
        self._apply_sort()
        self._render_table(self.filtered_rows)

        self.left_info.config(
            text=f"Loaded {len(self.base_rows)} instruments. Click headers to sort. (min games={MIN_GAMES_PER_COMP})"
        )

        if auto_select and self.filtered_rows:
            first_id = self.tree.get_children()[0]
            self.tree.selection_set(first_id)
            self.tree.focus(first_id)
            self._on_tree_select(None)

    def _render_table(self, rows):

        self.tree.delete(*self.tree.get_children())

        watched = [r for r in rows if r[0] in self.watchlist]
        rest = [r for r in rows if r[0] not in self.watchlist]

        def insert_row(sym, close, games):
            conf = self._confidence_label(games)
            self.tree.insert("", "end", values=(sym, f"{close:.4f}", conf))

        if watched:

            self.tree.insert("", "end", values=("— Watchlist —", "", ""))
            for sym, close, games in watched:
                insert_row(sym, close, games)

            self.tree.insert("", "end", values=("— All Instruments —", "", ""))

        for sym, close, games in rest:
            insert_row(sym, close, games)

    def _sort_table(self, which: str):
        if self.sort_by == which:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_by = which
            self.sort_desc = True if which in ("price", "conf") else False

        self._refresh_table_preserve_selection(self.selected_base)

    def _apply_sort(self):
        if self.sort_by == "symbol":
            self.filtered_rows.sort(key=lambda r: r[0], reverse=self.sort_desc)
        elif self.sort_by == "conf":
            order = {"HIGH": 3, "MED": 2, "LOW": 1, "UNK": 0}
            self.filtered_rows.sort(
                key=lambda r: order[self._confidence_label(r[2])],
                reverse=self.sort_desc
            )
        else:
            self.filtered_rows.sort(key=lambda r: r[1], reverse=self.sort_desc)

    def _on_search_change(self, _event=None):
        q = self.search_var.get().strip().upper()
        if not q:
            self.filtered_rows = list(self.base_rows)
        else:
            self.filtered_rows = [r for r in self.base_rows if q in r[0].upper()]

        self._refresh_table_preserve_selection(self.selected_base)

        if self.filtered_rows:
            for iid in self.tree.get_children():
                vals = self.tree.item(iid, "values")
                if vals and vals[0].startswith("—"):
                    continue
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self._on_tree_select(None)
                break
        else:
            self.instrument_title.config(text="—")
            self.selected_base = None
            self._update_watch_button()
            self.contract_menu["values"] = ["(continuous)"]
            self.contract_var.set("(continuous)")
            self.stats_label.config(text="No results for that search.")
            self._clear_chart("No matching instruments")

    def _on_tree_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return

        sym, price_str, conf = self.tree.item(sel[0], "values")

        if sym.startswith("—"):
            return

        self.selected_base = sym
        self._update_watch_button()

        self.variant_rows = get_variants_for_base_on_latest_day(sym, min_games=MIN_GAMES_PER_COMP)
        values = ["(continuous)"] + [f"{vsym}  ({vclose:.4f})" for vsym, vclose, _g in self.variant_rows]
        self.contract_menu["values"] = values
        self.contract_var.set("(continuous)")

        self._plot_symbol(sym)
        self.stats_label.config(text=f"Latest price: {price_str} | Confidence: {conf} | Contracts: {len(self.variant_rows)}")

    def _on_contract_selected(self, _event):
        choice = self.contract_var.get()
        if choice == "(continuous)" and self.selected_base:
            self._plot_symbol(self.selected_base)
            return

        sym = choice.split("  (", 1)[0].strip()
        self._plot_symbol(sym)

    def _plot_symbol(self, sym: str):
        self.selected_symbol = sym
        self.current_points = series_for_symbol(sym)  # [(day, close, games), ...]

        self.instrument_title.config(text=sym)

        if not self.current_points:
            self._clear_chart(f"No series for {sym}")
            return

        days = [d for d, _, _ in self.current_points]
        closes = [c for _, c, _ in self.current_points]
        x = list(range(len(days)))

        self.ax.clear()
        self.ax.plot(x, closes, marker="o", linewidth=1.8)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_title("Daily Chart")
        self.ax.set_ylabel("Price")
        self.ax.set_xticks(x)
        self.ax.set_xticklabels(days)

        self.corner_text = self.ax.text(
            0.01, 0.99, "",
            transform=self.ax.transAxes,
            va="top", ha="left",
            fontsize=10
        )

        self.hover_annot = self.ax.annotate(
            "",
            xy=(0, 0),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray", alpha=0.85),
        )
        self.hover_annot.set_visible(False)

        self.fig.tight_layout()
        self.canvas.draw()

    def _clear_chart(self, title: str):
        self.current_points = []
        self.ax.clear()
        self.ax.set_title(title)
        self.ax.set_ylabel("Price")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

    def _on_mouse_move(self, event):
        if event.inaxes != self.ax or not self.current_points:
            if self.hover_annot and self.hover_annot.get_visible():
                self.hover_annot.set_visible(False)
                if self.corner_text:
                    self.corner_text.set_text("")
                self.canvas.draw_idle()
            return

        if event.xdata is None:
            return

        idx = int(round(event.xdata))
        if idx < 0 or idx >= len(self.current_points):
            if self.hover_annot.get_visible():
                self.hover_annot.set_visible(False)
                self.corner_text.set_text("")
                self.canvas.draw_idle()
            return

        day, close, games = self.current_points[idx]

        self.hover_annot.xy = (idx, close)
        self.hover_annot.set_text(f"{close:.4f}")
        self.hover_annot.set_visible(True)

        gtxt = f"{games}" if games is not None else "?"
        self.corner_text.set_text(f"{day}    CLOSE {close:.4f}    GAMES {gtxt}")

        self.canvas.draw_idle()


if __name__ == "__main__":
    MarketApp().mainloop()