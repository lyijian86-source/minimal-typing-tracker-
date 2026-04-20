from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

import keyboard

from type_record.config import AppConfig
from type_record.storage import DailyCountStore

CF_UNICODETEXT = 13


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
        self._session_started_at: datetime | None = None
        self._session_day_key: str | None = None
        self._session_delta = 0
        self._session_positive_count = 0
        self._session_pasted_count = 0
        self._session_backspace_count = 0
        self._last_input_at: datetime | None = None
        self._recent_positive_events: deque[datetime] = deque()

    def start(self) -> None:
        if self._hook is not None:
            return
        self._hook = keyboard.on_press(self._handle_key_event, suppress=False)

    def stop(self) -> None:
        if self._hook is None:
            return
        try:
            keyboard.unhook(self._hook)
        except KeyError:
            # The keyboard package may already have dropped the hook reference.
            # Treat stop as best-effort so shutdown can still flush session data.
            pass
        self._hook = None
        snapshot = None
        with self._lock:
            snapshot = self._snapshot_current_session(self._last_input_at or self._now())
            self._clear_session_state()
        if snapshot is not None:
            self.store.record_session(**snapshot)

    def get_live_stats(self) -> dict:
        snapshot = None
        with self._lock:
            now = self._now()
            snapshot = self._reset_session_if_day_changed(now)
            self._trim_recent_events(now)
            session_typed_count = max(0, self._session_positive_count - self._session_pasted_count)
            session_is_active = self._is_session_active(now)
            session_duration_seconds = 0
            if self._session_started_at is not None:
                session_end = now if session_is_active else self._last_input_at
                if session_end is not None:
                    session_duration_seconds = max(0, int((session_end - self._session_started_at).total_seconds()))
            accuracy = 0.0
            if session_typed_count > 0:
                accuracy = max(0, session_typed_count - self._session_backspace_count) / session_typed_count
            stats = {
                "session_is_active": session_is_active,
                "session_duration_seconds": session_duration_seconds,
                "session_delta": self._session_delta,
                "session_positive_count": session_typed_count,
                "session_pasted_count": self._session_pasted_count,
                "session_backspace_count": self._session_backspace_count,
                "recent_cpm": len(self._recent_positive_events),
                "last_input_at": self._last_input_at.isoformat(timespec="seconds") if self._last_input_at else None,
                "session_accuracy": accuracy,
            }
        if snapshot is not None:
            self.store.record_session(**snapshot)
        return stats

    def reset_session_stats(self) -> None:
        with self._lock:
            self._clear_session_state()

    def _handle_key_event(self, event: keyboard.KeyboardEvent) -> None:
        key_name = (event.name or "").lower()
        if not key_name or key_name in IGNORED_KEYS:
            return

        paste_count = self._resolve_paste_count(key_name)
        if paste_count > 0:
            # Pasted text contributes to total text volume, but it should not
            # inflate typing speed metrics such as CPM or peak WPM.
            self._record_input(delta=paste_count, positive_count=paste_count, pasted_count=paste_count, backspace_count=0, count_for_speed=False)
            return

        delta = self._resolve_delta(key_name)
        is_backspace = key_name == "backspace"
        if delta > 0 and self._has_shortcut_modifier():
            # Ignore text-like keys while Ctrl/Alt/Win shortcuts are active.
            # This prevents combinations such as Ctrl+V/C/A or Win+R from being
            # miscounted as actual typed characters.
            return

        positive_count = delta if delta > 0 else 0
        backspace_count = 1 if is_backspace else 0

        if delta == 0 and backspace_count == 0:
            return

        self._record_input(delta=delta, positive_count=positive_count, pasted_count=0, backspace_count=backspace_count, count_for_speed=positive_count > 0)

    def _record_input(self, delta: int, positive_count: int, pasted_count: int, backspace_count: int, count_for_speed: bool) -> None:
        now = self._now()
        peak_wpm: float | None = None
        snapshot = None

        with self._lock:
            snapshot = self._ensure_active_session(now)
            self._session_delta += delta
            self._last_input_at = now
            if positive_count > 0:
                self._session_positive_count += positive_count
                self._session_pasted_count += pasted_count
                if count_for_speed:
                    for _ in range(positive_count):
                        self._recent_positive_events.append(now)
            if backspace_count > 0:
                self._session_backspace_count += backspace_count
            self._trim_recent_events(now)
            if positive_count > 0 and count_for_speed:
                peak_wpm = len(self._recent_positive_events) / 5.0

        if snapshot is not None:
            self.store.record_session(**snapshot)
        self.store.record_key(
            delta=delta,
            positive_count=positive_count,
            backspace_count=backspace_count,
            pasted_count=pasted_count,
            event_time=now,
            peak_wpm=peak_wpm,
        )

    def _trim_recent_events(self, now: datetime | None = None) -> None:
        now = now or self._now()
        while self._recent_positive_events and (now - self._recent_positive_events[0]).total_seconds() > 60:
            self._recent_positive_events.popleft()

    def _ensure_active_session(self, now: datetime) -> dict | None:
        snapshot = self._reset_session_if_day_changed(now)
        if self._session_started_at is None:
            self._start_new_session(now)
            return snapshot
        if self._is_session_expired(now):
            expired_snapshot = self._snapshot_current_session(self._last_input_at or now)
            self._start_new_session(now)
            return expired_snapshot or snapshot
        return snapshot

    def _start_new_session(self, now: datetime) -> None:
        self._session_started_at = now
        self._session_day_key = now.date().isoformat()
        self._session_delta = 0
        self._session_positive_count = 0
        self._session_pasted_count = 0
        self._session_backspace_count = 0
        self._recent_positive_events.clear()

    def _reset_session_if_day_changed(self, now: datetime) -> dict | None:
        if self._session_day_key is None:
            return None
        if self._session_day_key == now.date().isoformat():
            return None

        # Session metrics are presented as "today/current session" context.
        # Once the day changes, carrying yesterday's runtime session into the
        # new day makes the numbers hard to interpret, so we start fresh.
        snapshot = self._snapshot_current_session(self._last_input_at or now)
        self._clear_session_state()
        return snapshot

    def _is_session_active(self, now: datetime) -> bool:
        return self._session_started_at is not None and not self._is_session_expired(now)

    def _is_session_expired(self, now: datetime) -> bool:
        if self._last_input_at is None:
            return False
        return (now - self._last_input_at).total_seconds() >= self.config.session_timeout_seconds

    def _now(self) -> datetime:
        return datetime.now()

    def _snapshot_current_session(self, ended_at: datetime) -> dict | None:
        if self._session_started_at is None:
            return None
        keyboard_typed = max(0, self._session_positive_count - self._session_pasted_count)
        if keyboard_typed <= 0 and self._session_pasted_count <= 0 and self._session_backspace_count <= 0 and self._session_delta == 0:
            return None
        return {
            "started_at": self._session_started_at,
            "ended_at": ended_at,
            "delta": self._session_delta,
            "positive_count": self._session_positive_count,
            "pasted_count": self._session_pasted_count,
            "backspace_count": self._session_backspace_count,
        }

    def _clear_session_state(self) -> None:
        self._session_started_at = None
        self._session_day_key = None
        self._session_delta = 0
        self._session_positive_count = 0
        self._session_pasted_count = 0
        self._session_backspace_count = 0
        self._last_input_at = None
        self._recent_positive_events.clear()

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

    def _has_shortcut_modifier(self) -> bool:
        ctrl_pressed = self._is_pressed("ctrl", "left ctrl", "right ctrl")
        win_pressed = self._is_pressed("windows", "left windows", "right windows")

        # AltGr is commonly represented as Ctrl+Alt on Windows keyboard hooks.
        # Keep it out of the shortcut filter so layouts that rely on AltGr do
        # not lose valid character counts.
        alt_gr_pressed = self._is_pressed("alt gr")
        alt_pressed = self._is_pressed("alt", "left alt", "right alt")
        pure_alt_pressed = alt_pressed and not alt_gr_pressed and not ctrl_pressed

        return ctrl_pressed or win_pressed or pure_alt_pressed

    def _resolve_paste_count(self, key_name: str) -> int:
        if not self._is_paste_shortcut(key_name):
            return 0

        clipboard_text = self._get_clipboard_text()
        if not clipboard_text:
            return 0
        return self._count_pasted_characters(clipboard_text)

    def _is_paste_shortcut(self, key_name: str) -> bool:
        ctrl_pressed = self._is_pressed("ctrl", "left ctrl", "right ctrl")
        shift_pressed = self._is_pressed("shift", "left shift", "right shift")
        alt_pressed = self._is_pressed("alt", "left alt", "right alt")
        win_pressed = self._is_pressed("windows", "left windows", "right windows")

        ctrl_v = key_name == "v" and ctrl_pressed and not alt_pressed and not win_pressed
        shift_insert = key_name == "insert" and shift_pressed and not ctrl_pressed and not alt_pressed and not win_pressed
        return ctrl_v or shift_insert

    def _is_pressed(self, *keys: str) -> bool:
        return any(keyboard.is_pressed(key) for key in keys)

    def _get_clipboard_text(self) -> str | None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        if not user32.OpenClipboard(None):
            return None

        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None

            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return None

            try:
                return ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def _count_pasted_characters(self, text: str) -> int:
        count = 0
        for char in text:
            if char == "\r":
                continue
            if char == " ":
                count += 1 if self.config.count_space else 0
                continue
            if char == "\n":
                count += 1 if self.config.count_enter else 0
                continue
            if char == "\t":
                continue
            if char.isprintable():
                count += 1
        return count
