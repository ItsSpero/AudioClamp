# AudioClamp v2.6.2 — Streamlined UI, Decluttered Controls & Windows Audio Optimization Guide

AudioClamp v2.6.2 introduces a major visual polish and decluttering pass across the entire desktop interface, decouples the titlebar device controls, and adds comprehensive in-app guidance for optimizing Windows audio to prevent sound breaking in games.

---

### What's New & Changed in v2.6.2

#### 1. Streamlined Titlebar & Clean Header
- **Clean Brand Lockup**: Redesigned `AUDIOCLAMP` logo lockup with refined typography and a subtle cyan `v2.6.2` version pill.
- **Dedicated Device Selector**: De-congested the compound status pill into a standalone **Playback Device Quick-Switcher** (`🔊 Realtek Audio ▾`) that opens the native Windows 11 endpoint menu on click.
- **Real-Time Latency Badge**: Added an isolated **Engine Status Tag** (`🟢 Pro Audio · 0.04ms`) with hover tooltips for MMCSS thread telemetry.
- **Refined Action Controls**: Balanced sizing and borders for `Mini`, `Guide`, `Eco`, and `Support` buttons.

#### 2. Clean & Decluttered Interface (Midnight Navy & Ice Blue)
- **Unified Palette**: Replaced competing neon colors (bright cyan, glowing lime green, harsh crimson, and amber) with a calm **Midnight Navy (`#0B111E` / `#111A2E`)** base and a single **Ice Blue (`#38BDF8`)** accent. Rose/Coral is now strictly reserved for active gain reduction and emergency limit indicators.
- **Removed 12 Inline `(?)` Circles**: Eliminated the intrusive circular question mark buttons that previously cluttered every card heading and option row.
- **Modernized VU Visualizer**: Replaced the harsh red and green meter bars with calm Ice Blue audio curves, clean telemetry readouts (`IN`, `GR`, `OUT`), and a crisp limit threshold line.
- **Streamlined Sliders & Controls**: Both Loudness Ceiling and Footstep Recovery sliders now feature smooth Ice Blue controls with high-contrast numerical badges.
- **Two-Column Card Alignment**: Restructured the **Dynamics Mode** and **Footstep Recovery** cards for clean symmetry.
- **Mini-Pill Controls**: Formatted **Combat Guard** (`Off`, `-4 dB`, `-8 dB`) and **Footstep Boost** (`Off`, `+3 dB`, `+6 dB`, `+9 dB`) into sleek segmented controls.
- **Low-Profile Preset Strip**: Compact, refined preset cards with clean slate borders (`border-slate-800`) and subtle active states.
- **Refined Panic Reset**: Replaced the blinding hazard red button with a subtle, modern coral outline button.

#### 3. New Windows Audio Optimization Guide
- Added a dedicated **Windows Audio** category in the in-app **📖 Guide** (`#guide-windows-audio`).
- Details the critical Windows settings to prevent audio ducking, distortion, and muffled footsteps:
  1. **Uncheck "Enable audio enhancements"**: How to disable hidden Windows/Realtek APO volume normalization and ducking in `mmsys.cpl` &rarr; Advanced &rarr; Signal Enhancements.
  2. **Set Format to 24-bit, 48000 Hz**: Avoids real-time upsampling latency by matching the native render rate of PUBG, CS2, Tarkov, and Unreal/Source engines.
  3. **Turn Off Spatial Sound & Loudness Equalization**: Keeps directional cues and distance perception 100% accurate without volume pumping.

#### 4. Packaging & Startup Performance
- Updated PyInstaller and Inno Setup build hooks for clean directory builds.
- Installer installs an unpacked build to `%LOCALAPPDATA%\Programs\AudioClamp` for sub-second launch times without extracting 32 MB to a temp folder on every run.

---

### Installation & Download

- **Fast-Boot Installer (Recommended)**: Download and run `AudioClamp-Setup-2.6.2.exe`. Installs or upgrades cleanly with desktop/start menu shortcuts.
- **Portable Version**: Download `AudioClamp.exe` and run anywhere with no installation required.
