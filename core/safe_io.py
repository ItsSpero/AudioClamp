"""Crash-safe JSON persistence.

Every file AudioClamp keeps (settings, volume recovery ledgers) is written to a temp file in the
same folder, flushed to disk, and then swapped in with os.replace, which is atomic on NTFS. A
power loss or forced kill mid-write leaves either the old file or the new one, never half of each.
"""
import json
import os
from typing import Any, Optional


def atomic_write_json(path: str, data: Any, indent: Optional[int] = None) -> bool:
    """Write data as JSON to path atomically. Returns False (and leaves path untouched) on failure."""
    tmp_path = f"{path}.{os.getpid()}.tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        print(f"[safe_io] Could not write {os.path.basename(path)}: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False


def read_json(path: str) -> Optional[Any]:
    """Return the parsed file, or None when it is missing or unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def remove_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[safe_io] Could not remove {os.path.basename(path)}: {e}")
