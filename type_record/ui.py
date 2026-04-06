from __future__ import annotations

import tkinter as tk
from datetime import datetime
from typing import Callable

from type_record.config import AppConfig
from type_record.counter import KeyboardCounter
from type_record.i18n import tr
from type_record.storage import DailyCountStore


class CounterWindow:
    def __init__(
        self,
        config: AppConfig,
        store: DailyCountStore,
        counter: KeyboardCounter,
        on_export_csv: Callable[[], None],
        on_language_changed: Callable[[str], None],
    ) -> None:
        self.config = config
        self.store = store
        self.counter = counter
        self.on_export_csv = on_export_csv
        self.on_language_changed = on_language_changed
        self.root = tk.Tk()
        self.root.title(config.app_name)
        self.root.geometry("820x620")
        self.root.minsize(820, 620)
        self.root.configure(bg="#EDF1F5")

        self.count_var = tk.StringVar(value="0")
        self.detail_var = tk.StringVar(value="0 today")
        self.session_var = tk.StringVar(value="Session +0")
        self.cpm_var = tk.StringVar(value="0")
        self.last_input_var = tk.StringVar(value=tr(self.config.language, "no_input"))
        self.yesterday_var = tk.StringVar(value="0")
        self.week_var = tk.StringVar(value="0")
        self.backspace_var = tk.StringVar(value="0")
        self.accuracy_var = tk.StringVar(value="0%")
        self.settings_var = tk.StringVar(value="")
        self.export_var = tk.StringVar(value="")
        self.history_vars: list[tuple[tk.StringVar, tk.StringVar]] = []

        self._build_layout()
        self._schedule_refresh()

    def set_on_close(self, callback) -> None:
        self.root.protocol("WM_DELETE_WINDOW", callback)

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self) -> None:
        self.root.withdraw()

    def call_in_main_thread(self, callback) -> None:
        self.root.after(0, callback)

    def run(self) -> None:
        self.root.mainloop()

    def destroy(self) -> None:
        self.root.destroy()

    def refresh_language(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        self.history_vars.clear()
        self._build_layout()

    def show_export_message(self, text: str) -> None:
        self.export_var.set(text)
        self.root.after(5000, lambda: self.export_var.set(""))

    def open_settings_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(tr(self.config.language, "settings_title"))
        dialog.geometry("420x420")
        dialog.minsize(420, 420)
        dialog.resizable(False, False)
        dialog.configure(bg="#FFFFFF")
        dialog.transient(self.root)
        dialog.grab_set()

        wrapper = tk.Frame(dialog, bg="#FFFFFF", padx=20, pady=20)
        wrapper.pack(fill=tk.BOTH, expand=True)

        tk.Label(wrapper, text=tr(self.config.language, "counting_rules"), bg="#FFFFFF", fg="#15171B", font=("Segoe UI Semibold", 14)).pack(anchor=tk.W)
        tk.Label(wrapper, text=tr(self.config.language, "settings_desc"), bg="#FFFFFF", fg="#808791", font=("Segoe UI", 9), wraplength=340, justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 16))

        count_space = tk.BooleanVar(value=self.config.count_space)
        count_enter = tk.BooleanVar(value=self.config.count_enter)
        backspace_decrements = tk.BooleanVar(value=self.config.backspace_decrements)
        start_hidden = tk.BooleanVar(value=self.config.start_hidden_to_tray)
        language_mode = tk.StringVar(value=self.config.language)

        self._settings_check(wrapper, tr(self.config.language, "count_space"), count_space).pack(fill=tk.X, pady=2)
        self._settings_check(wrapper, tr(self.config.language, "count_enter"), count_enter).pack(fill=tk.X, pady=2)
        self._settings_check(wrapper, tr(self.config.language, "backspace_subtracts"), backspace_decrements).pack(fill=tk.X, pady=2)
        self._settings_check(wrapper, tr(self.config.language, "start_hidden"), start_hidden).pack(fill=tk.X, pady=2)

        tk.Label(wrapper, text=tr(self.config.language, "language_mode"), bg="#FFFFFF", fg="#1B1D22", font=("Segoe UI Semibold", 10)).pack(anchor=tk.W, pady=(16, 6))

        lang_row = tk.Frame(wrapper, bg="#FFFFFF")
        lang_row.pack(anchor=tk.W)
        tk.Radiobutton(lang_row, text=tr(self.config.language, "lang_zh"), value="zh", variable=language_mode, bg="#FFFFFF", activebackground="#FFFFFF", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.Radiobutton(lang_row, text=tr(self.config.language, "lang_en"), value="en", variable=language_mode, bg="#FFFFFF", activebackground="#FFFFFF", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(16, 0))

        spacer = tk.Frame(wrapper, bg="#FFFFFF")
        spacer.pack(fill=tk.BOTH, expand=True)

        def save_settings() -> None:
            self.config.count_space = bool(count_space.get())
            self.config.count_enter = bool(count_enter.get())
            self.config.backspace_decrements = bool(backspace_decrements.get())
            self.config.start_hidden_to_tray = bool(start_hidden.get())
            language_changed = self.config.language != language_mode.get()
            self.config.language = language_mode.get()
            self.config.save()
            dialog.destroy()
            if language_changed:
                self.on_language_changed(self.config.language)
                self.refresh_language()
            self.show()

        button_row = tk.Frame(wrapper, bg="#FFFFFF")
        button_row.pack(fill=tk.X, pady=(18, 0))
        tk.Button(button_row, text=tr(self.config.language, "save"), command=save_settings, bg="#397BFF", fg="#FFFFFF", activebackground="#2E67D8", activeforeground="#FFFFFF", relief=tk.FLAT, padx=18, pady=10, font=("Segoe UI Semibold", 10)).pack(side=tk.RIGHT)

    def _settings_check(self, parent: tk.Frame, text: str, variable: tk.BooleanVar) -> tk.Checkbutton:
        return tk.Checkbutton(parent, text=text, variable=variable, bg="#FFFFFF", fg="#1B1D22", activebackground="#FFFFFF", font=("Segoe UI", 10), anchor="w", padx=2, pady=6)

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg="#EDF1F5", padx=18, pady=18)
        shell.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(shell, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E7EBF0", padx=24, pady=22)
        card.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(card, bg="#FFFFFF")
        top.pack(fill=tk.X)

        title_wrap = tk.Frame(top, bg="#FFFFFF")
        title_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(title_wrap, text=tr(self.config.language, "today"), bg="#FFFFFF", fg="#969BA3", font=("Segoe UI Semibold", 10)).pack(anchor=tk.W)
        tk.Label(title_wrap, text=tr(self.config.language, "typing_count"), bg="#FFFFFF", fg="#14161A", font=("Segoe UI Semibold", 18)).pack(anchor=tk.W, pady=(6, 0))

        actions = tk.Frame(top, bg="#FFFFFF")
        actions.pack(side=tk.RIGHT)
        tk.Button(actions, text=tr(self.config.language, "export_csv"), command=self.on_export_csv, bg="#F7F8FA", fg="#5B6270", activebackground="#EEF1F5", activeforeground="#3D4350", relief=tk.FLAT, padx=12, pady=8, font=("Segoe UI Semibold", 9)).pack(side=tk.RIGHT, padx=(0, 8))
        tk.Button(actions, text=tr(self.config.language, "settings"), command=self.open_settings_dialog, bg="#F7F8FA", fg="#5B6270", activebackground="#EEF1F5", activeforeground="#3D4350", relief=tk.FLAT, padx=12, pady=8, font=("Segoe UI Semibold", 9)).pack(side=tk.RIGHT)

        content = tk.Frame(card, bg="#FFFFFF")
        content.pack(fill=tk.BOTH, expand=True, pady=(18, 10))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        left_col = tk.Frame(content, bg="#FFFFFF")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        tk.Label(left_col, textvariable=self.count_var, bg="#FFFFFF", fg="#111317", font=("Segoe UI", 52, "bold")).pack(anchor=tk.W, pady=(6, 0))
        tk.Label(left_col, textvariable=self.detail_var, bg="#FFFFFF", fg="#7D838C", font=("Segoe UI", 11)).pack(anchor=tk.W, pady=(4, 10))
        tk.Label(left_col, textvariable=self.session_var, bg="#FFFFFF", fg="#397BFF", font=("Segoe UI Semibold", 11)).pack(anchor=tk.W, pady=(0, 12))

        stats_grid = tk.Frame(left_col, bg="#FFFFFF")
        stats_grid.pack(fill=tk.X, pady=(0, 8))
        for column in range(2):
            stats_grid.grid_columnconfigure(column, weight=1)

        self._create_stat_box(stats_grid, tr(self.config.language, "last_minute"), self.cpm_var, 0, 0)
        self._create_stat_box(stats_grid, tr(self.config.language, "yesterday"), self.yesterday_var, 0, 1)
        self._create_stat_box(stats_grid, tr(self.config.language, "seven_day_total"), self.week_var, 1, 0)
        self._create_stat_box(stats_grid, tr(self.config.language, "backspace_today"), self.backspace_var, 1, 1)
        self._create_stat_box(stats_grid, tr(self.config.language, "accuracy"), self.accuracy_var, 2, 0)
        self._create_stat_box(stats_grid, tr(self.config.language, "last_input"), self.last_input_var, 2, 1)

        tk.Label(left_col, textvariable=self.export_var, bg="#FFFFFF", fg="#397BFF", font=("Segoe UI", 9), wraplength=380, justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 0))

        right_col = tk.Frame(content, bg="#F7F8FA", highlightthickness=1, highlightbackground="#ECEEF2", padx=14, pady=14)
        right_col.grid(row=0, column=1, sticky="nsew")

        tk.Label(right_col, text=tr(self.config.language, "recent_days"), bg="#F7F8FA", fg="#16181D", font=("Segoe UI Semibold", 12)).pack(anchor=tk.W)
        tk.Label(right_col, text=tr(self.config.language, "recent_days_desc"), bg="#F7F8FA", fg="#8E949C", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(4, 10))

        for _ in range(7):
            row = tk.Frame(right_col, bg="#F7F8FA")
            row.pack(fill=tk.X, pady=4)
            left_text = tk.StringVar(value="-")
            right_text = tk.StringVar(value="0")
            self.history_vars.append((left_text, right_text))
            tk.Label(row, textvariable=left_text, bg="#F7F8FA", fg="#4A4F59", font=("Segoe UI", 10)).pack(side=tk.LEFT)
            tk.Label(row, textvariable=right_text, bg="#F7F8FA", fg="#16181D", font=("Segoe UI Semibold", 10)).pack(side=tk.RIGHT)

        footer = tk.Frame(card, bg="#FFFFFF")
        footer.pack(fill=tk.X)
        tk.Label(footer, textvariable=self.settings_var, bg="#FFFFFF", fg="#9CA3AD", font=("Segoe UI", 9), justify=tk.LEFT, wraplength=740).pack(anchor=tk.W)

    def _create_stat_box(self, parent: tk.Frame, title: str, value_var: tk.StringVar, row: int, column: int) -> None:
        box = tk.Frame(parent, bg="#F7F8FA", padx=12, pady=10, highlightthickness=1, highlightbackground="#ECEEF2")
        box.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
        tk.Label(box, text=title, bg="#F7F8FA", fg="#8E949C", font=("Segoe UI", 9)).pack(anchor=tk.W)
        tk.Label(box, textvariable=value_var, bg="#F7F8FA", fg="#1B1D22", font=("Segoe UI Semibold", 11), wraplength=220, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))

    def _schedule_refresh(self) -> None:
        store_summary = self.store.get_summary()
        live_stats = self.counter.get_live_stats()
        recent_history = self.store.get_recent_history(limit=7)

        today_count = store_summary["today_count"]
        self.count_var.set(str(today_count))
        self.detail_var.set(tr(self.config.language, "today_detail", count=today_count))

        session_delta = live_stats["session_delta"]
        session_prefix = "+" if session_delta >= 0 else ""
        self.session_var.set(tr(self.config.language, "session", value=f"{session_prefix}{session_delta}"))
        self.cpm_var.set(tr(self.config.language, "cpm", count=live_stats["recent_cpm"]))
        self.yesterday_var.set(str(store_summary["yesterday_count"]))
        self.week_var.set(str(store_summary["last_7_days_total"]))
        self.backspace_var.set(str(store_summary["backspace_today"]))
        self.accuracy_var.set(f"{store_summary['accuracy'] * 100:.1f}%")
        self.last_input_var.set(self._format_last_input(store_summary["last_input_at"] or live_stats["last_input_at"]))
        self.settings_var.set(
            tr(
                self.config.language,
                "stored_settings",
                space=tr(self.config.language, "on") if self.config.count_space else tr(self.config.language, "off"),
                enter=tr(self.config.language, "on") if self.config.count_enter else tr(self.config.language, "off"),
                backspace=tr(self.config.language, "subtracts") if self.config.backspace_decrements else tr(self.config.language, "ignored"),
                hidden=tr(self.config.language, "on") if self.config.start_hidden_to_tray else tr(self.config.language, "off"),
                lang_name=tr(self.config.language, "language_name"),
            )
        )

        for index, pair in enumerate(self.history_vars):
            if index < len(recent_history):
                day = recent_history[index]
                pair[0].set(day["date"])
                pair[1].set(f"{day['count']} | {day['accuracy'] * 100:.0f}%")
            else:
                pair[0].set("-")
                pair[1].set("0")

        self.root.after(self.config.refresh_interval_ms, self._schedule_refresh)

    def _format_last_input(self, last_input_at: str | None) -> str:
        if not last_input_at:
            return tr(self.config.language, "no_input")
        try:
            last_time = datetime.fromisoformat(last_input_at)
        except ValueError:
            return tr(self.config.language, "unknown")
        return last_time.strftime("%H:%M:%S")
