from __future__ import annotations

import csv
import json
import os
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

    @property
    def backup_file_path(self) -> Path:
        return self.file_path.with_suffix(f"{self.file_path.suffix}.bak")

    def get_today_count(self) -> int:
        with self._lock:
            self._ensure_today_record()
            return int(self._state["counts_by_date"][self._today_str()])

    def record_key(
        self,
        delta: int,
        positive_count: int,
        backspace_count: int,
        pasted_count: int = 0,
        event_time: datetime | None = None,
        peak_wpm: float | None = None,
    ) -> int:
        with self._lock:
            self._ensure_today_record()
            today = self._today_str()
            current_value = int(self._state["counts_by_date"].get(today, 0))
            next_value = max(0, current_value + delta)
            self._state["counts_by_date"][today] = next_value

            if positive_count > 0:
                self._state["typed_by_date"][today] = int(self._state["typed_by_date"].get(today, 0)) + positive_count
            if pasted_count > 0:
                self._state["pasted_by_date"][today] = int(self._state["pasted_by_date"].get(today, 0)) + pasted_count
            if event_time is not None and positive_count > 0:
                hour_key = event_time.strftime("%H")
                keyboard_typed_count = max(0, positive_count - pasted_count)
                if keyboard_typed_count > 0:
                    self._increment_hour_bucket("hourly_typed_by_date", today, hour_key, keyboard_typed_count)
                if pasted_count > 0:
                    self._increment_hour_bucket("hourly_pasted_by_date", today, hour_key, pasted_count)
            if backspace_count > 0:
                self._state["backspace_by_date"][today] = int(self._state["backspace_by_date"].get(today, 0)) + backspace_count
            if peak_wpm is not None:
                current_peak = float(self._state["peak_wpm_by_date"].get(today, 0.0))
                self._state["peak_wpm_by_date"][today] = max(current_peak, float(peak_wpm))

            if event_time is not None:
                self._state["last_input_at"] = event_time.isoformat(timespec="seconds")
            self._save()
            return next_value

    def reset_today(self) -> None:
        with self._lock:
            self._ensure_today_record()
            today = self._today_str()
            self._state["counts_by_date"][today] = 0
            self._state["typed_by_date"][today] = 0
            self._state["pasted_by_date"][today] = 0
            self._state["backspace_by_date"][today] = 0
            self._state["peak_wpm_by_date"][today] = 0.0
            self._state["hourly_typed_by_date"][today] = {}
            self._state["hourly_pasted_by_date"][today] = {}
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

            typed_total_today = int(self._state["typed_by_date"].get(today_str, 0))
            pasted_today = int(self._state["pasted_by_date"].get(today_str, 0))
            typed_today = max(0, typed_total_today - pasted_today)
            backspace_today = int(self._state["backspace_by_date"].get(today_str, 0))
            peak_wpm_today = float(self._state["peak_wpm_by_date"].get(today_str, 0.0))
            kept_today = max(0, typed_today - backspace_today)
            accuracy = 0.0
            if typed_today > 0:
                accuracy = kept_today / typed_today

            return {
                "today_count": int(self._state["counts_by_date"].get(today_str, 0)),
                "yesterday_count": int(self._state["counts_by_date"].get(yesterday_str, 0)),
                "last_7_days_total": last_7_days_total,
                "last_input_at": self._state.get("last_input_at"),
                "typed_today": typed_today,
                "typed_total_today": typed_total_today,
                "pasted_today": pasted_today,
                "backspace_today": backspace_today,
                "kept_today": kept_today,
                "peak_wpm_today": peak_wpm_today,
                "accuracy": accuracy,
            }

    def get_recent_history(self, limit: int = 7) -> list[dict]:
        with self._lock:
            self._ensure_today_record()
            items = sorted(self._state["counts_by_date"].items(), reverse=True)
            history = []
            for day_key, count in items[:limit]:
                typed_total = int(self._state["typed_by_date"].get(day_key, 0))
                pasted = int(self._state["pasted_by_date"].get(day_key, 0))
                typed = max(0, typed_total - pasted)
                backspace = int(self._state["backspace_by_date"].get(day_key, 0))
                accuracy = 0.0
                if typed > 0:
                    accuracy = max(0, typed - backspace) / typed
                history.append({
                    "date": day_key,
                    "count": int(count),
                    "typed": typed,
                    "pasted": pasted,
                    "backspace": backspace,
                    "peak_wpm": float(self._state["peak_wpm_by_date"].get(day_key, 0.0)),
                    "accuracy": accuracy,
                })
            return history

    def get_trend_history(self, days: int = 30) -> list[dict]:
        with self._lock:
            self._ensure_today_record()
            today = date.today()
            history = []
            for offset in range(days - 1, -1, -1):
                day = today - timedelta(days=offset)
                day_key = day.isoformat()
                typed_total = int(self._state["typed_by_date"].get(day_key, 0))
                pasted = int(self._state["pasted_by_date"].get(day_key, 0))
                typed = max(0, typed_total - pasted)
                backspace = int(self._state["backspace_by_date"].get(day_key, 0))
                accuracy = 0.0
                if typed > 0:
                    accuracy = max(0, typed - backspace) / typed
                history.append({
                    "date": day_key,
                    "count": int(self._state["counts_by_date"].get(day_key, 0)),
                    "typed": typed,
                    "pasted": pasted,
                    "backspace": backspace,
                    "peak_wpm": float(self._state["peak_wpm_by_date"].get(day_key, 0.0)),
                    "accuracy": accuracy,
                })
            return history

    def get_full_history(self) -> list[dict]:
        with self._lock:
            self._ensure_today_record()
            history = []
            for day_key, count in sorted(self._state["counts_by_date"].items(), reverse=True):
                typed_total = int(self._state["typed_by_date"].get(day_key, 0))
                pasted = int(self._state["pasted_by_date"].get(day_key, 0))
                typed = max(0, typed_total - pasted)
                backspace = int(self._state["backspace_by_date"].get(day_key, 0))
                accuracy = 0.0
                if typed > 0:
                    accuracy = max(0, typed - backspace) / typed
                history.append({
                    "date": day_key,
                    "count": int(count),
                    "typed": typed,
                    "pasted": pasted,
                    "backspace": backspace,
                    "peak_wpm": float(self._state["peak_wpm_by_date"].get(day_key, 0.0)),
                    "accuracy": accuracy,
                })
            return history

    def get_hourly_distribution(self, day_key: str | None = None) -> list[dict]:
        with self._lock:
            self._ensure_today_record()
            target_day = day_key or self._today_str()
            typed_hours = self._state["hourly_typed_by_date"].get(target_day, {})
            pasted_hours = self._state["hourly_pasted_by_date"].get(target_day, {})
            distribution = []
            for hour in range(24):
                hour_key = f"{hour:02d}"
                typed = int(typed_hours.get(hour_key, 0))
                pasted = int(pasted_hours.get(hour_key, 0))
                distribution.append({
                    "hour": hour_key,
                    "typed": typed,
                    "pasted": pasted,
                    "total": typed + pasted,
                })
            return distribution

    def export_history_csv(self) -> Path:
        with self._lock:
            self._ensure_today_record()
            export_dir = self.data_dir / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = export_dir / f"typing_history_{timestamp}.csv"
            with export_path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["date", "count", "typed", "pasted", "backspace", "peak_wpm", "accuracy"])
                for day_key, count in sorted(self._state["counts_by_date"].items()):
                    typed_total = int(self._state["typed_by_date"].get(day_key, 0))
                    pasted = int(self._state["pasted_by_date"].get(day_key, 0))
                    typed = max(0, typed_total - pasted)
                    backspace = int(self._state["backspace_by_date"].get(day_key, 0))
                    peak_wpm = float(self._state["peak_wpm_by_date"].get(day_key, 0.0))
                    accuracy = 0.0
                    if typed > 0:
                        accuracy = max(0, typed - backspace) / typed
                    writer.writerow([day_key, int(count), typed, pasted, backspace, round(peak_wpm, 1), round(accuracy, 4)])
            return export_path

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
        self._state.setdefault("typed_by_date", {})
        self._state.setdefault("pasted_by_date", {})
        self._state.setdefault("backspace_by_date", {})
        self._state.setdefault("peak_wpm_by_date", {})
        self._state.setdefault("hourly_typed_by_date", {})
        self._state.setdefault("hourly_pasted_by_date", {})
        self._state["counts_by_date"].setdefault(today, 0)
        self._state["typed_by_date"].setdefault(today, 0)
        self._state["pasted_by_date"].setdefault(today, 0)
        self._state["backspace_by_date"].setdefault(today, 0)
        self._state["peak_wpm_by_date"].setdefault(today, 0.0)
        self._state["hourly_typed_by_date"].setdefault(today, {})
        self._state["hourly_pasted_by_date"].setdefault(today, {})

    def _load(self) -> dict:
        data = self._load_json_file(self.file_path)
        if data is None:
            data = self._load_json_file(self.backup_file_path)
        if data is None:
            return self._empty_state()

        if "counts_by_date" not in data:
            legacy_date = str(data.get("date", self._today_str()))
            legacy_count = max(0, int(data.get("count", 0)))
            return {
                "counts_by_date": {legacy_date: legacy_count},
                "typed_by_date": {legacy_date: legacy_count},
                "pasted_by_date": {legacy_date: 0},
                "backspace_by_date": {legacy_date: 0},
                "peak_wpm_by_date": {legacy_date: 0.0},
                "hourly_typed_by_date": {legacy_date: {}},
                "hourly_pasted_by_date": {legacy_date: {}},
                "last_input_at": None,
            }

        counts_by_date = {}
        typed_by_date = {}
        pasted_by_date = {}
        backspace_by_date = {}
        peak_wpm_by_date = {}
        hourly_typed_by_date = {}
        hourly_pasted_by_date = {}

        raw_counts = data.get("counts_by_date", {})
        if isinstance(raw_counts, dict):
            for day_key, value in raw_counts.items():
                counts_by_date[str(day_key)] = max(0, int(value))

        raw_typed = data.get("typed_by_date", {})
        if isinstance(raw_typed, dict):
            for day_key, value in raw_typed.items():
                typed_by_date[str(day_key)] = max(0, int(value))

        raw_pasted = data.get("pasted_by_date", {})
        if isinstance(raw_pasted, dict):
            for day_key, value in raw_pasted.items():
                pasted_by_date[str(day_key)] = max(0, int(value))

        raw_backspace = data.get("backspace_by_date", {})
        if isinstance(raw_backspace, dict):
            for day_key, value in raw_backspace.items():
                backspace_by_date[str(day_key)] = max(0, int(value))

        raw_peak_wpm = data.get("peak_wpm_by_date", {})
        if isinstance(raw_peak_wpm, dict):
            for day_key, value in raw_peak_wpm.items():
                peak_wpm_by_date[str(day_key)] = max(0.0, float(value))

        raw_hourly_typed = data.get("hourly_typed_by_date", {})
        if isinstance(raw_hourly_typed, dict):
            for day_key, hours in raw_hourly_typed.items():
                if isinstance(hours, dict):
                    hourly_typed_by_date[str(day_key)] = {
                        str(hour_key): max(0, int(value))
                        for hour_key, value in hours.items()
                    }

        raw_hourly_pasted = data.get("hourly_pasted_by_date", {})
        if isinstance(raw_hourly_pasted, dict):
            for day_key, hours in raw_hourly_pasted.items():
                if isinstance(hours, dict):
                    hourly_pasted_by_date[str(day_key)] = {
                        str(hour_key): max(0, int(value))
                        for hour_key, value in hours.items()
                    }

        return {
            "counts_by_date": counts_by_date,
            "typed_by_date": typed_by_date,
            "pasted_by_date": pasted_by_date,
            "backspace_by_date": backspace_by_date,
            "peak_wpm_by_date": peak_wpm_by_date,
            "hourly_typed_by_date": hourly_typed_by_date,
            "hourly_pasted_by_date": hourly_pasted_by_date,
            "last_input_at": data.get("last_input_at"),
        }

    def _empty_state(self) -> dict:
        return {
            "counts_by_date": {},
            "typed_by_date": {},
            "pasted_by_date": {},
            "backspace_by_date": {},
            "peak_wpm_by_date": {},
            "hourly_typed_by_date": {},
            "hourly_pasted_by_date": {},
            "last_input_at": None,
        }

    def _increment_hour_bucket(self, state_key: str, day_key: str, hour_key: str, amount: int) -> None:
        day_hours = self._state[state_key].setdefault(day_key, {})
        day_hours[hour_key] = int(day_hours.get(hour_key, 0)) + amount

    def _load_json_file(self, target: Path) -> dict | None:
        if not target.exists():
            return None

        try:
            with target.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None
        return data

    def _save(self) -> None:
        payload = json.dumps(self._state, ensure_ascii=False, indent=2)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temp file and atomically replace the target so an
        # interrupted save does not leave behind a truncated JSON file.
        self._write_json_atomic(self.file_path, payload)
        self._write_json_atomic(self.backup_file_path, payload)

    def _write_json_atomic(self, target: Path, payload: str) -> None:
        temp_path = target.with_suffix(f"{target.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, target)
