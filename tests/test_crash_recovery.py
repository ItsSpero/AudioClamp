"""Crash immunity tests: the real limiter worker runs against fake Windows audio objects.

A forced kill (Task Manager, crash, power loss) skips every cleanup path, so the only thing that
survives is what is on disk. Each scenario captures the recovery ledger while the limiter is
clamping, recreates the exact post-kill state (ledger on disk, volumes left clamped), and checks
that the next start puts everything back. No real audio device is touched.
"""
import os, sys, json, time, shutil, tempfile, pathlib
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path(__file__).resolve().parent.parent))

import core.audio_engine as ae
from core.audio_engine import AudioEngine
from core.config_manager import DEFAULT_CONFIG
from core.safe_io import atomic_write_json, read_json
from core.volume_recovery import VolumeLedger

GAME = "python.exe" if sys.executable.lower().endswith("python.exe") else os.path.basename(sys.executable)


class StubConfig:
    def __init__(self, **over):
        self.config = dict(DEFAULT_CONFIG); self.config.update(over); self.revision = 0
    def get(self, k, d=None): return self.config.get(k, d)
    def set(self, k, v, save=True): self.config[k] = v; self.revision += 1
    def apply_profile(self, n): pass


class FakeMeter:
    def __init__(self, peak): self.peak = peak
    def GetPeakValue(self, ptr): ptr.contents.value = self.peak
    def GetChannelsPeakValues(self, n, buf):
        for i in range(n): buf[i] = self.peak


class FakeEndpointVolume:
    def __init__(self, vol): self.vol = vol
    def GetChannelCount(self): return 2
    def RegisterControlChangeNotify(self, ptr): pass
    def UnregisterControlChangeNotify(self, ptr): pass
    def GetMasterVolumeLevelScalar(self): return self.vol
    def SetMasterVolumeLevelScalar(self, v, guid): self.vol = float(v)


class FakeActivator:
    def __init__(self, meter): self.meter = meter
    def Activate(self, iid, ctx, params): return self
    def QueryInterface(self, iface): return self.meter


class FakeDevice:
    def __init__(self, dev_id, vol, peak):
        self.id = dev_id
        self.FriendlyName = f"Fake {dev_id}"
        self.EndpointVolume = FakeEndpointVolume(vol)
        self.meter = FakeMeter(peak)
        self._dev = FakeActivator(self.meter)


class FakeSimpleVolume:
    def __init__(self, v): self.v = v
    def GetMasterVolume(self): return self.v
    def SetMasterVolume(self, v, guid): self.v = float(v)


class FakeSessionCtl:
    def __init__(self, meter, vol): self.meter, self.vol = meter, vol
    def QueryInterface(self, iface):
        return self.vol if iface is ae.ISimpleAudioVolume else self.meter
    def GetSessionInstanceIdentifier(self): return "fake-session"
    def GetState(self): return 1


class FakeSession:
    def __init__(self, pid, vol, peak):
        self.ProcessId = pid
        self.meter = FakeMeter(peak)
        self.SimpleAudioVolume = FakeSimpleVolume(vol)
        self._ctl = FakeSessionCtl(self.meter, self.SimpleAudioVolume)


class FakeAudioUtilities:
    speakers = None
    sessions = []
    @classmethod
    def GetSpeakers(cls): return cls.speakers
    @classmethod
    def GetAllSessions(cls): return list(cls.sessions)
    @classmethod
    def GetDeviceEnumerator(cls): raise OSError("no endpoint notifications in tests")


ae.AudioUtilities = FakeAudioUtilities
tmp = tempfile.mkdtemp(prefix="audioclamp_test_")
ae.APPDATA_DIR = tmp
LEDGER = os.path.join(tmp, "volume_recovery.json")


def near(a, b, tol=0.002): return abs(a - b) <= tol


def run_engine(secs, **cfg):
    eng = AudioEngine(StubConfig(auto_profile_switch=False, **cfg))
    eng.start()
    time.sleep(secs)
    return eng


def wait_for(cond, timeout=1.5):
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if cond(): return True
        time.sleep(0.01)
    return cond()


# ---- 1. Whole-PC mode: killed mid-clamp, next start restores the master level ----
dev = FakeDevice("{dev-A}", 0.8, 1.0)
FakeAudioUtilities.speakers, FakeAudioUtilities.sessions = dev, []
eng = run_engine(0.3, target_mode="master_device", threshold_db=-12.0)
clamped = dev.EndpointVolume.vol
assert clamped < 0.5, f"limiter should be clamping the master, got {clamped}"
on_disk = read_json(LEDGER)
assert on_disk and near(on_disk["masters"]["{dev-A}"], 0.8), on_disk
eng.stop()
assert near(dev.EndpointVolume.vol, 0.8) and not os.path.exists(LEDGER), "clean stop restores and clears"

atomic_write_json(LEDGER, on_disk)          # what a kill leaves behind ...
dev.EndpointVolume.vol = clamped            # ... with Windows holding the clamped level
dev.meter.peak = 0.0
eng = run_engine(0.15, target_mode="master_device", threshold_db=-12.0)
assert near(dev.EndpointVolume.vol, 0.8), f"startup must restore 0.8, got {dev.EndpointVolume.vol}"
assert near(eng.user_target_master_vol, 0.8), "the clamped level must not become the user's level"
eng.stop()
assert near(dev.EndpointVolume.vol, 0.8) and not os.path.exists(LEDGER)
print("1. whole-PC kill mid-clamp: master restored on next start")

# ---- 2. Whole-PC mode: switching the default device hands the old one back ----
dev_a, dev_b = FakeDevice("{dev-A}", 0.8, 1.0), FakeDevice("{dev-B}", 0.5, 1.0)
FakeAudioUtilities.speakers = dev_a
eng = run_engine(0.3, target_mode="master_device", threshold_db=-12.0)
assert dev_a.EndpointVolume.vol < 0.5
FakeAudioUtilities.speakers = dev_b
eng.signal_device_changed()
assert wait_for(lambda: dev_b.EndpointVolume.vol < 0.3), "new device is clamped"
assert near(dev_a.EndpointVolume.vol, 0.8), f"old device must be restored, got {dev_a.EndpointVolume.vol}"
eng.stop()
assert near(dev_b.EndpointVolume.vol, 0.5) and not os.path.exists(LEDGER)
print("2. device switch mid-clamp: old device restored, new device clamped, both clean on stop")

# ---- 3. Game session mode: killed mid-clamp, the game comes back at its true level ----
dev = FakeDevice("{dev-A}", 0.6, 0.0)
game = FakeSession(os.getpid(), 0.9, 1.0)
FakeAudioUtilities.speakers, FakeAudioUtilities.sessions = dev, [game]
eng = run_engine(0.3, target_mode="auto_game", monitored_apps=[GAME], threshold_db=-12.0)
clamped = game.SimpleAudioVolume.v
assert clamped < 0.5, f"game session should be clamped, got {clamped}"
assert near(dev.EndpointVolume.vol, 0.6), "session mode must never touch the master"
on_disk = read_json(LEDGER)
assert on_disk and near(on_disk["sessions"][GAME], 0.9), on_disk
eng.stop()
assert near(game.SimpleAudioVolume.v, 0.9) and not os.path.exists(LEDGER)

atomic_write_json(LEDGER, on_disk)
game.SimpleAudioVolume.v = clamped          # Windows remembered the clamped mixer level
game.meter.peak = 0.0
eng = run_engine(0.15, target_mode="auto_game", monitored_apps=[GAME], threshold_db=-12.0)
assert near(game.SimpleAudioVolume.v, 0.9), f"game must be back at 0.9, got {game.SimpleAudioVolume.v}"
assert near(eng.session_base_volumes[GAME], 0.9), "clamped level must not be re-measured as the baseline"
eng.stop()
assert near(game.SimpleAudioVolume.v, 0.9) and not os.path.exists(LEDGER)
print("3. game-session kill mid-clamp: game restored and baseline kept")

# ---- 4. Leftover for a game that is not running survives until it launches ----
atomic_write_json(LEDGER, {"sessions": {GAME: 0.75}, "masters": {}})
FakeAudioUtilities.sessions = []
eng = run_engine(0.1, target_mode="auto_game", monitored_apps=[GAME])
eng.stop()
assert read_json(LEDGER) == {"sessions": {GAME: 0.75}, "masters": {}}, "entry must wait for the game"
game = FakeSession(os.getpid(), 0.3, 0.0)    # game launches at its clamped persisted level
FakeAudioUtilities.sessions = [game]
eng = run_engine(0.2, target_mode="auto_game", monitored_apps=[GAME])
eng.stop()
assert near(game.SimpleAudioVolume.v, 0.75) and not os.path.exists(LEDGER)
print("4. leftover for a closed game: kept on disk, applied when the game appears")

# ---- 5. Ledger and atomic writes reject garbage and never leave partial files ----
bad = os.path.join(tmp, "bad.json")
open(bad, "w").write('{"sessions": {"a.exe": 0.5')   # torn write from an old version
assert VolumeLedger(bad).empty
open(bad, "w").write('{"sessions": {"a.exe": 0.5, "b.exe": "loud", "c.exe": Infinity, "d.exe": 3.0, "e.exe": true}}')
assert VolumeLedger(bad).session_levels() == {"a.exe": 0.5}
good = os.path.join(tmp, "good.json")
assert atomic_write_json(good, {"v": 1})
assert not atomic_write_json(good, {"v": float("nan")}), "NaN must be refused"
assert read_json(good) == {"v": 1}, "a failed write keeps the previous file"
assert not [f for f in os.listdir(tmp) if f.endswith(".tmp")], "no temp files left behind"
print("5. ledger validation and atomic writes: OK")

shutil.rmtree(tmp, ignore_errors=True)
print("Crash recovery: all 5 scenarios passed")
