from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Callable

from type_record.config import AppConfig
from type_record.counter import KeyboardCounter
from type_record.i18n import tr
from type_record.storage import DailyCountStore


class CounterWindow:
    def __init__(self, config: AppConfig, store: DailyCountStore, counter: KeyboardCounter, on_export_csv: Callable[[], None], on_language_changed: Callable[[str], None]) -> None:
        self.config, self.store, self.counter = config, store, counter
        self.on_export_csv, self.on_language_changed = on_export_csv, on_language_changed
        self.root = tk.Tk()
        self.root.title(config.app_name)
        self.root.geometry("1100x760")
        self.root.minsize(1040, 720)
        self.root.configure(bg="#F4F4F6")
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

        self.history_vars: list[tuple[tk.StringVar, tk.StringVar]] = []
        self._latest_trend_history: list[dict] = []
        self._history_dialog: tk.Toplevel | None = None
        self._history_tree: ttk.Treeview | None = None
        self._hourly_dialog: tk.Toplevel | None = None
        self._hourly_tree: ttk.Treeview | None = None
        self._hourly_canvas: tk.Canvas | None = None
        self._hourly_peak_var: tk.StringVar | None = None
        self._hourly_date_var: tk.StringVar | None = None
        self._hourly_date_selector: ttk.Combobox | None = None
        self._refresh_after_id: str | None = None

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
        self._hourly_canvas = None
        self._hourly_peak_var = self._hourly_date_var = None
        self._hourly_date_selector = None
        self._configure_ttk()
        self._build_layout()
        self._schedule_refresh()

    def show_export_message(self, text: str) -> None:
        self.export_var.set(text)
        self.root.after(5000, lambda: self.export_var.set(""))

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg="#F4F4F6", padx=22, pady=22); shell.pack(fill=tk.BOTH, expand=True)
        top = tk.Frame(shell, bg="#F4F4F6"); top.pack(fill=tk.X, pady=(0, 18))
        title = tk.Frame(top, bg="#F4F4F6"); title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(title, text=tr(self.config.language, "today"), bg="#F4F4F6", fg="#969CA4", font=("Segoe UI Semibold", 10)).pack(anchor=tk.W)
        tk.Label(title, text=tr(self.config.language, "typing_count"), bg="#F4F4F6", fg="#17181C", font=("Segoe UI Semibold", 20)).pack(anchor=tk.W, pady=(4, 0))
        actions = tk.Frame(top, bg="#F4F4F6"); actions.pack(side=tk.RIGHT)
        for text, callback, primary in [(tr(self.config.language, "settings"), self.open_settings_dialog, False), (tr(self.config.language, "export_csv"), self.on_export_csv, False), (tr(self.config.language, "hourly"), self.open_hourly_dialog, False), (tr(self.config.language, "history"), self.open_history_dialog, True)]:
            self._button(actions, text, callback, primary).pack(side=tk.RIGHT, padx=(8, 0))

        content = tk.Frame(shell, bg="#F4F4F6"); content.pack(fill=tk.BOTH, expand=True); content.grid_columnconfigure(0, weight=3); content.grid_columnconfigure(1, weight=4); content.grid_rowconfigure(0, weight=1)
        left = tk.Frame(content, bg="#F4F4F6"); left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        right = tk.Frame(content, bg="#F4F4F6"); right.grid(row=0, column=1, sticky="nsew"); right.grid_rowconfigure(0, weight=3); right.grid_rowconfigure(1, weight=2); right.grid_columnconfigure(0, weight=1)

        hero = self._card(left); hero.pack(fill=tk.X)
        tk.Label(hero, textvariable=self.count_var, bg="#FFFFFF", fg="#17181C", font=("Segoe UI", 56, "bold")).pack(anchor=tk.W)
        tk.Label(hero, textvariable=self.detail_var, bg="#FFFFFF", fg="#7C828B", font=("Segoe UI", 11)).pack(anchor=tk.W, pady=(4, 8))
        tk.Label(hero, textvariable=self.session_var, bg="#FFFFFF", fg="#397BFF", font=("Segoe UI Semibold", 11)).pack(anchor=tk.W)

        stats = self._card(left); stats.pack(fill=tk.X, pady=(14, 0))
        grid = tk.Frame(stats, bg="#FFFFFF"); grid.pack(fill=tk.X)
        for c in range(2): grid.grid_columnconfigure(c, weight=1)
        items = [(tr(self.config.language, "typed_today"), self.typed_today_var), (tr(self.config.language, "pasted_today"), self.pasted_today_var), (tr(self.config.language, "backspace_today"), self.backspace_var), (tr(self.config.language, "accuracy"), self.accuracy_var), (tr(self.config.language, "session_typed"), self.session_typed_var), (tr(self.config.language, "session_pasted"), self.session_pasted_var), (tr(self.config.language, "session_accuracy"), self.session_accuracy_var), (tr(self.config.language, "session_length"), self.session_length_var), (tr(self.config.language, "last_minute"), self.cpm_var), (tr(self.config.language, "peak_wpm_today"), self.peak_wpm_var), (tr(self.config.language, "yesterday"), self.yesterday_var), (tr(self.config.language, "seven_day_total"), self.week_var), (tr(self.config.language, "last_input"), self.last_input_var)]
        for i, (label, var) in enumerate(items): self._tile(grid, label, var, i // 2, i % 2)

        notes = self._card(left); notes.pack(fill=tk.X, pady=(14, 0))
        for var, color in [(self.export_var, "#397BFF"), (self.accuracy_hint_var, "#8A9099"), (self.count_mode_var, "#8A9099")]:
            tk.Label(notes, textvariable=var, bg="#FFFFFF", fg=color, font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(notes, text=tr(self.config.language, "paste_hint"), bg="#FFFFFF", fg="#8A9099", font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(notes, text=tr(self.config.language, "session_hint", minutes=max(1, self.config.session_timeout_seconds // 60)), bg="#FFFFFF", fg="#8A9099", font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(notes, textvariable=self.settings_var, bg="#FFFFFF", fg="#A9AEB6", font=("Segoe UI", 9), wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 0))

        trend = self._card(right); trend.grid(row=0, column=0, sticky="nsew")
        tk.Label(trend, text=tr(self.config.language, "trend_30_days"), bg="#FFFFFF", fg="#17181C", font=("Segoe UI Semibold", 13)).pack(anchor=tk.W)
        tk.Label(trend, text=tr(self.config.language, "recent_days_desc"), bg="#FFFFFF", fg="#8A9099", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(4, 4))
        tk.Label(trend, textvariable=self.trend_meta_var, bg="#FFFFFF", fg="#4F87FF", font=("Segoe UI Semibold", 9)).pack(anchor=tk.W, pady=(0, 10))
        self.trend_canvas = tk.Canvas(trend, bg="#FFFFFF", highlightthickness=0, height=320); self.trend_canvas.pack(fill=tk.BOTH, expand=True); self.trend_canvas.bind("<Configure>", lambda _e: self._draw_trend_chart())

        history = self._card(right); history.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        htop = tk.Frame(history, bg="#FFFFFF"); htop.pack(fill=tk.X)
        htitle = tk.Frame(htop, bg="#FFFFFF"); htitle.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(htitle, text=tr(self.config.language, "history"), bg="#FFFFFF", fg="#17181C", font=("Segoe UI Semibold", 13)).pack(anchor=tk.W)
        tk.Label(htitle, text=tr(self.config.language, "full_history_desc"), bg="#FFFFFF", fg="#8A9099", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(4, 0))
        self._button(htop, tr(self.config.language, "open_history"), self.open_history_dialog, False).pack(side=tk.RIGHT)
        rows = tk.Frame(history, bg="#FFFFFF"); rows.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        for _ in range(8):
            row = tk.Frame(rows, bg="#FFFFFF"); row.pack(fill=tk.X, pady=5)
            left_var, right_var = tk.StringVar(value="-"), tk.StringVar(value="0")
            self.history_vars.append((left_var, right_var))
            tk.Label(row, textvariable=left_var, bg="#FFFFFF", fg="#5E6470", font=("Segoe UI", 10)).pack(side=tk.LEFT)
            tk.Label(row, textvariable=right_var, bg="#FFFFFF", fg="#17181C", font=("Segoe UI Semibold", 10)).pack(side=tk.RIGHT)
        tk.Label(history, textvariable=self.history_footer_var, bg="#FFFFFF", fg="#A9AEB6", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(10, 0))

    def open_settings_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(tr(self.config.language, "settings_title"))
        dialog.geometry("500x540")
        dialog.minsize(500, 540)
        dialog.resizable(False, False)
        dialog.configure(bg="#F4F4F6")
        dialog.transient(self.root)
        dialog.grab_set()
        shell = tk.Frame(dialog, bg="#F4F4F6", padx=18, pady=18)
        shell.pack(fill=tk.BOTH, expand=True)
        card = self._card(shell)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text=tr(self.config.language, "settings_title"), bg="#FFFFFF", fg="#17181C", font=("Segoe UI Semibold", 16)).pack(anchor=tk.W)
        tk.Label(card, text=tr(self.config.language, "settings_desc"), bg="#FFFFFF", fg="#8A9099", font=("Segoe UI", 9), wraplength=400, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 18))
        count_space, count_enter = tk.BooleanVar(value=self.config.count_space), tk.BooleanVar(value=self.config.count_enter)
        backspace_decrements, start_hidden = tk.BooleanVar(value=self.config.backspace_decrements), tk.BooleanVar(value=self.config.start_hidden_to_tray)
        language_mode = tk.StringVar(value=self.config.language)
        box = self._subcard(card); box.pack(fill=tk.X)
        for text, var in [(tr(self.config.language, "count_space"), count_space), (tr(self.config.language, "count_enter"), count_enter), (tr(self.config.language, "backspace_subtracts"), backspace_decrements), (tr(self.config.language, "start_hidden"), start_hidden)]:
            tk.Checkbutton(box, text=text, variable=var, bg="#F7F7F8", activebackground="#F7F7F8", font=("Segoe UI", 10), anchor="w", padx=2, pady=6, relief=tk.FLAT).pack(fill=tk.X)
        tk.Label(card, text=tr(self.config.language, "language_mode"), bg="#FFFFFF", fg="#17181C", font=("Segoe UI Semibold", 10)).pack(anchor=tk.W, pady=(16, 8))
        lang = self._subcard(card); lang.pack(fill=tk.X)
        tk.Radiobutton(lang, text=tr(self.config.language, "lang_zh"), value="zh", variable=language_mode, bg="#F7F7F8", activebackground="#F7F7F8", font=("Segoe UI", 10)).pack(anchor=tk.W)
        tk.Radiobutton(lang, text=tr(self.config.language, "lang_en"), value="en", variable=language_mode, bg="#F7F7F8", activebackground="#F7F7F8", font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(8, 0))
        tk.Frame(card, bg="#FFFFFF").pack(fill=tk.BOTH, expand=True, pady=(0, 12))

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

        footer = tk.Frame(shell, bg="#F4F4F6")
        footer.pack(fill=tk.X, pady=(14, 0))
        self._button(footer, tr(self.config.language, "save"), save_settings, True).pack(side=tk.RIGHT)

    def open_history_dialog(self) -> None:
        if self._history_dialog and self._history_dialog.winfo_exists():
            self._history_dialog.deiconify(); self._history_dialog.lift(); self._refresh_history_dialog(); return
        dialog = tk.Toplevel(self.root); dialog.title(tr(self.config.language, "full_history")); dialog.geometry("860x640"); dialog.minsize(820, 600); dialog.configure(bg="#F4F4F6"); dialog.transient(self.root); self._history_dialog = dialog
        shell = tk.Frame(dialog, bg="#F4F4F6", padx=18, pady=18); shell.pack(fill=tk.BOTH, expand=True)
        card = self._card(shell); card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text=tr(self.config.language, "full_history"), bg="#FFFFFF", fg="#17181C", font=("Segoe UI Semibold", 16)).pack(anchor=tk.W)
        tk.Label(card, text=tr(self.config.language, "full_history_desc"), bg="#FFFFFF", fg="#8A9099", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(6, 14))
        wrap = tk.Frame(card, bg="#FFFFFF"); wrap.pack(fill=tk.BOTH, expand=True)
        cols = ("date", "count", "typed", "pasted", "backspace", "accuracy", "peak_wpm")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", style="TypeRecord.Treeview")
        for col, label in [("date", "history_columns_date"), ("count", "history_columns_count"), ("typed", "history_columns_typed"), ("pasted", "history_columns_pasted"), ("backspace", "history_columns_backspace"), ("accuracy", "history_columns_accuracy"), ("peak_wpm", "history_columns_peak_wpm")]:
            tree.heading(col, text=tr(self.config.language, label))
        tree.column("date", width=150, anchor=tk.W)
        for col in ("count", "typed", "pasted", "backspace", "accuracy", "peak_wpm"): tree.column(col, width=92, anchor=tk.E)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview); tree.configure(yscrollcommand=sb.set); tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._history_tree = tree; dialog.protocol("WM_DELETE_WINDOW", self._close_history_dialog); self._refresh_history_dialog()

    def open_hourly_dialog(self) -> None:
        if self._hourly_dialog and self._hourly_dialog.winfo_exists():
            self._hourly_dialog.deiconify(); self._hourly_dialog.lift(); self._refresh_hourly_dialog(); return
        dialog = tk.Toplevel(self.root); dialog.title(tr(self.config.language, "hourly_today")); dialog.geometry("900x660"); dialog.minsize(860, 620); dialog.configure(bg="#F4F4F6"); dialog.transient(self.root); self._hourly_dialog = dialog
        shell = tk.Frame(dialog, bg="#F4F4F6", padx=18, pady=18); shell.pack(fill=tk.BOTH, expand=True)
        card = self._card(shell); card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text=tr(self.config.language, "hourly_today"), bg="#FFFFFF", fg="#17181C", font=("Segoe UI Semibold", 16)).pack(anchor=tk.W)
        tk.Label(card, text=tr(self.config.language, "hourly_today_desc"), bg="#FFFFFF", fg="#8A9099", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(6, 12))
        row = tk.Frame(card, bg="#FFFFFF"); row.pack(fill=tk.X, pady=(0, 12))
        tk.Label(row, text=tr(self.config.language, "hourly_date"), bg="#FFFFFF", fg="#5E6470", font=("Segoe UI Semibold", 9)).pack(side=tk.LEFT)
        self._hourly_date_var = tk.StringVar(value=self._today_date_str())
        self._hourly_date_selector = ttk.Combobox(row, textvariable=self._hourly_date_var, state="readonly", width=16, values=self._available_history_dates(), style="TypeRecord.TCombobox")
        self._hourly_date_selector.pack(side=tk.LEFT, padx=(10, 0)); self._hourly_date_selector.bind("<<ComboboxSelected>>", lambda _e: self._refresh_hourly_dialog())
        self._hourly_peak_var = tk.StringVar(value=""); tk.Label(card, textvariable=self._hourly_peak_var, bg="#FFFFFF", fg="#397BFF", font=("Segoe UI Semibold", 10)).pack(anchor=tk.W, pady=(0, 12))
        graph = self._subcard(card); graph.pack(fill=tk.X); self._hourly_canvas = tk.Canvas(graph, bg="#F7F7F8", highlightthickness=0, height=250); self._hourly_canvas.pack(fill=tk.BOTH, expand=True); self._hourly_canvas.bind("<Configure>", lambda _e: self._draw_hourly_chart())
        wrap = tk.Frame(card, bg="#FFFFFF"); wrap.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        tree = ttk.Treeview(wrap, columns=("hour", "typed", "pasted", "total"), show="headings", style="TypeRecord.Treeview")
        for col, label in [("hour", "hourly_table_hour"), ("typed", "hourly_table_typed"), ("pasted", "hourly_table_pasted"), ("total", "hourly_table_total")]:
            tree.heading(col, text=tr(self.config.language, label))
        tree.column("hour", width=120, anchor=tk.W)
        for col in ("typed", "pasted", "total"): tree.column(col, width=120, anchor=tk.E)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview); tree.configure(yscrollcommand=sb.set); tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._hourly_tree = tree; dialog.protocol("WM_DELETE_WINDOW", self._close_hourly_dialog); self._refresh_hourly_dialog()

    def _refresh_history_dialog(self) -> None:
        if self._history_tree is None: return
        self._history_tree.delete(*self._history_tree.get_children())
        for item in self.store.get_full_history():
            self._history_tree.insert("", tk.END, values=(item["date"], item["count"], item["typed"], item["pasted"], item["backspace"], f"{item['accuracy'] * 100:.1f}%", f"{item['peak_wpm']:.1f}"))

    def _refresh_hourly_dialog(self) -> None:
        if self._hourly_tree is None: return
        dates = self._available_history_dates(); selected = self._selected_hourly_date()
        if self._hourly_date_selector is not None: self._hourly_date_selector["values"] = dates
        if selected not in dates:
            selected = dates[0]
            if self._hourly_date_var is not None: self._hourly_date_var.set(selected)
        data = self.store.get_hourly_distribution(selected)
        self._hourly_tree.delete(*self._hourly_tree.get_children())
        for item in data: self._hourly_tree.insert("", tk.END, values=(f"{item['hour']}:00", item["typed"], item["pasted"], item["total"]))
        if self._hourly_peak_var is not None:
            peak = max(data, key=lambda item: item["total"], default=None)
            self._hourly_peak_var.set(f"{tr(self.config.language, 'hourly_peak')}: {selected}  {peak['hour']}:00  {peak['total']}" if peak and peak["total"] > 0 else tr(self.config.language, "hourly_empty"))
        self._draw_hourly_chart()

    def _schedule_refresh(self) -> None:
        summary, live = self.store.get_summary(), self.counter.get_live_stats()
        recent = self.store.get_recent_history(limit=8); self._latest_trend_history = self.store.get_trend_history(days=30)
        self.count_var.set(str(summary["today_count"])); self.detail_var.set(tr(self.config.language, "today_detail", count=summary["today_count"]))
        delta = live["session_delta"]; prefix = "+" if delta >= 0 else ""
        if live["session_duration_seconds"] > 0 or delta != 0: self.session_var.set(tr(self.config.language, "session_current" if live["session_is_active"] else "session_last", value=f"{prefix}{delta}"))
        else: self.session_var.set(tr(self.config.language, "session_none"))
        self.session_length_var.set(self._format_duration(live["session_duration_seconds"])); self.session_typed_var.set(str(live["session_positive_count"])); self.session_pasted_var.set(str(live["session_pasted_count"]))
        self.session_accuracy_var.set(f"{live['session_accuracy'] * 100:.1f}%"); self.typed_today_var.set(str(summary["typed_today"])); self.pasted_today_var.set(str(summary["pasted_today"]))
        self.backspace_var.set(str(summary["backspace_today"])); self.accuracy_var.set(f"{summary['accuracy'] * 100:.1f}%"); self.cpm_var.set(tr(self.config.language, "cpm", count=live["recent_cpm"]))
        self.peak_wpm_var.set(f"{summary['peak_wpm_today']:.1f}"); self.yesterday_var.set(str(summary["yesterday_count"])); self.week_var.set(str(summary["last_7_days_total"]))
        self.last_input_var.set(self._format_last_input(summary["last_input_at"] or live["last_input_at"]))
        self.count_mode_var.set(tr(self.config.language, "count_mode_subtracts" if self.config.backspace_decrements else "count_mode_ignored"))
        self.accuracy_hint_var.set(tr(self.config.language, "accuracy_hint", kept=summary["kept_today"], typed=summary["typed_today"]))
        self.settings_var.set(tr(self.config.language, "stored_settings", space=tr(self.config.language, "on") if self.config.count_space else tr(self.config.language, "off"), enter=tr(self.config.language, "on") if self.config.count_enter else tr(self.config.language, "off"), backspace=tr(self.config.language, "subtracts") if self.config.backspace_decrements else tr(self.config.language, "ignored"), hidden=tr(self.config.language, "on") if self.config.start_hidden_to_tray else tr(self.config.language, "off"), lang_name=tr(self.config.language, "language_name")))
        self.history_footer_var.set(tr(self.config.language, "days_recorded", count=len(self.store.get_full_history())))
        self._update_trend_meta()
        for i, pair in enumerate(self.history_vars):
            if i < len(recent):
                day = recent[i]; pair[0].set(day["date"]); pair[1].set(tr(self.config.language, "history_preview", count=day["count"], typed=day["typed"], pasted=day["pasted"]))
            else: pair[0].set("-"); pair[1].set("0")
        self._draw_trend_chart(); self._refresh_history_dialog(); self._refresh_hourly_dialog()
        self._refresh_after_id = self.root.after(self.config.refresh_interval_ms, self._schedule_refresh)

    def _update_trend_meta(self) -> None:
        non_zero = [item for item in self._latest_trend_history if item["count"] > 0]
        if not non_zero: self.trend_meta_var.set(tr(self.config.language, "trend_empty")); return
        peak, latest = max(non_zero, key=lambda item: item["count"]), non_zero[-1]
        self.trend_meta_var.set(f"Peak {peak['count']}  {peak['date']}   Latest {latest['count']}")

    def _draw_trend_chart(self) -> None:
        canvas = self.trend_canvas; canvas.delete("all"); data = self._latest_trend_history
        if not data: return
        width, height = max(canvas.winfo_width(), 480), max(canvas.winfo_height(), 260)
        ml, mr, mt, mb = 38, 18, 20, 34
        cw, ch = width - ml - mr, height - mt - mb
        max_count = max((item["count"] for item in data), default=0)
        if max_count <= 0:
            canvas.create_text(width / 2, height / 2, text=tr(self.config.language, "trend_empty"), fill="#9BA1AA", font=("Segoe UI", 10)); return
        plot_max = max_count * 1.12
        for step in range(4): canvas.create_line(ml, mt + ch * step / 3, width - mr, mt + ch * step / 3, fill="#EEEFF1", width=1)
        pts, coords = [], []
        for i, item in enumerate(data):
            x = ml if len(data) == 1 else ml + cw * i / (len(data) - 1)
            y = mt + ch * (1 - item["count"] / plot_max)
            coords.append((x, y, item)); pts.extend([x, y])
        canvas.create_polygon(ml, mt + ch, *pts, width - mr, mt + ch, fill="#E8F0FF", outline="")
        canvas.create_line(*pts, fill="#2E6AF4", width=3, smooth=True)
        peak, latest = max(coords, key=lambda item: item[2]["count"]), coords[-1]
        for x, y, item in coords:
            if item["count"] <= 0: continue
            r, fill = (5, "#111827") if (x, y, item) == peak else ((5, "#2E6AF4") if (x, y, item) == latest else (3, "#2E6AF4"))
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="")
        canvas.create_text(peak[0], max(mt, peak[1] - 16), text=str(peak[2]["count"]), fill="#111827", font=("Segoe UI Semibold", 9))
        canvas.create_text(ml, height - 12, text=data[0]["date"][5:], fill="#A1A7B0", font=("Segoe UI", 8), anchor="w")
        canvas.create_text(width - mr, height - 12, text=data[-1]["date"][5:], fill="#A1A7B0", font=("Segoe UI", 8), anchor="e")

    def _draw_hourly_chart(self) -> None:
        if self._hourly_canvas is None: return
        canvas = self._hourly_canvas; canvas.delete("all"); data = self.store.get_hourly_distribution(self._selected_hourly_date())
        width, height = max(canvas.winfo_width(), 620), max(canvas.winfo_height(), 220)
        ml, mr, mt, mb = 28, 12, 18, 26
        cw, ch = width - ml - mr, height - mt - mb
        max_total = max((item["total"] for item in data), default=0)
        if max_total <= 0:
            canvas.create_text(width / 2, height / 2, text=tr(self.config.language, "hourly_empty"), fill="#9BA1AA", font=("Segoe UI", 10)); return
        bar = max(8, int(cw / 24) - 4)
        for i, item in enumerate(data):
            x, bottom = ml + i * (cw / 24) + 2, mt + ch
            th, ph = ch * item["typed"] / max_total, ch * item["pasted"] / max_total
            if item["typed"] > 0: canvas.create_rectangle(x, bottom - th, x + bar, bottom, fill="#2E6AF4", outline="")
            if item["pasted"] > 0: canvas.create_rectangle(x, bottom - th - ph, x + bar, bottom - th, fill="#A7C8FF", outline="")
            if i % 3 == 0: canvas.create_text(x + bar / 2, height - 10, text=item["hour"], fill="#A1A7B0", font=("Segoe UI", 8))

    def _close_history_dialog(self) -> None:
        if self._history_dialog and self._history_dialog.winfo_exists(): self._history_dialog.destroy()
        self._history_dialog = None; self._history_tree = None

    def _close_hourly_dialog(self) -> None:
        if self._hourly_dialog and self._hourly_dialog.winfo_exists(): self._hourly_dialog.destroy()
        self._hourly_dialog = None; self._hourly_tree = None; self._hourly_canvas = None; self._hourly_peak_var = None; self._hourly_date_var = None; self._hourly_date_selector = None

    def _button(self, parent: tk.Widget, text: str, command, primary: bool) -> tk.Button:
        bg, fg, abg = ("#17181C", "#FFFFFF", "#111216") if primary else ("#FFFFFF", "#4F5560", "#F0F1F3")
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=abg, activeforeground=fg, relief=tk.FLAT, padx=14, pady=8, font=("Segoe UI Semibold", 9), highlightthickness=1, highlightbackground="#E5E7EB" if not primary else "#17181C")

    def _card(self, parent: tk.Widget) -> tk.Frame: return tk.Frame(parent, bg="#FFFFFF", highlightthickness=1, highlightbackground="#ECECEE", padx=18, pady=18)
    def _subcard(self, parent: tk.Widget) -> tk.Frame: return tk.Frame(parent, bg="#F7F7F8", highlightthickness=1, highlightbackground="#ECECEE", padx=14, pady=14)

    def _tile(self, parent: tk.Frame, title: str, var: tk.StringVar, row: int, col: int) -> None:
        tile = tk.Frame(parent, bg="#F7F7F8", highlightthickness=1, highlightbackground="#ECECEE", padx=14, pady=12)
        tile.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        tk.Label(tile, text=title, bg="#F7F7F8", fg="#8A9099", font=("Segoe UI", 9)).pack(anchor=tk.W)
        tk.Label(tile, textvariable=var, bg="#F7F7F8", fg="#17181C", font=("Segoe UI Semibold", 11), wraplength=210, justify=tk.LEFT).pack(anchor=tk.W, pady=(7, 0))

    def _configure_ttk(self) -> None:
        style = ttk.Style(self.root); style.theme_use("clam")
        style.configure("TypeRecord.Treeview", background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#17181C", rowheight=30, borderwidth=0, relief="flat")
        style.configure("TypeRecord.Treeview.Heading", background="#F7F7F8", foreground="#6B7280", relief="flat", font=("Segoe UI Semibold", 9))
        style.map("TypeRecord.Treeview", background=[("selected", "#E8F0FF")], foreground=[("selected", "#17181C")])
        style.configure("TypeRecord.TCombobox", fieldbackground="#FFFFFF", background="#FFFFFF", foreground="#17181C", arrowcolor="#5E6470", bordercolor="#E5E7EB", lightcolor="#E5E7EB", darkcolor="#E5E7EB")

    def _cancel_refresh(self) -> None:
        if self._refresh_after_id is not None:
            try: self.root.after_cancel(self._refresh_after_id)
            except tk.TclError: pass
            self._refresh_after_id = None

    def _available_history_dates(self) -> list[str]:
        dates = [item["date"] for item in self.store.get_full_history()]
        return dates or [self._today_date_str()]

    def _selected_hourly_date(self) -> str:
        return self._hourly_date_var.get().strip() if self._hourly_date_var and self._hourly_date_var.get().strip() else self._today_date_str()

    def _today_date_str(self) -> str: return datetime.now().date().isoformat()

    def _format_last_input(self, last_input_at: str | None) -> str:
        if not last_input_at: return tr(self.config.language, "no_input")
        try: return datetime.fromisoformat(last_input_at).strftime("%H:%M:%S")
        except ValueError: return tr(self.config.language, "unknown")

    def _format_duration(self, seconds: int) -> str:
        seconds = max(0, seconds); hours, rem = divmod(seconds, 3600); minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours > 0 else f"{minutes:02d}:{secs:02d}"
