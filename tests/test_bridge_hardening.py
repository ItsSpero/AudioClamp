"""Bridge hardening tests: input validation, non-blocking telemetry, WebView navigation rules."""
import sys, time, pathlib
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path(__file__).resolve().parent.parent))

from ui import bridge_validation as bv
from ui.telemetry_pump import LatestValueSender
from ui.webview_hardening import is_navigation_allowed, origin_of

# ---- 1. Numbers: finite only, clamped to what the UI offers ----
nan, inf = float("nan"), float("inf")
for junk in (nan, inf, -inf, "nan", "inf", "12; alert(1)", None, [], {}, True, False):
    assert bv.finite_number(junk, *bv.THRESHOLD_DB_RANGE) is None, junk
assert bv.finite_number(-12, *bv.THRESHOLD_DB_RANGE) == -12.0
assert bv.finite_number(-500, *bv.THRESHOLD_DB_RANGE) == -30.0
assert bv.finite_number(25, *bv.THRESHOLD_DB_RANGE) == 0.0
assert bv.finite_number(" -6.5 ", *bv.THRESHOLD_DB_RANGE) == -6.5
assert bv.finite_number(1e9, *bv.RELEASE_MS_RANGE) == 1000.0
assert bv.finite_number(1, *bv.RELEASE_MS_RANGE) == 40.0, "the 40 ms release floor holds at the bridge too"
assert bv.finite_number(99, *bv.BOOST_DB_RANGE) == 12.0
print("1. numeric validation: OK")

# ---- 2. Modes and profiles: allow-lists only ----
assert bv.choice("auto_game", bv.TARGET_MODES) == "auto_game"
for junk in ("master", "AUTO_GAME", "", None, 1, "auto_game "):
    assert bv.choice(junk, bv.TARGET_MODES) is None, junk
assert bv.choice("brickwall", bv.KNEE_MODES) == "brickwall"
assert bv.choice("hard", bv.KNEE_MODES) is None
assert bv.boolean(True) is True and bv.boolean(0) is False
assert bv.boolean("true") is None and bv.boolean(2) is None and bv.boolean(None) is None
print("2. allow-lists and booleans: OK")

# ---- 3. Executable names: bare file names only ----
assert bv.exe_name("TslGame.exe") == "TslGame.exe"
assert bv.exe_name(r"C:\Games\PUBG\TslGame.exe") == "TslGame.exe"
assert bv.exe_name("cs2", require_exe=True) == "cs2.exe"
assert bv.exe_name("../../evil.exe") == "evil.exe"
for junk in ("", "   ", "..", 'a"b.exe', "a<b>.exe", "a|b.exe", "x\x00.exe", "a" * 200 + ".exe", None, 5):
    assert bv.exe_name(junk) is None, repr(junk)
print("3. executable names: OK")

# ---- 4. Devices and window coordinates ----
known = ["{0.0.0.00000000}.{aaaa}", "{0.0.0.00000000}.{bbbb}"]
assert bv.device_id(known[1], known) == known[1]
assert bv.device_id("{0.0.0.00000000}.{cccc}", known) is None
assert bv.device_id(None, known) is None and bv.device_id("x" * 600, known) is None
assert bv.window_coord(120.7) == 120 and bv.window_coord(1e12) == 32767 and bv.window_coord(nan) is None
print("4. device ids and window coordinates: OK")

# ---- 5. Telemetry never blocks the limiter, even when the WebView stalls ----
delivered = []
def slow_send(payload):
    time.sleep(0.5)          # a stalled renderer
    delivered.append(payload)

sender = LatestValueSender(slow_send)
worst = 0.0
for i in range(200):
    t = time.perf_counter()
    sender.submit(f'{{"n": {i}}}')
    worst = max(worst, time.perf_counter() - t)
    time.sleep(0.003)        # one limiter tick
assert worst < 0.005, f"submit blocked for {worst * 1000:.1f} ms"
deadline = time.perf_counter() + 3.0
while (not delivered or delivered[-1] != '{"n": 199}') and time.perf_counter() < deadline:
    time.sleep(0.02)
assert delivered and delivered[-1] == '{"n": 199}', "the newest packet is always delivered"
assert len(delivered) < 10 and sender.dropped > 150, "stale packets are dropped, not queued"
sender.stop()
print(f"5. telemetry: worst submit {worst * 1e6:.0f} us with a 500 ms stalled WebView, "
      f"{len(delivered)} sent, {sender.dropped} stale dropped")

# ---- 6. Navigation stays on the app's own origin ----
app = origin_of("http://127.0.0.1:51234/index.html")
assert is_navigation_allowed("http://127.0.0.1:51234/index.html#guide", app)
assert is_navigation_allowed("about:blank", app)
for uri in ("http://127.0.0.1:51235/index.html", "https://example.com/", "file:///C:/Users/x/Downloads/evil.html",
            "javascript:alert(1)", "data:text/html,<script>1</script>", ""):
    assert not is_navigation_allowed(uri, app), uri
file_app = origin_of("file:///C:/Program%20Files/AudioClamp/ui/web/index.html")
assert is_navigation_allowed("file:///C:/Program%20Files/AudioClamp/ui/web/index.html?x=1", file_app)
assert not is_navigation_allowed("file:///C:/Users/x/Desktop/evil.html", file_app)
print("6. navigation lock: OK")

print("Bridge hardening: all 6 checks passed")
