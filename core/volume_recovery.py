"""Volume recovery ledger: survive crashes and forced kills without leaving audio turned down.

Windows remembers every app's mixer level and the endpoint master level. If AudioClamp is killed
mid-clamp (Task Manager, crash, power loss), the game would come back at the clamped level on its
next launch and the next run would mistake that for the normal level.

The ledger records the true level of everything the limiter controls the moment it takes control:
game sessions by process name, and the master level per endpoint id. An entry is removed only once
that level has been written back. Anything still listed at startup is a leftover from an unclean
exit, and the engine puts it back. Entries for apps that are not running stay until they reappear.
"""
import math
import threading
from typing import Any, Dict, Optional

from core.safe_io import atomic_write_json, read_json, remove_file


def _valid_level(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    if not math.isfinite(v) or v < 0.01 or v > 1.0:
        return None
    return v


class VolumeLedger:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._sessions: Dict[str, float] = {}
        self._masters: Dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        state = read_json(self.path)
        if not isinstance(state, dict):
            if state is None:
                return
            remove_file(self.path)
            return
        for name, level in (state.get("sessions") or {}).items():
            v = _valid_level(level)
            if isinstance(name, str) and name and v is not None:
                self._sessions[name] = v
        for dev_id, level in (state.get("masters") or {}).items():
            v = _valid_level(level)
            if isinstance(dev_id, str) and dev_id and v is not None:
                self._masters[dev_id] = v

    def _save_locked(self) -> None:
        if not self._sessions and not self._masters:
            remove_file(self.path)
            return
        atomic_write_json(self.path, {"sessions": self._sessions, "masters": self._masters})

    # ---- Game sessions ----
    def session_levels(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._sessions)

    def record_session(self, name: str, level: float) -> None:
        v = _valid_level(level)
        if not name or v is None:
            return
        with self._lock:
            if self._sessions.get(name) == v:
                return
            self._sessions[name] = v
            self._save_locked()

    def resolve_session(self, name: str) -> None:
        with self._lock:
            if self._sessions.pop(name, None) is not None:
                self._save_locked()

    # ---- Master endpoint ----
    def master_level(self, device_id: str) -> Optional[float]:
        with self._lock:
            return self._masters.get(device_id)

    def record_master(self, device_id: str, level: float) -> None:
        v = _valid_level(level)
        if not device_id or v is None:
            return
        with self._lock:
            if self._masters.get(device_id) == v:
                return
            self._masters[device_id] = v
            self._save_locked()

    def resolve_master(self, device_id: str) -> None:
        with self._lock:
            if self._masters.pop(device_id, None) is not None:
                self._save_locked()

    @property
    def empty(self) -> bool:
        with self._lock:
            return not self._sessions and not self._masters
