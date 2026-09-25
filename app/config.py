from pathlib import Path
import os

HOME = Path(os.environ.get("HOME", "/home/deb"))
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "airplay-control"
STATE_DIR.mkdir(parents=True, exist_ok=True)

UXPLAY_BIN = os.environ.get("UXPLAY_BIN", "/usr/bin/uxplay")
WAYLAND_DISPLAY = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
WAYLAND_SOCKET = RUNTIME_DIR / WAYLAND_DISPLAY

UXPLAY_LOG = STATE_DIR / "uxplay.log"
PROCESS_STATE = RUNTIME_DIR / "airplay-control-uxplay.json"

BASE_ENV = os.environ.copy()
BASE_ENV.update(
    {
        "HOME": str(HOME),
        "XDG_RUNTIME_DIR": str(RUNTIME_DIR),
        "WAYLAND_DISPLAY": WAYLAND_DISPLAY,
        "ALSOFT_DRIVERS": "alsa",
    }
)

# Normal mirroring profile: hardware H.264 decode + Wayland output.
AV_ARGS = [
    "-v4l2",
    "-bt709",
    "-vs", "waylandsink",
    "-vsync", "no",
]

# AirPlay Audio profile. `-vs 0` suppresses mirrored video while `-ca`
# asks UxPlay to render album art when the client is using AirPlay Audio.
# `-async` gives best-quality AirPlay Audio at the cost of added latency.
AUDIO_ARGS = [
    "-vs", "0",
    "-ca",
    "-async",
]
