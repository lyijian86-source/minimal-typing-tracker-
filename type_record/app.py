from __future__ import annotations

import os
import sys
import tkinter.messagebox as messagebox

from type_record.config import AppConfig
from type_record.counter import KeyboardCounter
from type_record.i18n import tr
from type_record.storage import DailyCountStore
from type_record.tray import TrayController
from type_record.ui import CounterWindow


def main() -> None:
    config = AppConfig.load()
    store = DailyCountStore(config.data_file)
    counter = KeyboardCounter(config=config, store=store)
    tray: TrayController | None = None

    def export_csv() -> None:
        export_path = store.export_history_csv()
        window.call_in_main_thread(lambda: window.show_export_message(tr(config.language, "exported", name=export_path.name)))
        os.startfile(str(export_path.parent))

    try:
        counter.start()
    except Exception as exc:
        message = tr(config.language, "error_start_listener", error=exc)
        try:
            messagebox.showerror(config.app_name, message)
        finally:
            raise SystemExit(1) from exc

    def handle_language_changed(language: str) -> None:
        if tray is not None:
            tray.refresh_language(language)

    window = CounterWindow(
        config=config,
        store=store,
        counter=counter,
        on_export_csv=export_csv,
        on_language_changed=handle_language_changed,
    )
    is_exiting = False

    def show_window() -> None:
        window.call_in_main_thread(window.show)

    def open_settings() -> None:
        window.call_in_main_thread(window.open_settings_dialog)

    def reset_today() -> None:
        def confirm_and_reset() -> None:
            should_reset = messagebox.askyesno(tr(config.language, "reset_title"), tr(config.language, "reset_confirm"))
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
        if tray is not None:
            tray.stop()
        window.call_in_main_thread(window.destroy)

    tray = TrayController(
        tooltip=config.tray_tooltip,
        language=config.language,
        on_show=show_window,
        on_open_settings=open_settings,
        on_export_csv=export_csv,
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
