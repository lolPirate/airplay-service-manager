from pathlib import Path
import os

HOME = Path(os.environ.get("HOME", "/home/deb"))
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "airplay-control"
STATE_DIR.mkdir(parents=True, exist_ok=True)

UXPLAY_NAME = "RaspiAirPlayServer"
UXPLAY_BIN = os.environ.get("UXPLAY_BIN", "/usr/bin/uxplay")
WAYLAND_DISPLAY = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
WAYLAND_SOCKET = RUNTIME_DIR / WAYLAND_DISPLAY
WLR_RANDR_BIN = os.environ.get("WLR_RANDR_BIN", "/usr/bin/wlr-randr")
# Leave unset to select the only enabled display automatically.
DISPLAY_OUTPUT = os.environ.get("DISPLAY_OUTPUT", "")

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

DISPLAY_MODES = {
    "landscape": "normal",
    "portrait-right": "90",
    "portrait-left": "270",
    "landscape-flipped": "180",
}

# Normal mirroring profile: hardware H.264 decode + Wayland output.
AV_ARGS = [
    "-n", UXPLAY_NAME,
    "-nh",
    "-s", "1920x1080",
    "-v4l2",
    "-bt709",
    "-vs", "waylandsink",
    "-vsync", "no",
]

# AirPlay Audio profile. `-vs 0` suppresses mirrored video while `-ca`
# asks UxPlay to render album art when the client is using AirPlay Audio.
# `-async` gives best-quality AirPlay Audio at the cost of added latency.
AUDIO_ARGS = [
    "-n", UXPLAY_NAME,
    "-nh",
    "-vs", "0",
    "-ca"
]
