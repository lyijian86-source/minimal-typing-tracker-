from __future__ import annotations

import os
import sys
import tkinter.messagebox as messagebox

from type_record.config import AppConfig
from type_record.counter import KeyboardCounter
from type_record.storage import DailyCountStore
from type_record.tray import TrayController
from type_record.ui import CounterWindow


def main() -> None:
    config = AppConfig()
    store = DailyCountStore(config.data_file)
    counter = KeyboardCounter(config=config, store=store)

    try:
        counter.start()
    except Exception as exc:
        message = (
            "Failed to start keyboard listener.\n\n"
            "Common causes:\n"
            "1. The keyboard package is not installed\n"
            "2. Security software blocked the global keyboard hook\n"
            "3. Input in elevated apps may not be visible to a normal process\n\n"
            f"Error: {exc}"
        )
        try:
            messagebox.showerror("Type Record", message)
        finally:
            raise SystemExit(1) from exc

    window = CounterWindow(config=config, store=store, counter=counter)
    is_exiting = False

    def show_window() -> None:
        window.call_in_main_thread(window.show)

    def reset_today() -> None:
        def confirm_and_reset() -> None:
            should_reset = messagebox.askyesno(
                "Reset Today",
                "Reset today's count to 0?",
            )
            if not should_reset:
                return
            store.reset_today()
            counter.reset_session_stats()
            window.show()

        window.call_in_main_thread(confirm_and_reset)

    def open_data_folder() -> None:
        os.startfile(str(store.data_dir))

    def exit_app() -> None:
        nonlocal is_exiting
        if is_exiting:
            return
        is_exiting = True
        counter.stop()
        tray.stop()
        window.call_in_main_thread(window.destroy)

    tray = TrayController(
        tooltip=config.tray_tooltip,
        on_show=show_window,
        on_reset_today=reset_today,
        on_open_data_folder=open_data_folder,
        on_exit=exit_app,
    )
    tray.start()

    if config.start_hidden_to_tray:
        window.hide()

    def close_to_tray() -> None:
        window.hide()

    window.set_on_close(close_to_tray)

    try:
        window.run()
    except KeyboardInterrupt:
        exit_app()
        sys.exit(0)
