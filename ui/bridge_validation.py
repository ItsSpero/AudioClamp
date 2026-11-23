"""Strict validation for values arriving from the page through window.pywebview.api.

Everything the page sends is untrusted: values are type-checked, rejected when not finite, and
clamped to the range the UI itself offers. Invalid input returns None and changes nothing.
"""
import math
import os
import re
from typing import Any, Iterable, Optional

TARGET_MODES = frozenset({"auto_game", "specific_app", "master_device"})
KNEE_MODES = frozenset({"soft_knee", "brickwall"})

THRESHOLD_DB_RANGE = (-30.0, 0.0)
RELEASE_MS_RANGE = (40.0, 1000.0)
BOOST_DB_RANGE = (0.0, 12.0)
GUARD_DB_RANGE = (0.0, 12.0)
NUDGE_DB_RANGE = (-12.0, 12.0)
WINDOW_COORD_RANGE = (-32768, 32767)

MAX_EXE_NAME_LEN = 128
MAX_DEVICE_ID_LEN = 512
# A Windows file name: no path separators, reserved characters or control characters
_EXE_NAME_RE = re.compile(r'^[^<>:"/\\|?*\x00-\x1f]+$')


def finite_number(value: Any, lo: float, hi: float) -> Optional[float]:
    """A real, finite number clamped to [lo, hi]; None for anything else (bools, NaN, text)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            return None
    if not isinstance(value, (int, float)):
        return None
    v = float(value)
    if not math.isfinite(v):
        return None
    return max(lo, min(hi, v))


def choice(value: Any, allowed: Iterable[str]) -> Optional[str]:
    return value if isinstance(value, str) and value in allowed else None


def exe_name(value: Any, require_exe: bool = False) -> Optional[str]:
    """A bare executable file name such as 'TslGame.exe'. Paths are reduced to their file name."""
    if not isinstance(value, str):
        return None
    name = os.path.basename(value.strip().replace("/", "\\")).strip()
    if require_exe and name and not name.lower().endswith(".exe"):
        name += ".exe"
    if not name or name in (".", "..") or len(name) > MAX_EXE_NAME_LEN:
        return None
    if not _EXE_NAME_RE.match(name):
        return None
    return name


def device_id(value: Any, known_ids: Iterable[str]) -> Optional[str]:
    """Only an id of a playback device Windows reports as active right now."""
    if not isinstance(value, str) or not value or len(value) > MAX_DEVICE_ID_LEN:
        return None
    return value if value in set(known_ids) else None


def window_coord(value: Any) -> Optional[int]:
    v = finite_number(value, *WINDOW_COORD_RANGE)
    return None if v is None else int(v)


def boolean(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None
