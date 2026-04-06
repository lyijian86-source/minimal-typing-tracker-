# Type Record

Minimal Windows desktop input counter:

- Runs in the background
- Listens to global keyboard input
- Stores only daily totals
- Does not store typed content
- Minimizes to the system tray

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

## Behavior

- V1 counts stable input units from key presses, not guaranteed final text inserted into every app
- Direct single-key printable input counts as `+1`
- `Space` counts by default
- `Enter` does not count by default
- `Backspace` is ignored by default
- Closing the window hides it to the system tray
- Use the tray menu to show the window again or exit the app

## Notes on accuracy

- This app uses a global keyboard hook, so its most stable metric is counted key input rather than final committed text.
- In IME scenarios such as Chinese pinyin composition and candidate selection, totals reflect key actions consistently, but may not match the exact number of characters finally committed to the target app.
- `Backspace` is ignored by default because deletion is not a reliable inverse of previously counted input across IMEs, selections, replacements, and app-specific behavior.

## Data file

The app first tries:

```text
%APPDATA%\TypeRecord\data\daily_counts.json
```

If that path is not writable, it falls back to:

```text
<project>\data\daily_counts.json
```
