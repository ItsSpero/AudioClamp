# AudioClamp v2.6.3

A reliability, security and layout release.

### What's New
* **Crash-Safe Volumes**: If AudioClamp is closed from Task Manager or crashes mid-clamp, the next start puts game and master volumes back where you had them. Games that are closed at the time are restored when they next launch.
* **Smoother Limiting**: Removed a ~28 ms stall that hit the limiter once a second, and the limiter no longer waits on the window to redraw.
* **Device Switching**: Changing your output device while Master PC mode is clamping now hands the old device back at your level.
* **Hardened Window**: The app window only shows AudioClamp's own page, ignores dropped files, and loads no online resources. Fonts are now built in.
* **Cleaner Layout**: Eco, Mini, Guide and Support moved to the bottom bar; hotkeys now live in a Global Hotkeys card in the Guide. Removed the shortcut pills under the sliders and the last off-palette colors.
* **Compact HUD**: Shorter, with a single Ice Blue output meter.

---
### Downloads
* **`AudioClamp-Setup-2.6.3.exe`** — Fast-boot Windows installer (Recommended)
* **`AudioClamp.exe`** — Standalone portable executable
