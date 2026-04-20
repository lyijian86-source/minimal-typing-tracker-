from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Callable

from type_record.config import AppConfig
from type_record.counter import KeyboardCounter
from type_record.i18n import tr
from type_record.storage import DailyCountStore

# ---------------------------------------------------------------------------
# Design system — colour tokens
# ---------------------------------------------------------------------------
_BG = "#F4F5F9"
_CARD = "#FFFFFF"
_CARD_INNER = "#F6F7FB"
_BORDER = "#E2E5EE"
_BORDER_INNER = "#ECEEF4"
_TEXT_PRIMARY = "#1A1D26"
_TEXT_SECONDARY = "#4A5068"
_TEXT_TERTIARY = "#8B92A5"
_TEXT_QUATERNARY = "#B0B6C6"
_ACCENT = "#5C6AC4"
_ACCENT_LIGHT = "#E8EAF6"
_ACCENT_SOFT = "#9CA3D4"
_CHART_BG = "#FAFAFE"
_CHART_GRID = "#EDEFF5"
_HOURLY_TYPED = "#5C6AC4"
_HOURLY_PASTED = "#B8BDE0"
_SUCCESS = "#4CAF82"


class CounterWindow:
    def __init__(self, config: AppConfig, store: DailyCountStore, counter: KeyboardCounter, on_export_csv: Callable[[], None], on_language_changed: Callable[[str], None]) -> None:
        self.config, self.store, self.counter = config, store, counter
        self.on_export_csv, self.on_language_changed = on_export_csv, on_language_changed
        self.root = tk.Tk()
        self.root.title(config.app_name)
        self.root.geometry("1100x760")
        self.root.minsize(1040, 720)
        self.root.configure(bg=_BG)
        self._configure_ttk()

        self.count_var = tk.StringVar(value="0")
        self.detail_var = tk.StringVar(value="0")
        self.session_var = tk.StringVar(value="")
        self.session_length_var = tk.StringVar(value="00:00")
        self.session_typed_var = tk.StringVar(value="0")
        self.session_pasted_var = tk.StringVar(value="0")
        self.session_accuracy_var = tk.StringVar(value="0%")
        self.typed_today_var = tk.StringVar(value="0")
        self.pasted_today_var = tk.StringVar(value="0")
        self.backspace_var = tk.StringVar(value="0")
        self.accuracy_var = tk.StringVar(value="0%")
        self.cpm_var = tk.StringVar(value="0")
        self.peak_wpm_var = tk.StringVar(value="0.0")
        self.yesterday_var = tk.StringVar(value="0")
        self.week_var = tk.StringVar(value="0")
        self.last_input_var = tk.StringVar(value=tr(config.language, "no_input"))
        self.export_var = tk.StringVar(value="")
        self.accuracy_hint_var = tk.StringVar(value="")
        self.count_mode_var = tk.StringVar(value="")
        self.settings_var = tk.StringVar(value="")
        self.history_footer_var = tk.StringVar(value="")
        self.trend_meta_var = tk.StringVar(value="")
        self.trend_peak_var = tk.StringVar(value="0")
        self.trend_latest_var = tk.StringVar(value="0")

        self.history_vars: list[dict[str, tk.StringVar]] = []
        self._latest_trend_history: list[dict] = []
        self._history_dialog: tk.Toplevel | None = None
        self._history_tree: ttk.Treeview | None = None
        self._history_preview_canvas: tk.Canvas | None = None
        self._history_preview_inner: tk.Frame | None = None
        self._hourly_dialog: tk.Toplevel | None = None
        self._hourly_tree: ttk.Treeview | None = None
        self._hourly_canvas: tk.Canvas | None = None
        self._hourly_peak_var: tk.StringVar | None = None
        self._hourly_date_var: tk.StringVar | None = None
        self._hourly_date_selector: ttk.Combobox | None = None
        self._refresh_after_id: str | None = None
        self._trend_tooltip_items: list[int] = []

        self._build_layout()
        self._schedule_refresh()

    def set_on_close(self, callback) -> None: self.root.protocol("WM_DELETE_WINDOW", callback)
    def show(self) -> None:
        self.root.deiconify()
        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        self.root.lift()
        self.root.focus_force()
    def hide(self) -> None: self.root.withdraw()
    def call_in_main_thread(self, callback) -> None: self.root.after(0, callback)
    def run(self) -> None: self.root.mainloop()

    def destroy(self) -> None:
        self._cancel_refresh()
        if self._history_dialog and self._history_dialog.winfo_exists(): self._history_dialog.destroy()
        if self._hourly_dialog and self._hourly_dialog.winfo_exists(): self._hourly_dialog.destroy()
        self.root.destroy()

    def refresh_language(self) -> None:
        self._cancel_refresh()
        if self._history_dialog and self._history_dialog.winfo_exists(): self._history_dialog.destroy()
        if self._hourly_dialog and self._hourly_dialog.winfo_exists(): self._hourly_dialog.destroy()
        for child in self.root.winfo_children(): child.destroy()
        self.history_vars.clear()
        self._history_dialog = self._hourly_dialog = None
        self._history_tree = self._hourly_tree = None
        self._history_preview_canvas = None
        self._history_preview_inner = None
        self._hourly_canvas = None
        self._hourly_peak_var = self._hourly_date_var = None
        self._hourly_date_selector = None
        self._trend_tooltip_items.clear()
        self._configure_ttk()
        self._build_layout()
        self._schedule_refresh()

    def show_export_message(self, text: str) -> None:
        self.export_var.set(text)
        self.root.after(5000, lambda: self.export_var.set(""))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg=_BG, padx=28, pady=24)
        shell.pack(fill=tk.BOTH, expand=True)

        # Top bar
        top = tk.Frame(shell, bg=_BG)
        top.pack(fill=tk.X, pady=(0, 22))
        title = tk.Frame(top, bg=_BG)
        title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(title, text=tr(self.config.language, "today"), bg=_BG, fg=_TEXT_TERTIARY, font=("Segoe UI Semibold", 8)).pack(anchor=tk.W)
        tk.Label(title, text=tr(self.config.language, "typing_count"), bg=_BG, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 24)).pack(anchor=tk.W, pady=(5, 0))
        actions = tk.Frame(top, bg=_BG)
        actions.pack(side=tk.RIGHT, anchor=tk.NE)
        for text, callback, primary in [(tr(self.config.language, "settings"), self.open_settings_dialog, False), (tr(self.config.language, "export_csv"), self.on_export_csv, False), (tr(self.config.language, "hourly"), self.open_hourly_dialog, False), (tr(self.config.language, "history"), self.open_history_dialog, True)]:
            self._toolbar_button(actions, text, callback, primary).pack(side=tk.RIGHT, padx=(8, 0))

        # Two-column content
        content = tk.Frame(shell, bg=_BG)
        content.pack(fill=tk.BOTH, expand=True)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=5)
        content.grid_rowconfigure(0, weight=1)

        left = tk.Frame(content, bg=_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        right = tk.Frame(content, bg=_BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=3)
        right.grid_rowconfigure(1, weight=2)
        right.grid_columnconfigure(0, weight=1)

        # Hero card
        hero = self._card(left)
        hero.pack(fill=tk.X)
        tk.Label(hero, text=tr(self.config.language, "today"), bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI Semibold", 8)).pack(anchor=tk.W)
        tk.Label(hero, textvariable=self.count_var, bg=_CARD, fg=_TEXT_PRIMARY, font=("Segoe UI", 64, "bold")).pack(anchor=tk.W, pady=(6, 0))
        tk.Label(hero, textvariable=self.detail_var, bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI", 11)).pack(anchor=tk.W, pady=(2, 12))

        # Today stats
        today_stats = self._card(left)
        today_stats.pack(fill=tk.X, pady=(16, 0))
        self._metric_block(
            today_stats,
            tr(self.config.language, "group_today"),
            [
                (tr(self.config.language, "typed_today"), self.typed_today_var),
                (tr(self.config.language, "backspace_today"), self.backspace_var),
                (tr(self.config.language, "accuracy"), self.accuracy_var),
                (tr(self.config.language, "last_minute"), self.cpm_var),
                (tr(self.config.language, "peak_wpm_today"), self.peak_wpm_var),
            ],
        ).pack(fill=tk.X)

        # Context stats
        context_stats = self._card(left)
        context_stats.pack(fill=tk.X, pady=(16, 0))
        self._metric_block(
            context_stats,
            tr(self.config.language, "group_context"),
            [
                (tr(self.config.language, "yesterday"), self.yesterday_var),
                (tr(self.config.language, "seven_day_total"), self.week_var),
                (tr(self.config.language, "last_input"), self.last_input_var),
            ],
            columns=1,
        ).pack(fill=tk.X)

        # System notes
        notes = self._card(left)
        notes.pack(fill=tk.X, pady=(16, 0))
        tk.Label(notes, text="SYSTEM", bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI Semibold", 8)).pack(anchor=tk.W)
        for var, color in [(self.export_var, _SUCCESS), (self.accuracy_hint_var, _TEXT_TERTIARY), (self.count_mode_var, _TEXT_TERTIARY)]:
            tk.Label(notes, textvariable=var, bg=_CARD, fg=color, font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(12 if var is self.export_var else 0, 6))
        tk.Label(notes, text=tr(self.config.language, "paste_hint"), bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(notes, textvariable=self.settings_var, bg=_CARD, fg=_TEXT_QUATERNARY, font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 0))

        # Trend card
        trend = self._card(right)
        trend.grid(row=0, column=0, sticky="nsew")
        trend_header = tk.Frame(trend, bg=_CARD)
        trend_header.pack(fill=tk.X)
        trend_title = tk.Frame(trend_header, bg=_CARD)
        trend_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(trend_title, text=tr(self.config.language, "trend_30_days"), bg=_CARD, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 15)).pack(anchor=tk.W)
        tk.Label(trend_title, text=tr(self.config.language, "recent_days_desc"), bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI", 9), wraplength=360, justify=tk.LEFT).pack(anchor=tk.W, pady=(7, 0))
        trend_summary = tk.Frame(trend_header, bg=_CARD)
        trend_summary.pack(side=tk.RIGHT, anchor=tk.NE, padx=(20, 0))
        for label_key, var in (("trend_peak_label", self.trend_peak_var), ("trend_latest_label", self.trend_latest_var)):
            cell = tk.Frame(trend_summary, bg=_CARD)
            cell.pack(anchor=tk.E, pady=(0, 10))
            tk.Label(cell, text=tr(self.config.language, label_key), bg=_CARD, fg=_TEXT_QUATERNARY, font=("Segoe UI Semibold", 8)).pack(anchor=tk.E)
            tk.Label(cell, textvariable=var, bg=_CARD, fg=_TEXT_SECONDARY, font=("Segoe UI Semibold", 10)).pack(anchor=tk.E, pady=(5, 0))
        trend_visual = tk.Frame(trend, bg=_CHART_BG, highlightthickness=1, highlightbackground=_BORDER, padx=28, pady=26)
        trend_visual.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        self.trend_canvas = tk.Canvas(trend_visual, bg=_CHART_BG, highlightthickness=0, height=360)
        self.trend_canvas.pack(fill=tk.BOTH, expand=True)
        tk.Label(trend_visual, textvariable=self.trend_meta_var, bg=_CHART_BG, fg=_TEXT_TERTIARY, font=("Segoe UI", 9), justify=tk.LEFT, wraplength=620).pack(anchor=tk.W, pady=(16, 0))
        self.trend_canvas.bind("<Configure>", lambda _e: self._draw_trend_chart())
        self.trend_canvas.bind("<Motion>", self._on_trend_hover)
        self.trend_canvas.bind("<Leave>", self._on_trend_leave)

        # History preview card
        history = self._card(right)
        history.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        htop = tk.Frame(history, bg=_CARD)
        htop.pack(fill=tk.X)
        htitle = tk.Frame(htop, bg=_CARD)
        htitle.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(htitle, text=tr(self.config.language, "history"), bg=_CARD, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 13)).pack(anchor=tk.W)
        tk.Label(htitle, text=tr(self.config.language, "full_history_desc"), bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(5, 0))
        self._toolbar_button(htop, tr(self.config.language, "open_history"), self.open_history_dialog, False).pack(side=tk.RIGHT)
        preview_wrap = tk.Frame(history, bg=_CARD)
        preview_wrap.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        self._history_preview_canvas = tk.Canvas(preview_wrap, bg=_CARD, highlightthickness=0)
        history_scrollbar = ttk.Scrollbar(preview_wrap, orient=tk.VERTICAL, command=self._history_preview_canvas.yview)
        self._history_preview_canvas.configure(yscrollcommand=history_scrollbar.set)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._history_preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._history_preview_inner = tk.Frame(self._history_preview_canvas, bg=_CARD)
        self._history_preview_canvas.create_window((0, 0), window=self._history_preview_inner, anchor="nw")
        self._history_preview_inner.bind("<Configure>", lambda _e: self._sync_history_preview_scrollregion())
        self._history_preview_canvas.bind("<Configure>", lambda e: self._resize_history_preview_inner(e.width))
        self._history_preview_canvas.bind("<MouseWheel>", self._on_history_preview_mousewheel)
        tk.Label(history, textvariable=self.history_footer_var, bg=_CARD, fg=_TEXT_QUATERNARY, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(12, 0))

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def open_settings_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(tr(self.config.language, "settings_title"))
        dialog.geometry("540x580")
        dialog.minsize(540, 580)
        dialog.resizable(False, False)
        dialog.configure(bg=_BG)
        dialog.transient(self.root)
        dialog.grab_set()
        shell = tk.Frame(dialog, bg=_BG, padx=20, pady=20)
        shell.pack(fill=tk.BOTH, expand=True)
        card = self._card(shell)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text=tr(self.config.language, "settings_title"), bg=_CARD, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 17)).pack(anchor=tk.W)
        tk.Label(card, text=tr(self.config.language, "settings_desc"), bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(7, 20))
        count_space, count_enter = tk.BooleanVar(value=self.config.count_space), tk.BooleanVar(value=self.config.count_enter)
        backspace_decrements, start_hidden = tk.BooleanVar(value=self.config.backspace_decrements), tk.BooleanVar(value=self.config.start_hidden_to_tray)
        language_mode = tk.StringVar(value=self.config.language)
        box = self._subcard(card)
        box.pack(fill=tk.X)
        for text, var in [(tr(self.config.language, "count_space"), count_space), (tr(self.config.language, "count_enter"), count_enter), (tr(self.config.language, "backspace_subtracts"), backspace_decrements), (tr(self.config.language, "start_hidden"), start_hidden)]:
            tk.Checkbutton(box, text=text, variable=var, bg=_CARD_INNER, activebackground=_CARD_INNER, fg=_TEXT_SECONDARY, activeforeground=_TEXT_SECONDARY, selectcolor=_CARD, font=("Segoe UI", 10), anchor="w", padx=2, pady=6, relief=tk.FLAT).pack(fill=tk.X)
        tk.Label(card, text=tr(self.config.language, "language_mode"), bg=_CARD, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 10)).pack(anchor=tk.W, pady=(18, 8))
        lang = self._subcard(card)
        lang.pack(fill=tk.X)
        tk.Radiobutton(lang, text=tr(self.config.language, "lang_zh"), value="zh", variable=language_mode, bg=_CARD_INNER, activebackground=_CARD_INNER, fg=_TEXT_SECONDARY, activeforeground=_TEXT_SECONDARY, selectcolor=_CARD, font=("Segoe UI", 10)).pack(anchor=tk.W)
        tk.Radiobutton(lang, text=tr(self.config.language, "lang_en"), value="en", variable=language_mode, bg=_CARD_INNER, activebackground=_CARD_INNER, fg=_TEXT_SECONDARY, activeforeground=_TEXT_SECONDARY, selectcolor=_CARD, font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(8, 0))
        tk.Frame(card, bg=_CARD).pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        def save_settings() -> None:
            self.config.count_space = bool(count_space.get())
            self.config.count_enter = bool(count_enter.get())
            self.config.backspace_decrements = bool(backspace_decrements.get())
            self.config.start_hidden_to_tray = bool(start_hidden.get())
            changed = self.config.language != language_mode.get()
            self.config.language = language_mode.get()
            self.config.save()
            dialog.destroy()
            if changed:
                self.on_language_changed(self.config.language)
                self.refresh_language()
            self.show()

        footer = tk.Frame(shell, bg=_BG)
        footer.pack(fill=tk.X, pady=(14, 0))
        self._toolbar_button(footer, tr(self.config.language, "save"), save_settings, True).pack(side=tk.RIGHT)

    def open_history_dialog(self) -> None:
        if self._history_dialog and self._history_dialog.winfo_exists():
            self._history_dialog.deiconify()
            self._history_dialog.lift()
            self._refresh_history_dialog()
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(tr(self.config.language, "full_history"))
        dialog.geometry("900x680")
        dialog.minsize(860, 620)
        dialog.configure(bg=_BG)
        dialog.transient(self.root)
        self._history_dialog = dialog
        shell = tk.Frame(dialog, bg=_BG, padx=20, pady=20)
        shell.pack(fill=tk.BOTH, expand=True)
        card = self._card(shell)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text=tr(self.config.language, "full_history"), bg=_CARD, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 17)).pack(anchor=tk.W)
        tk.Label(card, text=tr(self.config.language, "full_history_desc"), bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(7, 16))
        wrap = tk.Frame(card, bg=_CARD)
        wrap.pack(fill=tk.BOTH, expand=True)
        cols = ("date", "count", "typed", "pasted", "backspace", "accuracy", "peak_wpm")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", style="TypeRecord.Treeview")
        for col, label in [("date", "history_columns_date"), ("count", "history_columns_count"), ("typed", "history_columns_typed"), ("pasted", "history_columns_pasted"), ("backspace", "history_columns_backspace"), ("accuracy", "history_columns_accuracy"), ("peak_wpm", "history_columns_peak_wpm")]:
            tree.heading(col, text=tr(self.config.language, label))
        tree.column("date", width=150, anchor=tk.W)
        for col in ("count", "typed", "pasted", "backspace", "accuracy", "peak_wpm"):
            tree.column(col, width=92, anchor=tk.E)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._history_tree = tree
        dialog.protocol("WM_DELETE_WINDOW", self._close_history_dialog)
        self._refresh_history_dialog()

    def open_hourly_dialog(self) -> None:
        if self._hourly_dialog and self._hourly_dialog.winfo_exists():
            self._hourly_dialog.deiconify()
            self._hourly_dialog.lift()
            self._refresh_hourly_dialog()
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(tr(self.config.language, "hourly_today"))
        dialog.geometry("920x700")
        dialog.minsize(880, 640)
        dialog.configure(bg=_BG)
        dialog.transient(self.root)
        self._hourly_dialog = dialog
        shell = tk.Frame(dialog, bg=_BG, padx=20, pady=20)
        shell.pack(fill=tk.BOTH, expand=True)
        card = self._card(shell)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text=tr(self.config.language, "hourly_today"), bg=_CARD, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 17)).pack(anchor=tk.W)
        tk.Label(card, text=tr(self.config.language, "hourly_today_desc"), bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(7, 14))
        row = tk.Frame(card, bg=_CARD)
        row.pack(fill=tk.X, pady=(0, 12))
        tk.Label(row, text=tr(self.config.language, "hourly_date"), bg=_CARD, fg=_TEXT_SECONDARY, font=("Segoe UI Semibold", 9)).pack(side=tk.LEFT)
        self._hourly_date_var = tk.StringVar(value=self._today_date_str())
        self._hourly_date_selector = ttk.Combobox(row, textvariable=self._hourly_date_var, state="readonly", width=16, values=self._available_history_dates(), style="TypeRecord.TCombobox")
        self._hourly_date_selector.pack(side=tk.LEFT, padx=(10, 0))
        self._hourly_date_selector.bind("<<ComboboxSelected>>", lambda _e: self._refresh_hourly_dialog())
        self._hourly_peak_var = tk.StringVar(value="")
        tk.Label(card, textvariable=self._hourly_peak_var, bg=_CARD, fg=_TEXT_SECONDARY, font=("Segoe UI Semibold", 10)).pack(anchor=tk.W, pady=(0, 14))
        graph = self._subcard(card)
        graph.pack(fill=tk.X)
        self._hourly_canvas = tk.Canvas(graph, bg=_CHART_BG, highlightthickness=0, height=250)
        self._hourly_canvas.pack(fill=tk.BOTH, expand=True)
        self._hourly_canvas.bind("<Configure>", lambda _e: self._draw_hourly_chart())
        wrap = tk.Frame(card, bg=_CARD)
        wrap.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        tree = ttk.Treeview(wrap, columns=("hour", "typed", "pasted", "total"), show="headings", style="TypeRecord.Treeview")
        for col, label in [("hour", "hourly_table_hour"), ("typed", "hourly_table_typed"), ("pasted", "hourly_table_pasted"), ("total", "hourly_table_total")]:
            tree.heading(col, text=tr(self.config.language, label))
        tree.column("hour", width=120, anchor=tk.W)
        for col in ("typed", "pasted", "total"):
            tree.column(col, width=120, anchor=tk.E)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._hourly_tree = tree
        dialog.protocol("WM_DELETE_WINDOW", self._close_hourly_dialog)
        self._refresh_hourly_dialog()

    # ------------------------------------------------------------------
    # Dialog refresh helpers
    # ------------------------------------------------------------------
    def _refresh_history_dialog(self) -> None:
        if self._history_tree is None:
            return
        self._history_tree.delete(*self._history_tree.get_children())
        for item in self.store.get_full_history():
            self._history_tree.insert("", tk.END, values=(item["date"], item["count"], item["typed"], item["pasted"], item["backspace"], f"{item['accuracy'] * 100:.1f}%", f"{item['peak_wpm']:.1f}"))

    def _refresh_hourly_dialog(self) -> None:
        if self._hourly_tree is None:
            return
        dates = self._available_history_dates()
        selected = self._selected_hourly_date()
        if self._hourly_date_selector is not None:
            self._hourly_date_selector["values"] = dates
        if selected not in dates:
            selected = dates[0]
            if self._hourly_date_var is not None:
                self._hourly_date_var.set(selected)
        data = self.store.get_hourly_distribution(selected)
        self._hourly_tree.delete(*self._hourly_tree.get_children())
        for item in data:
            self._hourly_tree.insert("", tk.END, values=(f"{item['hour']}:00", item["typed"], item["pasted"], item["total"]))
        if self._hourly_peak_var is not None:
            peak = max(data, key=lambda item: item["total"], default=None)
            self._hourly_peak_var.set(f"{tr(self.config.language, 'hourly_peak')}: {selected}  {peak['hour']}:00  {peak['total']}" if peak and peak["total"] > 0 else tr(self.config.language, "hourly_empty"))
        self._draw_hourly_chart()

    # ------------------------------------------------------------------
    # Periodic refresh
    # ------------------------------------------------------------------
    def _schedule_refresh(self) -> None:
        summary, live = self.store.get_summary(), self.counter.get_live_stats()
        full_history = self.store.get_full_history()
        self._latest_trend_history = self.store.get_trend_history(days=30)
        self.count_var.set(str(summary["today_count"]))
        self.detail_var.set(tr(self.config.language, "today_detail", count=summary["today_count"]))
        delta = live["session_delta"]
        prefix = "+" if delta >= 0 else ""
        if live["session_duration_seconds"] > 0 or delta != 0:
            self.session_var.set(tr(self.config.language, "session_current" if live["session_is_active"] else "session_last", value=f"{prefix}{delta}"))
        else:
            self.session_var.set(tr(self.config.language, "session_none"))
        self.session_length_var.set(self._format_duration(live["session_duration_seconds"]))
        self.session_typed_var.set(str(live["session_positive_count"]))
        self.session_pasted_var.set(str(live["session_pasted_count"]))
        self.session_accuracy_var.set(f"{live['session_accuracy'] * 100:.1f}%")
        self.typed_today_var.set(str(summary["typed_today"]))
        self.pasted_today_var.set(str(summary["pasted_today"]))
        self.backspace_var.set(str(summary["backspace_today"]))
        self.accuracy_var.set(f"{summary['accuracy'] * 100:.1f}%")
        self.cpm_var.set(tr(self.config.language, "cpm", count=live["recent_cpm"]))
        self.peak_wpm_var.set(f"{summary['peak_wpm_today']:.1f}")
        self.yesterday_var.set(str(summary["yesterday_count"]))
        self.week_var.set(str(summary["last_7_days_total"]))
        self.last_input_var.set(self._format_last_input(summary["last_input_at"] or live["last_input_at"]))
        self.count_mode_var.set(tr(self.config.language, "count_mode_subtracts" if self.config.backspace_decrements else "count_mode_ignored"))
        self.accuracy_hint_var.set(tr(self.config.language, "accuracy_hint", kept=summary["kept_today"], typed=summary["typed_today"]))
        self.settings_var.set(tr(self.config.language, "stored_settings", space=tr(self.config.language, "on") if self.config.count_space else tr(self.config.language, "off"), enter=tr(self.config.language, "on") if self.config.count_enter else tr(self.config.language, "off"), backspace=tr(self.config.language, "subtracts") if self.config.backspace_decrements else tr(self.config.language, "ignored"), hidden=tr(self.config.language, "on") if self.config.start_hidden_to_tray else tr(self.config.language, "off"), lang_name=tr(self.config.language, "language_name")))
        self.history_footer_var.set(tr(self.config.language, "days_recorded", count=len(full_history)))
        self._update_trend_meta()
        self._ensure_history_preview_rows(len(full_history))
        for i, row in enumerate(self.history_vars):
            if i < len(full_history):
                day = full_history[i]
                row["date"].set(day["date"])
                row["count"].set(str(day["count"]))
                row["meta"].set(
                    tr(
                        self.config.language,
                        "history_preview_meta",
                        typed=day["typed"],
                        pasted=day["pasted"],
                        accuracy=f"{day['accuracy'] * 100:.1f}%",
                    )
                )
            else:
                row["date"].set("-")
                row["count"].set("0")
                row["meta"].set("")
        self._sync_history_preview_scrollregion()
        self._draw_trend_chart()
        self._refresh_history_dialog()
        self._refresh_hourly_dialog()
        self._refresh_after_id = self.root.after(self.config.refresh_interval_ms, self._schedule_refresh)

    def _update_trend_meta(self) -> None:
        non_zero = [item for item in self._latest_trend_history if item["count"] > 0]
        if not non_zero:
            self.trend_meta_var.set(tr(self.config.language, "trend_empty"))
            self.trend_peak_var.set(tr(self.config.language, "trend_empty"))
            self.trend_latest_var.set(tr(self.config.language, "trend_empty"))
            return
        peak = max(non_zero, key=lambda item: item["count"])
        latest = self._latest_trend_history[-1]
        self.trend_peak_var.set(f"{peak['count']}  {peak['date']}")
        self.trend_latest_var.set(f"{latest['count']}  {latest['date']}")
        if self.config.language == "zh":
            self.trend_meta_var.set(f"峰值 {peak['count']}  {peak['date']}  |  最新 {latest['count']}  {latest['date']}")
        else:
            self.trend_meta_var.set(f"Peak {peak['count']}  {peak['date']}  |  Latest {latest['count']}  {latest['date']}")

    # ------------------------------------------------------------------
    # Trend chart
    # ------------------------------------------------------------------
    def _draw_trend_chart(self) -> None:
        canvas = self.trend_canvas
        canvas.delete("all")
        data = self._latest_trend_history
        if not data:
            return

        width = max(canvas.winfo_width(), 560)
        height = max(canvas.winfo_height(), 320)
        ml, mr, mt, mb = 52, 18, 18, 38
        cw, ch = width - ml - mr, height - mt - mb

        # Background
        canvas.create_rectangle(0, 0, width, height, fill=_CHART_BG, outline="")

        max_count = max((item["count"] for item in data), default=0)
        if max_count <= 0:
            canvas.create_text(
                width / 2, height / 2,
                text=tr(self.config.language, "trend_empty"),
                fill=_TEXT_TERTIARY, font=("Segoe UI", 11),
            )
            return

        plot_max = max_count * 1.15

        # Y-axis grid lines and labels
        num_grid = 5
        for i in range(num_grid + 1):
            ratio = i / num_grid
            y = mt + ch * ratio
            value = int(plot_max * (1 - ratio))
            canvas.create_line(ml, y, width - mr, y, fill=_CHART_GRID, width=1, dash=(2, 4))
            canvas.create_text(
                ml - 8, y,
                text=self._format_axis_value(value),
                fill=_TEXT_QUATERNARY, font=("Segoe UI", 8), anchor="e",
            )

        # Compute data point coordinates
        n = len(data)
        coords: list[tuple[float, float, dict]] = []
        flat_points: list[float] = []
        for index, item in enumerate(data):
            x = ml + cw * index / (n - 1) if n > 1 else ml
            y = mt + ch * (1 - item["count"] / plot_max)
            # Clamp to chart area to prevent spline overshoot
            y = max(mt, min(mt + ch, y))
            coords.append((x, y, item))
            flat_points.extend([x, y])

        # Area fill (smooth polygon)
        area_coords: list[float] = [ml, mt + ch] + flat_points + [width - mr, mt + ch]
        canvas.create_polygon(*area_coords, fill=_ACCENT_LIGHT, outline="", smooth=True, splinesteps=36)

        # Main line (smooth)
        if len(flat_points) >= 4:
            canvas.create_line(
                *flat_points, fill=_ACCENT, width=2.5, smooth=True,
                splinesteps=36, capstyle=tk.ROUND, joinstyle=tk.ROUND,
            )
        elif len(flat_points) >= 2:
            canvas.create_line(*flat_points, fill=_ACCENT, width=2.5, capstyle=tk.ROUND)

        # X-axis date labels
        self._draw_x_axis_labels(canvas, data, ml, mr, width, height)

        # Peak annotation (always visible)
        peak_coord = max(coords, key=lambda c: c[2]["count"])
        if peak_coord[2]["count"] > 0:
            self._draw_peak_annotation(canvas, peak_coord, mt)

        # Latest point marker
        latest = coords[-1]
        if latest[2]["count"] > 0:
            lx, ly = latest[0], latest[1]
            canvas.create_oval(lx - 7, ly - 7, lx + 7, ly + 7, fill=_ACCENT_LIGHT, outline="")
            canvas.create_oval(lx - 4, ly - 4, lx + 4, ly + 4, fill=_ACCENT, outline="")

    def _draw_x_axis_labels(self, canvas: tk.Canvas, data: list[dict], ml: int, mr: int, width: int, height: int) -> None:
        n = len(data)
        if n == 0:
            return
        num_labels = min(7, n)
        if n == 1:
            canvas.create_text(ml, height - 14, text=data[0]["date"][5:], fill=_TEXT_QUATERNARY, font=("Segoe UI", 8), anchor="n")
            return
        step = max(1, (n - 1) // (num_labels - 1))
        cw = width - ml - mr
        drawn = set()
        for i in range(0, n, step):
            x = ml + cw * i / (n - 1)
            date_str = data[i]["date"][5:]
            canvas.create_text(x, height - 14, text=date_str, fill=_TEXT_QUATERNARY, font=("Segoe UI", 8), anchor="n")
            drawn.add(i)
        # Always show last date
        if (n - 1) not in drawn:
            x = ml + cw
            canvas.create_text(x, height - 14, text=data[-1]["date"][5:], fill=_TEXT_QUATERNARY, font=("Segoe UI", 8), anchor="n")

    def _draw_peak_annotation(self, canvas: tk.Canvas, coord: tuple[float, float, dict], mt: int) -> None:
        px, py, item = coord
        peak_value = item["count"]
        label = f"{peak_value:,}"
        approx_w = len(label) * 8 + 16
        approx_h = 22

        # Decide position: prefer above, flip below if too close to top
        if py - 36 > mt:
            tip_y = py - 30
            pointer_tip = py - 6
        else:
            tip_y = py + 30
            pointer_tip = py + 6

        # Shadow (offset 2px)
        canvas.create_rectangle(
            px - approx_w / 2 + 2, tip_y - approx_h / 2 + 2,
            px + approx_w / 2 + 2, tip_y + approx_h / 2 + 2,
            fill="#D0D3DC", outline="",
        )
        # Background pill
        canvas.create_rectangle(
            px - approx_w / 2, tip_y - approx_h / 2,
            px + approx_w / 2, tip_y + approx_h / 2,
            fill=_TEXT_PRIMARY, outline="",
        )
        # Small triangle pointer
        if tip_y < py:
            canvas.create_polygon(px - 5, tip_y + approx_h / 2, px + 5, tip_y + approx_h / 2, px, pointer_tip, fill=_TEXT_PRIMARY, outline="")
        else:
            canvas.create_polygon(px - 5, tip_y - approx_h / 2, px + 5, tip_y - approx_h / 2, px, pointer_tip, fill=_TEXT_PRIMARY, outline="")
        # Text
        canvas.create_text(px, tip_y, text=label, fill="#FFFFFF", font=("Segoe UI Semibold", 9))

        # Peak point marker
        canvas.create_oval(px - 6, py - 6, px + 6, py + 6, fill="#FFFFFF", outline=_BORDER)
        canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill=_ACCENT, outline="")

    # ------------------------------------------------------------------
    # Trend chart hover tooltip
    # ------------------------------------------------------------------
    def _on_trend_hover(self, event: tk.Event) -> None:
        canvas = self.trend_canvas
        data = self._latest_trend_history
        if not data:
            return

        # Remove previous tooltip
        for item_id in self._trend_tooltip_items:
            canvas.delete(item_id)
        self._trend_tooltip_items.clear()

        width = max(canvas.winfo_width(), 560)
        height = max(canvas.winfo_height(), 320)
        ml, mr, mt, mb = 52, 18, 18, 38
        cw, ch = width - ml - mr, height - mt - mb

        mouse_x = event.x
        if mouse_x < ml - 10 or mouse_x > width - mr + 10:
            return

        n = len(data)
        if n == 0:
            return
        max_count = max((d["count"] for d in data), default=0)
        if max_count <= 0:
            return
        plot_max = max_count * 1.15

        index = round((mouse_x - ml) / cw * (n - 1)) if n > 1 else 0
        index = max(0, min(n - 1, index))
        item = data[index]

        x = ml + cw * index / (n - 1) if n > 1 else ml
        y = mt + ch * (1 - item["count"] / plot_max)
        y = max(mt, min(mt + ch, y))

        # Vertical crosshair
        line_id = canvas.create_line(x, mt, x, mt + ch, fill=_ACCENT_SOFT, width=1, dash=(3, 3))
        self._trend_tooltip_items.append(line_id)

        # Highlighted data point
        marker_outer = canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#FFFFFF", outline=_ACCENT, width=2)
        marker_inner = canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=_ACCENT, outline="")
        self._trend_tooltip_items.extend([marker_outer, marker_inner])

        # Tooltip box
        date_str = item["date"]
        count_str = f"{item['count']:,}"
        tooltip_text = f"{date_str}  {count_str}"
        approx_tip_w = len(tooltip_text) * 7 + 20
        approx_tip_h = 28

        # Position: prefer above the point
        if y > mt + 60:
            tip_y = y - 38
            pointer_tip = y - 10
            pointer_base = tip_y + approx_tip_h / 2
        else:
            tip_y = y + 38
            pointer_tip = y + 10
            pointer_base = tip_y - approx_tip_h / 2

        tip_x = max(ml + approx_tip_w / 2, min(width - mr - approx_tip_w / 2, x))

        # Shadow
        bg_shadow = canvas.create_rectangle(
            tip_x - approx_tip_w / 2 + 2, tip_y - approx_tip_h / 2 + 2,
            tip_x + approx_tip_w / 2 + 2, tip_y + approx_tip_h / 2 + 2,
            fill="#C8CBD5", outline="",
        )
        # Background
        bg = canvas.create_rectangle(
            tip_x - approx_tip_w / 2, tip_y - approx_tip_h / 2,
            tip_x + approx_tip_w / 2, tip_y + approx_tip_h / 2,
            fill=_TEXT_PRIMARY, outline="",
        )
        # Triangle pointer
        if tip_y < y:
            pointer = canvas.create_polygon(
                tip_x - 5, pointer_base, tip_x + 5, pointer_base, tip_x, pointer_tip,
                fill=_TEXT_PRIMARY, outline="",
            )
        else:
            pointer = canvas.create_polygon(
                tip_x - 5, pointer_base, tip_x + 5, pointer_base, tip_x, pointer_tip,
                fill=_TEXT_PRIMARY, outline="",
            )
        # Text
        text = canvas.create_text(tip_x, tip_y, text=tooltip_text, fill="#FFFFFF", font=("Segoe UI Semibold", 9))
        self._trend_tooltip_items.extend([bg_shadow, bg, pointer, text])

    def _on_trend_leave(self, event: tk.Event) -> None:
        for item_id in self._trend_tooltip_items:
            self.trend_canvas.delete(item_id)
        self._trend_tooltip_items.clear()

    # ------------------------------------------------------------------
    # Hourly bar chart
    # ------------------------------------------------------------------
    def _draw_hourly_chart(self) -> None:
        if self._hourly_canvas is None:
            return
        canvas = self._hourly_canvas
        canvas.delete("all")
        data = self.store.get_hourly_distribution(self._selected_hourly_date())

        width = max(canvas.winfo_width(), 620)
        height = max(canvas.winfo_height(), 220)
        ml, mr, mt, mb = 44, 16, 20, 28
        cw, ch = width - ml - mr, height - mt - mb

        max_total = max((item["total"] for item in data), default=0)
        if max_total <= 0:
            canvas.create_text(
                width / 2, height / 2,
                text=tr(self.config.language, "hourly_empty"),
                fill=_TEXT_TERTIARY, font=("Segoe UI", 10),
            )
            return

        # Y-axis grid lines and labels
        num_grid = 4
        for i in range(num_grid + 1):
            ratio = i / num_grid
            y = mt + ch * ratio
            value = int(max_total * (1 - ratio))
            canvas.create_line(ml, y, width - mr, y, fill=_CHART_GRID, width=1, dash=(2, 4))
            canvas.create_text(
                ml - 8, y,
                text=self._format_axis_value(value),
                fill=_TEXT_QUATERNARY, font=("Segoe UI", 8), anchor="e",
            )

        slot_width = cw / 24
        bar_width = min(28, max(10, int(slot_width) - 8))
        baseline = mt + ch

        # Baseline
        canvas.create_line(ml, baseline, width - mr, baseline, fill=_CHART_GRID, width=1)

        for i, item in enumerate(data):
            x = ml + i * slot_width + (slot_width - bar_width) / 2
            typed_height = 0
            pasted_height = 0
            if item["typed"] > 0:
                typed_height = max(4, ch * item["typed"] / max_total)
            if item["pasted"] > 0:
                pasted_height = max(4, ch * item["pasted"] / max_total)

            # Typed bar (bottom, rounded top)
            if item["typed"] > 0:
                r = min(5, typed_height / 2)
                self._rounded_top_bar(
                    canvas,
                    x, baseline - typed_height, x + bar_width, baseline,
                    r=r, fill=_HOURLY_TYPED, outline="",
                )

            # Pasted bar (stacked on top of typed, rounded top)
            if item["pasted"] > 0:
                r = min(5, pasted_height / 2)
                self._rounded_top_bar(
                    canvas,
                    x, baseline - typed_height - pasted_height, x + bar_width, baseline - typed_height,
                    r=r, fill=_HOURLY_PASTED, outline="",
                )

            # X-axis label every 4 hours
            if i % 4 == 0:
                canvas.create_text(
                    x + bar_width / 2, height - 10,
                    text=item["hour"], fill=_TEXT_QUATERNARY, font=("Segoe UI", 8),
                )

    def _rounded_top_bar(self, canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float = 5, **kwargs) -> int:
        if y2 - y1 < r * 2:
            return canvas.create_rectangle(x1, y1, x2, y2, **kwargs)
        points = [
            x1, y2,
            x1, y1 + r,
            x1 + r, y1,
            x2 - r, y1,
            x2, y1 + r,
            x2, y2,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    # ------------------------------------------------------------------
    # History preview rows
    # ------------------------------------------------------------------
    def _ensure_history_preview_rows(self, count: int) -> None:
        if self._history_preview_inner is None:
            return
        while len(self.history_vars) < count:
            row_vars = {
                "date": tk.StringVar(value="-"),
                "count": tk.StringVar(value="0"),
                "meta": tk.StringVar(value=""),
            }
            self.history_vars.append(row_vars)
            row_card = tk.Frame(self._history_preview_inner, bg=_CARD_INNER, highlightthickness=1, highlightbackground=_BORDER_INNER, padx=14, pady=12)
            row_card.pack(fill=tk.X, pady=5)
            row_head = tk.Frame(row_card, bg=_CARD_INNER)
            row_head.pack(fill=tk.X)
            tk.Label(row_head, textvariable=row_vars["date"], bg=_CARD_INNER, fg=_TEXT_TERTIARY, font=("Segoe UI Semibold", 9)).pack(side=tk.LEFT)
            tk.Label(row_head, textvariable=row_vars["count"], bg=_CARD_INNER, fg=_TEXT_SECONDARY, font=("Segoe UI Semibold", 15)).pack(side=tk.RIGHT)
            tk.Label(row_card, textvariable=row_vars["meta"], bg=_CARD_INNER, fg=_TEXT_TERTIARY, font=("Segoe UI", 9), justify=tk.LEFT, wraplength=360).pack(anchor=tk.W, pady=(8, 0))

        while len(self.history_vars) > count:
            row_vars = self.history_vars.pop()
            last_child = self._history_preview_inner.winfo_children()[-1]
            last_child.destroy()

    def _sync_history_preview_scrollregion(self) -> None:
        if self._history_preview_canvas is None or self._history_preview_inner is None:
            return
        self._history_preview_canvas.configure(scrollregion=self._history_preview_canvas.bbox("all"))

    def _resize_history_preview_inner(self, width: int) -> None:
        if self._history_preview_canvas is None or self._history_preview_inner is None:
            return
        items = self._history_preview_canvas.find_all()
        if items:
            self._history_preview_canvas.itemconfigure(items[0], width=width)

    def _on_history_preview_mousewheel(self, event) -> str:
        if self._history_preview_canvas is not None:
            self._history_preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _close_history_dialog(self) -> None:
        if self._history_dialog and self._history_dialog.winfo_exists():
            self._history_dialog.destroy()
        self._history_dialog = None
        self._history_tree = None

    def _close_hourly_dialog(self) -> None:
        if self._hourly_dialog and self._hourly_dialog.winfo_exists():
            self._hourly_dialog.destroy()
        self._hourly_dialog = None
        self._hourly_tree = None
        self._hourly_canvas = None
        self._hourly_peak_var = None
        self._hourly_date_var = None
        self._hourly_date_selector = None

    # ------------------------------------------------------------------
    # UI building blocks
    # ------------------------------------------------------------------
    def _button(self, parent: tk.Widget, text: str, command, primary: bool) -> tk.Button:
        if primary:
            return tk.Button(
                parent, text=text, command=command,
                bg=_ACCENT, fg="#FFFFFF", activebackground="#4F5AB8", activeforeground="#FFFFFF",
                relief=tk.FLAT, padx=14, pady=6,
                font=("Segoe UI Semibold", 9),
                highlightthickness=1, highlightbackground=_ACCENT, bd=0,
            )
        return tk.Button(
            parent, text=text, command=command,
            bg=_CARD, fg=_ACCENT, activebackground=_ACCENT_LIGHT, activeforeground=_ACCENT,
            relief=tk.FLAT, padx=14, pady=6,
            font=("Segoe UI Semibold", 9),
            highlightthickness=1, highlightbackground=_BORDER_INNER, bd=0,
        )

    def _toolbar_button(self, parent: tk.Widget, text: str, command, primary: bool) -> tk.Button:
        if primary:
            return tk.Button(
                parent, text=text, command=command,
                bg=_ACCENT, fg="#FFFFFF", activebackground="#4F5AB8", activeforeground="#FFFFFF",
                relief=tk.FLAT, padx=14, pady=6,
                font=("Segoe UI Semibold", 9),
                highlightthickness=1, highlightbackground=_ACCENT, bd=0,
            )
        return tk.Button(
            parent, text=text, command=command,
            bg=_CARD, fg=_ACCENT, activebackground=_ACCENT_LIGHT, activeforeground=_ACCENT,
            relief=tk.FLAT, padx=14, pady=6,
            font=("Segoe UI Semibold", 9),
            highlightthickness=1, highlightbackground=_BORDER_INNER, bd=0,
        )

    def _card(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(parent, bg=_CARD, highlightthickness=1, highlightbackground=_BORDER, padx=24, pady=22)

    def _subcard(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(parent, bg=_CARD_INNER, highlightthickness=1, highlightbackground=_BORDER_INNER, padx=18, pady=16)

    def _tile(self, parent: tk.Frame, title: str, var: tk.StringVar, row: int, col: int) -> None:
        tile = tk.Frame(parent, bg=_CARD_INNER, highlightthickness=1, highlightbackground=_BORDER_INNER, padx=14, pady=12)
        tile.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        tk.Label(tile, text=title, bg=_CARD_INNER, fg=_TEXT_TERTIARY, font=("Segoe UI", 9)).pack(anchor=tk.W)
        tk.Label(tile, textvariable=var, bg=_CARD_INNER, fg=_TEXT_PRIMARY, font=("Segoe UI Semibold", 11), wraplength=210, justify=tk.LEFT).pack(anchor=tk.W, pady=(7, 0))

    def _metric_block(self, parent: tk.Widget, title: str, items: list[tuple[str, tk.StringVar]], columns: int = 2) -> tk.Frame:
        block = tk.Frame(parent, bg=_CARD)
        tk.Label(block, text=title, bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI Semibold", 8)).pack(anchor=tk.W)
        grid = tk.Frame(block, bg=_CARD)
        grid.pack(fill=tk.X, pady=(16, 0))
        for column in range(columns):
            grid.grid_columnconfigure(column, weight=1)

        for index, (label, var) in enumerate(items):
            row = index // columns
            column = index % columns
            cell = tk.Frame(grid, bg=_CARD, padx=2, pady=14)
            cell.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else 14, 0), pady=0)
            tk.Label(cell, text=label, bg=_CARD, fg=_TEXT_TERTIARY, font=("Segoe UI Semibold", 8)).pack(anchor=tk.W)
            tk.Label(cell, textvariable=var, bg=_CARD, fg=_TEXT_SECONDARY, font=("Segoe UI Semibold", 16), wraplength=210, justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 0))
            if columns > 1 and column == 0:
                divider = tk.Frame(cell, bg=_BORDER_INNER, width=1, height=44)
                divider.place(relx=1.02, rely=0.5, anchor="w")

        return block

    def _trend_stat(self, parent: tk.Widget, title: str, var: tk.StringVar) -> tk.Frame:
        stat = tk.Frame(parent, bg=_CARD_INNER, highlightthickness=1, highlightbackground=_BORDER_INNER, padx=14, pady=12)
        tk.Label(stat, text=title, bg=_CARD_INNER, fg=_TEXT_TERTIARY, font=("Segoe UI Semibold", 8)).pack(anchor=tk.W)
        tk.Label(stat, textvariable=var, bg=_CARD_INNER, fg=_TEXT_SECONDARY, font=("Segoe UI Semibold", 10)).pack(anchor=tk.W, pady=(6, 0))
        return stat

    # ------------------------------------------------------------------
    # ttk theme
    # ------------------------------------------------------------------
    def _configure_ttk(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TypeRecord.Treeview", background=_CARD, fieldbackground=_CARD, foreground=_TEXT_PRIMARY, rowheight=36, borderwidth=0, relief="flat")
        style.configure("TypeRecord.Treeview.Heading", background=_CARD_INNER, foreground=_TEXT_TERTIARY, relief="flat", font=("Segoe UI Semibold", 9))
        style.map("TypeRecord.Treeview", background=[("selected", _ACCENT_LIGHT)], foreground=[("selected", _TEXT_PRIMARY)])
        style.configure("TypeRecord.TCombobox", fieldbackground=_CARD, background=_CARD, foreground=_TEXT_SECONDARY, arrowcolor=_TEXT_TERTIARY, bordercolor=_BORDER, lightcolor=_BORDER, darkcolor=_BORDER)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _cancel_refresh(self) -> None:
        if self._refresh_after_id is not None:
            try:
                self.root.after_cancel(self._refresh_after_id)
            except tk.TclError:
                pass
            self._refresh_after_id = None

    def _available_history_dates(self) -> list[str]:
        dates = [item["date"] for item in self.store.get_full_history()]
        return dates or [self._today_date_str()]

    def _selected_hourly_date(self) -> str:
        return self._hourly_date_var.get().strip() if self._hourly_date_var and self._hourly_date_var.get().strip() else self._today_date_str()

    def _today_date_str(self) -> str:
        return datetime.now().date().isoformat()

    def _format_last_input(self, last_input_at: str | None) -> str:
        if not last_input_at:
            return tr(self.config.language, "no_input")
        try:
            return datetime.fromisoformat(last_input_at).strftime("%H:%M:%S")
        except ValueError:
            return tr(self.config.language, "unknown")

    def _format_duration(self, seconds: int) -> str:
        seconds = max(0, seconds)
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours > 0 else f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def _format_axis_value(value: int) -> str:
        if value >= 10000:
            return f"{value / 1000:.0f}k"
        if value >= 1000:
            return f"{value / 1000:.1f}k"
        return str(value)
