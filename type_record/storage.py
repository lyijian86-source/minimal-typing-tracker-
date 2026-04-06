from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock


@dataclass
class DailyCountStore:
    file_path: Path

    def __post_init__(self) -> None:
        self._lock = Lock()
        self.file_path = self._resolve_writable_path(self.file_path)
        self._state = self._load()
        self._ensure_today_record()

    @property
    def data_dir(self) -> Path:
        return self.file_path.parent

    def get_today_count(self) -> int:
        with self._lock:
            self._ensure_today_record()
            return int(self._state["counts_by_date"][self._today_str()])

    def increment(self, delta: int, event_time: datetime | None = None) -> int:
        with self._lock:
            self._ensure_today_record()
            today = self._today_str()
            current_value = int(self._state["counts_by_date"].get(today, 0))
            next_value = max(0, current_value + delta)
            self._state["counts_by_date"][today] = next_value
            if event_time is not None:
                self._state["last_input_at"] = event_time.isoformat(timespec="seconds")
            self._save()
            return next_value

    def reset_today(self) -> None:
        with self._lock:
            self._ensure_today_record()
            self._state["counts_by_date"][self._today_str()] = 0
            self._save()

    def get_summary(self) -> dict:
        with self._lock:
            self._ensure_today_record()
            today = date.today()
            today_str = today.isoformat()
            yesterday_str = (today - timedelta(days=1)).isoformat()
            last_7_days_total = 0

            for offset in range(7):
                day_key = (today - timedelta(days=offset)).isoformat()
                last_7_days_total += int(self._state["counts_by_date"].get(day_key, 0))

            return {
                "today_count": int(self._state["counts_by_date"].get(today_str, 0)),
                "yesterday_count": int(self._state["counts_by_date"].get(yesterday_str, 0)),
                "last_7_days_total": last_7_days_total,
                "last_input_at": self._state.get("last_input_at"),
            }

    def _today_str(self) -> str:
        return date.today().isoformat()

    def _resolve_writable_path(self, preferred_path: Path) -> Path:
        try:
            preferred_path.parent.mkdir(parents=True, exist_ok=True)
            return preferred_path
        except OSError:
            fallback_path = Path.cwd() / "data" / "daily_counts.json"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            return fallback_path

    def _ensure_today_record(self) -> None:
        today = self._today_str()
        self._state.setdefault("counts_by_date", {})
        self._state["counts_by_date"].setdefault(today, 0)

    def _load(self) -> dict:
        if not self.file_path.exists():
            return self._empty_state()

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return self._empty_state()

        if not isinstance(data, dict):
            return self._empty_state()

        if "counts_by_date" not in data:
            legacy_date = str(data.get("date", self._today_str()))
            legacy_count = max(0, int(data.get("count", 0)))
            return {
                "counts_by_date": {legacy_date: legacy_count},
                "last_input_at": None,
            }

        counts_by_date = {}
        raw_counts = data.get("counts_by_date", {})
        if isinstance(raw_counts, dict):
            for day_key, value in raw_counts.items():
                counts_by_date[str(day_key)] = max(0, int(value))

        return {
            "counts_by_date": counts_by_date,
            "last_input_at": data.get("last_input_at"),
        }

    def _empty_state(self) -> dict:
        return {
            "counts_by_date": {},
            "last_input_at": None,
        }

    def _save(self) -> None:
        with self.file_path.open("w", encoding="utf-8") as file:
            json.dump(self._state, file, ensure_ascii=False, indent=2)
