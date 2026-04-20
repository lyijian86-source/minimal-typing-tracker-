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

    @property
    def settings_backup_file(self) -> Path:
        return self.settings_file.with_suffix(f"{self.settings_file.suffix}.bak")

    @classmethod
    def load(cls) -> AppConfig:
        instance = cls()
        settings_path = instance._resolve_settings_path(instance.settings_file)
        backup_path = settings_path.with_suffix(f"{settings_path.suffix}.bak")
        data = instance._load_settings_json(settings_path)
        if data is None:
            data = instance._load_settings_json(backup_path)

        if isinstance(data, dict):
            for field_name in asdict(instance):
                if field_name in data:
                    setattr(instance, field_name, data[field_name])

        instance._settings_path = settings_path
        instance._settings_backup_path = backup_path
        return instance

    def save(self) -> None:
        settings_path = self._resolve_settings_path(getattr(self, "_settings_path", self.settings_file))
        backup_path = getattr(self, "_settings_backup_path", settings_path.with_suffix(f"{settings_path.suffix}.bak"))
        payload = asdict(self)
        self._write_json_atomic(settings_path, payload)
        self._write_json_atomic(backup_path, payload)
        self._settings_path = settings_path
        self._settings_backup_path = backup_path

    def _resolve_settings_path(self, preferred_path: Path) -> Path:
        try:
            preferred_path.parent.mkdir(parents=True, exist_ok=True)
            test_file = preferred_path.parent / ".write_test.tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return preferred_path
        except OSError:
            fallback_path = Path.cwd() / "data" / "settings.json"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            return fallback_path

    def _load_settings_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _write_json_atomic(self, target: Path, payload: dict) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_suffix(f"{target.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, target)
