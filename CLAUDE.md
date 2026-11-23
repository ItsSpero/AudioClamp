# AudioClamp — Project Architecture & AI Memory

AudioClamp is a Windows real-time audio peak limiter and dynamic range controller for competitive esports and hearing protection, providing sub-millisecond WASAPI session and master limiting.

This document serves as persistent memory and instructions for AI assistants (Claude, ChatGPT, Cursor, Windsurf, Copilot, Antigravity) working on the codebase.

---

## Tech Stack
- **Runtime**: Python 3.12+ (Windows x86_64)
- **Audio API**: CoreAudio WASAPI, MMCSS Pro Audio, `pycaw`, `comtypes`
- **GUI Engine**: `pywebview` (Microsoft Edge WebView2) + HTML5, CSS3, Vanilla JS Canvas visualizer
- **Packaging**: PyInstaller standalone executable + Inno Setup 6 installer
- **CI/CD**: GitHub Actions (`.github/workflows/ci-release.yml`)

---

## Key Commands
- **Run Source**: `python main.py`
- **Run Test Suite**: `python tests/test_footstep_boost.py; python tests/test_combat_guard.py; python tests/test_dsp_smoke.py; python tests/test_spray_sim.py; python tests/test_crash_recovery.py; python tests/test_bridge_hardening.py`
  - `test_dsp_smoke.py` runs the real worker against live devices; in auto-detect mode it will target a running game's session, so run it with games closed.
- **Syntax Validation**: `python -m compileall .` and `node -c ui/web/app.js`
- **Build Standalone Executable**: `python build_exe.py` → `dist/AudioClamp.exe` (~32 MB)
- **Build Setup Installer**: `python build_exe.py --installer` → `dist/installer/AudioClamp-Setup-<version>.exe` (~24 MB, requires Inno Setup 6; version pulled from `core/__init__.py`)
- **Install Locally**: `powershell -ExecutionPolicy Bypass -File Install-AudioClamp.ps1`
- **Check Single-Instance Mutex**: `powershell -Command "try { [System.Threading.Mutex]::OpenExisting('AudioClamp_SingleInstance_Mutex_391827'); 'HELD' } catch { 'FREE' }"`

---

## Critical Invariants & Architecture Rules

### 1. Single-Instance Mutex
Process ownership is locked with `AudioClamp_SingleInstance_Mutex_391827`.
* When running local builds or tests, verify this mutex is `FREE` before and after.
* Never leave hanging background processes that hold the mutex.

### 2. Limiter DSP Invariants (`core/audio_engine.py`)
* **Attack Phase**: Only engages when downward attenuation is required (`target_att < current_att`). Never increase gain in the attack branch.
* **Release Phase**: Uses two-stage exponential decay: at the 40 ms floor while more than 3 dB of reduction remains, then `max(0.040, release_ms / 1000.0)` for the last 3 dB. Time constant never drops below 40 ms. An adaptive 25–38ms transient hold (`release_ms / 3500`) prevents gunshot echo surges.
* **4:1 Soft-Knee Dynamics**: Competitive shooter profiles (PUBG, CS2, Tarkov) enforce a 4:1 soft-knee ratio with 5.0 dB knee width to preserve acoustic distance perception.
* **Hearing-Safe Mode (`hearing_safe`)**: Opt-in override that swaps the knee for a hard brickwall cap at the ceiling, replaces adaptive hold with a 150 ms combat hold, and disables the fast release stage.
* **Combat Guard (`combat_guard_db`)**: Keeps gain reduced between bursts (4 s timer). Only caps how far gain recovers during combat; it must never push gain down in the release branch.
* **Footstep Boost (`core/footstep_boost.py`)**: Raises Windows master volume by B dB, lowers all non-game apps (Discord, browser) by B dB, and lowers the ceiling by B dB. Only active while the limiter is ON and a game session is isolated. Adjustments must be relative to current levels and survive user manual volume changes.
* **Polling Rate**: Fixed-rate ~333 Hz (3 ms) worker loop. (Meter-synced polling was benchmarked and discarded because jitter increased reaction time from 1.5 ms to 5.4 ms).
* **Volume Recovery Ledger (`core/volume_recovery.py`)**: Before the limiter first writes a game session or the master endpoint, it records the true level in `%LOCALAPPDATA%\AudioClamp\volume_recovery.json`; entries are removed only after that level is written back. Leftovers at startup come from an unclean exit and are restored (sessions immediately or when the game reappears, master when its device is bound). Never write a clamped volume before recording the baseline.
* **Limiter Thread Never Blocks**: Telemetry goes through `ui/telemetry_pump.py` (latest-value, non-blocking); never call `evaluate_js` from the worker. Session rescans enumerate on the cached `IAudioSessionManager2` of the bound endpoint; `AudioUtilities.GetAllSessions()` costs ~28 ms and must stay out of the worker loop.
* **Hardware Latency Reality**: Windows WASAPI per-session meters only refresh every ~28 ms (measured in PUBG). The first ~30 ms of any initial transient crack passes before a volume-based clamp can land. Never claim 0 ms reaction time in UI copy.

### 3. Persistence & Bridge Security
* All JSON files are written through `core/safe_io.atomic_write_json` (temp file + fsync + `os.replace`).
* Every `JsApi` argument is validated in `ui/bridge_validation.py` (finite numbers clamped to UI ranges, allow-listed modes/profiles, bare `.exe` names, known device ids). Invalid input changes nothing.
* `ui/webview_hardening.py` locks WebView2 to the app's own origin, refuses external drops and disables zoom/autofill. The page has a CSP and loads no remote resources (fonts are bundled in `ui/web/assets/fonts`).

### 4. Windows COM & Audio Endpoint Switching
* Worker threads must call `CoInitializeEx(COINIT_MULTITHREADED)` and gracefully catch `OSError` if already initialized.
* Output device switching routes via undocumented native Windows COM interface `IPolicyConfig` (`CLSID_PolicyConfigClient = {870AF99C-171D-4F9E-AF0D-E63Df40c2BC9}`).

### 5. UI Design System (Midnight Navy & Ice Blue)
* **Theme Palette**:
  - Base Background: `#070B14`
  - Window & Card Base: `#0B111E` / `#111A2E`
  - Elevated Card Elements: `#162036`
  - Slate Borders: `rgba(148, 163, 184, 0.12)` (`#1E293B`)
* **Accents**:
  - Unified Primary Accent: Ice Blue `#38BDF8`.
  - Emergency / Limit / Clamping ONLY: Rose/Coral `#F43F5E`.
  - Success / Online: Emerald `#10B981`.
* **Zero Visual Glare / Clutter**:
  - Never introduce neon rainbows (no competing bright cyan, lime green, yellow, crimson elements).
  - No redundant quick-pill buttons under continuous sliders.
  - No inline circular `(?)` buttons (all guide documentation lives inside the dedicated `📖 Guide` modal).
  - Competitive Presets are rendered in a compact horizontal strip.

### 6. Clean Code & Dead Code Policy
* In v2.6.2, 161 lines of legacy fallbacks were purged:
  - DO NOT re-add `#unifiedStatusPill`, `#powerDot`, `#powerStatusText`, `#autoStatusBadge`, `#discordBadge`, `#targetBannerText`, `#kneeSwitch`, `.card-info-btn`, or `.btn-support-top`.
  - UI-to-Python bindings must go through `JsApi` in `ui/webview_window.py` and call `window.pywebview.api.<method>()`.

### 7. Releases & Documentation
* Version source of truth is `core/__init__.py`.
* Pushing a tag `v*` (e.g. `v2.6.2`) triggers GitHub Actions to run tests, build the standalone executable and installer, and publish the release.
* Release notes in `RELEASE_NOTES.md` must stay short, crisp, and focused exclusively on what changed, without repeating manuals or past release notes.

---

## File Directory Map
- `core/audio_engine.py` — WASAPI loopback capture, DSP soft-knee dynamics, Combat Guard, worker thread loop
- `core/footstep_boost.py` — Master endpoint booster, session compensator, crash recovery
- `core/volume_recovery.py` — Crash recovery ledger for game session and master levels
- `core/safe_io.py` — Atomic JSON writes shared by config and recovery files
- `ui/bridge_validation.py` — Input validation for every `JsApi` call
- `ui/telemetry_pump.py` — Non-blocking latest-value telemetry sender
- `ui/webview_hardening.py` — WebView2 navigation lock and feature lock-down
- `core/config_manager.py` — JSON config persistence, default settings, game presets
- `ui/webview_window.py` — pywebview host, Edge WebView2 integration, JS-to-Python bridge (`JsApi`)
- `ui/web/index.html` — Desktop UI layout, frameless titlebar, visualizer canvas, guide modal
- `ui/web/style.css` — Midnight Navy design system, responsive styles, animations
- `ui/web/app.js` — Frontend state, real-time Canvas VU visualizer, telemetry handler
- `build_exe.py` — PyInstaller onedir/onefile builder & Inno Setup 6 compiler
- `installer/AudioClamp.iss` — Inno Setup script for the Windows installer
- `tests/` — Automated test suite for DSP, Footstep Boost, Combat Guard, and spray simulations
- `RELEASE_NOTES.md` — Active release summary published to GitHub Releases
