from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppConfig:
    app_name: str = "Type Record"
    count_space: bool = True
    count_enter: bool = False
    backspace_decrements: bool = True
    refresh_interval_ms: int = 300
    session_timeout_seconds: int = 300
    tray_tooltip: str = "Type Record"
    start_hidden_to_tray: bool = True
    language: str = "en"

    @property
    def data_file(self) -> Path:
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else Path.cwd()
        return base_dir / "TypeRecord" / "data" / "daily_counts.json"

    @property
    def settings_file(self) -> Path:
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else Path.cwd()
        return base_dir / "TypeRecord" / "config" / "settings.json"

    @classmethod
    def load(cls) -> AppConfig:
        instance = cls()
        settings_path = instance._resolve_settings_path(instance.settings_file)

        if settings_path.exists():
            try:
                with settings_path.open("r", encoding="utf-8") as file:
                    data = json.load(file)
                if isinstance(data, dict):
                    for field_name in asdict(instance):
                        if field_name in data:
                            setattr(instance, field_name, data[field_name])
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass

        instance._settings_path = settings_path
        return instance

    def save(self) -> None:
        settings_path = self._resolve_settings_path(getattr(self, "_settings_path", self.settings_file))
        payload = asdict(self)
        with settings_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        self._settings_path = settings_path

    def _resolve_settings_path(self, preferred_path: Path) -> Path:
        try:
            preferred_path.parent.mkdir(parents=True, exist_ok=True)
            test_file = preferred_path.parent / '.write_test.tmp'
            test_file.write_text('ok', encoding='utf-8')
            test_file.unlink(missing_ok=True)
            return preferred_path
        except OSError:
            fallback_path = Path.cwd() / 'data' / 'settings.json'
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            return fallback_path
