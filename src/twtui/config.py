"""Settings and per-user file storage (channels.txt, config.json)."""
import glob
import json
import os
import re
import sys


STREAMLINK = "streamlink"
FLAGS = ["best", "--twitch-low-latency", "--hls-live-edge", "1"]

# Runtime settings, editable in the settings view and persisted to config.json.
SETTINGS = {
    "hide_stream_console": False,   # run streamlink with no console window
    "kill_streams_on_exit": False,  # terminate launched streams when client exits
}
# (key, label, help) in display order.
SETTINGS_META = [
    ("hide_stream_console", "Hide streamlink console", "run streams without a console window"),
    ("kill_streams_on_exit", "Kill streams on exit", "close all open streams when you quit"),
]


# App dir (frozen exe or source); used only to find a legacy channels.txt / *.bat.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

BAT_DIR = getattr(sys, "_MEIPASS", APP_DIR)

def _config_dir():
    # Per-user writable config dir (source / frozen exe / pipx install).
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "twitch-tui")
    os.makedirs(d, exist_ok=True)
    return d


# TWITCH_TUI_CHANNELS overrides the path (testing / multiple profiles).
CHANNELS_FILE = os.environ.get("TWITCH_TUI_CHANNELS") or os.path.join(_config_dir(), "channels.txt")

CHANNELS_HEADER = "# One Twitch channel per line. Blank lines and #comments ignored.\n"

CONFIG_FILE = os.path.join(_config_dir(), "config.json")
STREAMS_FILE = os.path.join(_config_dir(), "open_streams.json")


def load_config():
    try:
        data = json.load(open(CONFIG_FILE, encoding="utf-8"))
    except Exception:
        return
    for k in SETTINGS:
        if isinstance(data.get(k), bool):
            SETTINGS[k] = data[k]


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, indent=2)
    except Exception:
        pass


def _read_channels(path):
    chans = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            chans.append(line)
    return chans


def load_channels():
    if os.path.exists(CHANNELS_FILE):
        return _read_channels(CHANNELS_FILE)

    # First run: seed from a legacy channels.txt next to the app, else *.bat, else empty.
    legacy = os.path.join(APP_DIR, "channels.txt")
    if os.path.exists(legacy):
        channels = _read_channels(legacy)
    else:
        channels = []
        for path in sorted(glob.glob(os.path.join(BAT_DIR, "*.bat"))):
            if os.path.basename(path).lower() == "watch.bat":
                continue
            text = open(path, encoding="utf-8").read()
            m = re.search(r"twitch\.tv/(\S+)", text)
            if m:
                channels.append(m.group(1))
    save_channels(channels)   # create the user file so follow/unfollow persist
    return channels


def save_channels(channels):
    os.makedirs(os.path.dirname(CHANNELS_FILE) or ".", exist_ok=True)
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        f.write(CHANNELS_HEADER)
        for c in channels:
            f.write(c + "\n")
