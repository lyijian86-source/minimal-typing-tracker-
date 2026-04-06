from __future__ import annotations

from pathlib import Path
from threading import Thread
from typing import Callable

import pystray
from PIL import Image


class TrayController:
    def __init__(
        self,
        tooltip: str,
        on_show: Callable[[], None],
        on_reset_today: Callable[[], None],
        on_open_data_folder: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.tooltip = tooltip
        self.on_show = on_show
        self.on_reset_today = on_reset_today
        self.on_open_data_folder = on_open_data_folder
        self.on_exit = on_exit
        self._icon: pystray.Icon | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return

        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self._handle_show, default=True),
            pystray.MenuItem("Reset Today", self._handle_reset_today),
            pystray.MenuItem("Open Data Folder", self._handle_open_data_folder),
            pystray.MenuItem("Exit", self._handle_exit),
        )
        self._icon = pystray.Icon(
            "type_record",
            self._build_icon_image(),
            self.tooltip,
            menu,
        )
        self._thread = Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
        self._icon = None
        self._thread = None

    def _handle_show(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = (icon, item)
        self.on_show()

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
