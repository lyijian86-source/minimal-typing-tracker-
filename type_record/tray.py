from __future__ import annotations

from pathlib import Path
from threading import Thread
from typing import Callable

import pystray
from PIL import Image

from type_record.i18n import tr


class TrayController:
    def __init__(
        self,
        tooltip: str,
        language: str,
        on_show: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_export_csv: Callable[[], None],
        on_reset_today: Callable[[], None],
        on_open_data_folder: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.tooltip = tooltip
        self.language = language
        self.on_show = on_show
        self.on_open_settings = on_open_settings
        self.on_export_csv = on_export_csv
        self.on_reset_today = on_reset_today
        self.on_open_data_folder = on_open_data_folder
        self.on_exit = on_exit
        self._icon: pystray.Icon | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._build_and_run()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
        self._icon = None
        self._thread = None

    def refresh_language(self, language: str) -> None:
        self.language = language
        self.stop()
        self._build_and_run()

    def _build_and_run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem(tr(self.language, "show_window"), self._handle_show, default=True),
            pystray.MenuItem(tr(self.language, "settings"), self._handle_open_settings),
            pystray.MenuItem(tr(self.language, "export_csv"), self._handle_export_csv),
            pystray.MenuItem(tr(self.language, "reset_today"), self._handle_reset_today),
            pystray.MenuItem(tr(self.language, "open_data_folder"), self._handle_open_data_folder),
            pystray.MenuItem(tr(self.language, "exit"), self._handle_exit),
        )
        self._icon = pystray.Icon("type_record", self._build_icon_image(), self.tooltip, menu)
        self._thread = Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def _handle_show(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = (icon, item)
        self.on_show()

    def _handle_open_settings(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = (icon, item)
        self.on_open_settings()

    def _handle_export_csv(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = (icon, item)
        self.on_export_csv()

    def _handle_reset_today(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = (icon, item)
        self.on_reset_today()

    def _handle_open_data_folder(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = (icon, item)
        self.on_open_data_folder()

    def _handle_exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = (icon, item)
        self.on_exit()

    def _build_icon_image(self) -> Image.Image:
        asset_path = Path(__file__).resolve().parent.parent / "assets" / "tray_icon.png"
        with Image.open(asset_path) as image:
            return image.convert("RGBA").copy()
