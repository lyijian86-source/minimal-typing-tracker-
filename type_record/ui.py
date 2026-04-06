from __future__ import annotations

import tkinter as tk
from datetime import datetime

from type_record.config import AppConfig
from type_record.counter import KeyboardCounter
from type_record.storage import DailyCountStore


class CounterWindow:
    def __init__(self, config: AppConfig, store: DailyCountStore, counter: KeyboardCounter) -> None:
        self.config = config
        self.store = store
        self.counter = counter
        self.root = tk.Tk()
        self.root.title(config.app_name)
        self.root.geometry("470x360")
        self.root.minsize(470, 360)
        self.root.configure(bg="#EDF1F5")

        self.count_var = tk.StringVar(value="0")
        self.detail_var = tk.StringVar(value="0 today")
        self.session_var = tk.StringVar(value="Session +0")
        self.cpm_var = tk.StringVar(value="0")
        self.last_input_var = tk.StringVar(value="No input yet")
        self.yesterday_var = tk.StringVar(value="0")
        self.week_var = tk.StringVar(value="0")
        self.settings_var = tk.StringVar(value="")

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

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg="#EDF1F5", padx=22, pady=22)
        shell.pack(fill=tk.BOTH, expand=True)

        shadow = tk.Frame(shell, bg="#E3E8EE", bd=0)
        shadow.pack(fill=tk.BOTH, expand=True, padx=(4, 0), pady=(4, 0))

        card = tk.Frame(shadow, bg="#FFFFFF", bd=0)
        card.place(x=-4, y=-4, relwidth=1.0, relheight=1.0)

        top = tk.Frame(card, bg="#FFFFFF", padx=28, pady=24)
        top.pack(fill=tk.X)

        left = tk.Frame(top, bg="#FFFFFF")
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            left,
            text="TODAY",
            bg="#FFFFFF",
            fg="#969BA3",
            font=("Segoe UI Semibold", 10),
        ).pack(anchor=tk.W)

        tk.Label(
            left,
            text="Typing Count",
            bg="#FFFFFF",
            fg="#14161A",
            font=("Segoe UI Semibold", 18),
        ).pack(anchor=tk.W, pady=(6, 0))

        token = tk.Frame(top, bg="#F7F8FA", padx=16, pady=10)
        token.pack(side=tk.RIGHT)

        tk.Label(
            token,
            text="W",
            bg="#F7F8FA",
            fg="#397BFF",
            font=("Segoe UI Semibold", 18),
        ).pack()

        body = tk.Frame(card, bg="#FFFFFF", padx=28)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            body,
            textvariable=self.count_var,
            bg="#FFFFFF",
            fg="#111317",
            font=("Segoe UI", 52, "bold"),
        ).pack(anchor=tk.W, pady=(8, 0))

        tk.Label(
            body,
            textvariable=self.detail_var,
            bg="#FFFFFF",
            fg="#7D838C",
            font=("Segoe UI", 11),
        ).pack(anchor=tk.W, pady=(4, 12))

        tk.Label(
            body,
            textvariable=self.session_var,
            bg="#FFFFFF",
            fg="#397BFF",
            font=("Segoe UI Semibold", 11),
        ).pack(anchor=tk.W, pady=(0, 10))

        stats_grid = tk.Frame(body, bg="#FFFFFF")
        stats_grid.pack(fill=tk.X, pady=(0, 8))
        for column in range(2):
            stats_grid.columnconfigure(column, weight=1)

        self._create_stat_box(stats_grid, "Last minute", self.cpm_var, 0, 0)
        self._create_stat_box(stats_grid, "Yesterday", self.yesterday_var, 0, 1)
        self._create_stat_box(stats_grid, "7-day total", self.week_var, 1, 0)
        self._create_stat_box(stats_grid, "Last input", self.last_input_var, 1, 1)

        footer = tk.Frame(card, bg="#FFFFFF", padx=28, pady=18)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(
            footer,
            textvariable=self.settings_var,
            bg="#FFFFFF",
            fg="#9CA3AD",
            font=("Segoe UI", 9),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _create_stat_box(
        self,
        parent: tk.Frame,
        title: str,
        value_var: tk.StringVar,
        row: int,
        column: int,
    ) -> None:
        box = tk.Frame(
            parent,
            bg="#F7F8FA",
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground="#ECEEF2",
        )
        box.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)

        tk.Label(
            box,
            text=title,
            bg="#F7F8FA",
            fg="#8E949C",
            font=("Segoe UI", 9),
        ).pack(anchor=tk.W)

        tk.Label(
            box,
            textvariable=value_var,
            bg="#F7F8FA",
            fg="#1B1D22",
            font=("Segoe UI Semibold", 11),
            wraplength=155,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 0))

    def _schedule_refresh(self) -> None:
        store_summary = self.store.get_summary()
        live_stats = self.counter.get_live_stats()

        today_count = store_summary["today_count"]
        self.count_var.set(str(today_count))
        self.detail_var.set(f"{today_count} characters today")

        session_delta = live_stats["session_delta"]
        session_prefix = "+" if session_delta >= 0 else ""
        self.session_var.set(f"Session {session_prefix}{session_delta}")
        self.cpm_var.set(f"{live_stats['recent_cpm']} cpm")
        self.yesterday_var.set(str(store_summary["yesterday_count"]))
        self.week_var.set(str(store_summary["last_7_days_total"]))
        self.last_input_var.set(self._format_last_input(store_summary["last_input_at"] or live_stats["last_input_at"]))
        self.settings_var.set(
            "Space on | Enter "
            + ("on" if self.config.count_enter else "off")
            + " | Backspace "
            + ("subtracts" if self.config.backspace_decrements else "ignored")
        )

        self.root.after(self.config.refresh_interval_ms, self._schedule_refresh)

    def _format_last_input(self, last_input_at: str | None) -> str:
        if not last_input_at:
            return "No input yet"

        try:
            last_time = datetime.fromisoformat(last_input_at)
        except ValueError:
            return "Unknown"

        return last_time.strftime("%H:%M:%S")
