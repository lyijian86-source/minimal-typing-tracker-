from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

import keyboard

from type_record.config import AppConfig
from type_record.storage import DailyCountStore


IGNORED_KEYS = {
    "shift",
    "left shift",
    "right shift",
    "ctrl",
    "left ctrl",
    "right ctrl",
    "alt",
    "left alt",
    "right alt",
    "alt gr",
    "windows",
    "left windows",
    "right windows",
    "caps lock",
    "tab",
    "esc",
    "up",
    "down",
    "left",
    "right",
    "insert",
    "delete",
    "home",
    "end",
    "page up",
    "page down",
    "print screen",
    "menu",
}


@dataclass
class KeyboardCounter:
    config: AppConfig
    store: DailyCountStore

    def __post_init__(self) -> None:
        self._hook = None
        self._lock = Lock()
        self._session_delta = 0
        self._session_positive_count = 0
        self._last_input_at: datetime | None = None
        self._recent_positive_events: deque[datetime] = deque()

    def start(self) -> None:
        if self._hook is not None:
            return
        self._hook = keyboard.on_press(self._handle_key_event, suppress=False)

    def stop(self) -> None:
        if self._hook is None:
            return
        keyboard.unhook(self._hook)
        self._hook = None

    def get_live_stats(self) -> dict:
        with self._lock:
            self._trim_recent_events()
            return {
                "session_delta": self._session_delta,
                "session_positive_count": self._session_positive_count,
                "recent_cpm": len(self._recent_positive_events),
                "last_input_at": self._last_input_at.isoformat(timespec="seconds") if self._last_input_at else None,
            }

    def reset_session_stats(self) -> None:
        with self._lock:
            self._session_delta = 0
            self._session_positive_count = 0
            self._last_input_at = None
            self._recent_positive_events.clear()

    def _handle_key_event(self, event: keyboard.KeyboardEvent) -> None:
        key_name = (event.name or "").lower()
        if not key_name or key_name in IGNORED_KEYS:
            return

        delta = self._resolve_delta(key_name)
        if delta == 0:
            return

        now = datetime.now()
        self.store.increment(delta, event_time=now)

        with self._lock:
            self._session_delta += delta
            self._last_input_at = now
            if delta > 0:
                self._session_positive_count += delta
                for _ in range(delta):
                    self._recent_positive_events.append(now)
            self._trim_recent_events()

    def _trim_recent_events(self) -> None:
        now = datetime.now()
        while self._recent_positive_events and (now - self._recent_positive_events[0]).total_seconds() > 60:
            self._recent_positive_events.popleft()

    def _resolve_delta(self, key_name: str) -> int:
        if len(key_name) == 1:
            return 1

        if key_name == "space":
            return 1 if self.config.count_space else 0

        if key_name == "enter":
            return 1 if self.config.count_enter else 0

        if key_name == "backspace":
            return -1 if self.config.backspace_decrements else 0

        return 0
