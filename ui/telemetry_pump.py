"""Hands telemetry from the limiter thread to the WebView without ever blocking it.

pywebview's evaluate_js waits until WebView2 has run the script and returned. Calling it from the
MMCSS limiter thread meant every 50 ms the limiter sat idle for that round trip, and a busy or
stalled renderer paused clamping with it. submit() only stores the newest packet and wakes a
sender thread; if the WebView falls behind, older packets are dropped, never queued.
"""
import threading
from typing import Callable, Optional


class LatestValueSender:
    def __init__(self, send: Callable[[str], None], name: str = "AudioClamp-Telemetry"):
        self._send = send
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending: Optional[str] = None
        self._running = True
        self.sent = 0
        self.dropped = 0
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit(self, payload: str) -> None:
        """Non-blocking. Replaces any packet the sender has not picked up yet."""
        with self._lock:
            if self._pending is not None:
                self.dropped += 1
            self._pending = payload
        self._wake.set()

    def discard_pending(self) -> None:
        with self._lock:
            self._pending = None

    def stop(self, timeout: float = 1.0) -> None:
        self._running = False
        self._wake.set()
        self._thread.join(timeout)

    def _run(self) -> None:
        while self._running:
            self._wake.wait()
            self._wake.clear()
            with self._lock:
                payload, self._pending = self._pending, None
            if payload is None or not self._running:
                continue
            try:
                self._send(payload)
                self.sent += 1
            except Exception:
                pass
