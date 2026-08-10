"""Settings and per-user file storage (channels.txt, config.json)."""
import glob
import json
import os
import re
import sys
import shlex
from twtui.keymap import KEYBINDS


STREAMLINK = "streamlink"

QUALITY_CHOICES = ["best", "1080p60", "720p60", "720p", "480p", "worst"]

SETTINGS = {
    # General
    "kill_streams_on_exit": False,
    "kill_orphans_on_start": False,
    "kill_all_streams_on_start": False,
    "confirm_before_quit": False,
    # Streamlink
    "quality": "best",
    "low_latency": True,
    "hide_stream_console": False,
    "custom_flags": "",
    # Appearance
    "color_accent":       "magenta",
    "color_cursor":       "cyan",
    "color_live":         "green",
    "color_tab":          "yellow",
    "color_open":         "yellow",
    "color_highlight_bg": "grey19",
    # Lists
    "list_autorefresh_secs": 0,
    "search_results":        15,
    "category_rows":         100,
    "streams_per_category":  100,
    # Hotkeys
    "key_quit":     "q",
    "key_refresh":  "r",
    "key_follow":   "f",
    "key_search":   "/",
    "key_settings": "s",
    # System
    "run_on_startup": False,
}

COLOR_CHOICES = ["magenta","cyan","green","yellow","red","blue","white",
                 "bright_magenta","bright_cyan","bright_green","bright_blue",
                 "bright_red","orange1","purple"]
BG_CHOICES    = ["grey19","grey23","grey15","grey0","navy_blue","dark_red",
                 "deep_pink4","grey35"]

SETTINGS_SCHEMA = [
    ("General", [
        {"key": "kill_streams_on_exit",     "type": "bool",   "label": "Kill streams on exit",        "help": "close all open streams when you quit"},
        {"key": "kill_orphans_on_start",    "type": "bool",   "label": "Kill ended streams on start", "help": "on launch, close players whose stream already ended"},
        {"key": "kill_all_streams_on_start","type": "bool",   "label": "Kill all streams on start",   "help": "on launch, close every stream left from last session"},
        {"key": "confirm_before_quit",      "type": "bool",   "label": "Confirm before quit",         "help": "ask before quitting if streams are open"},
    ]),
    ("Streamlink", [
        {"key": "quality",             "type": "choice", "choices": QUALITY_CHOICES, "label": "Quality",            "help": "stream quality passed to streamlink"},
        {"key": "low_latency",         "type": "bool",   "label": "Low latency",        "help": "--twitch-low-latency (nearer live edge)"},
        {"key": "hide_stream_console", "type": "bool",   "label": "Hide streamlink console", "help": "run streams without a console window"},
        {"key": "custom_flags",        "type": "text",   "label": "Custom flags",       "help": "extra streamlink args, space-separated"},
    ]),
    ("Appearance", [
        {"key":"color_accent",      "type":"color","choices":COLOR_CHOICES,"label":"Accent",        "help":"panel borders + titles"},
        {"key":"color_cursor",      "type":"color","choices":COLOR_CHOICES,"label":"Cursor",        "help":"selection cursor + caret"},
        {"key":"color_live",        "type":"color","choices":COLOR_CHOICES,"label":"Live",          "help":"live dot + viewer counts"},
        {"key":"color_tab",         "type":"color","choices":COLOR_CHOICES,"label":"Tab highlight", "help":"active tab background"},
        {"key":"color_open",        "type":"color","choices":COLOR_CHOICES,"label":"Open marker",   "help":"▶ open + ★ followed"},
        {"key":"color_highlight_bg","type":"color","choices":BG_CHOICES,   "label":"Selected row",  "help":"highlighted row background"},
    ]),
    ("Lists", [
        {"key":"list_autorefresh_secs","type":"int","min":0,"max":600,"step":5,"unit":"s","label":"Auto-refresh","help":"re-check followed status every N sec (0 = off)"},
        {"key":"search_results",       "type":"int","min":5,"max":30, "step":5,"label":"Search results", "help":"max channel search rows (twitch caps ~10-15)"},
        {"key":"category_rows",        "type":"int","min":10,"max":100,"step":10,"label":"Category rows","help":"top games / category search rows"},
        {"key":"streams_per_category", "type":"int","min":10,"max":100,"step":10,"label":"Streams per category","help":"channels loaded when opening a category"},
    ]),
    ("Hotkeys", [
        {"key":"key_quit",    "type":"key","label":"Quit",     "help":"list-mode quit key"},
        {"key":"key_refresh", "type":"key","label":"Refresh",  "help":"re-check followed channels"},
        {"key":"key_follow",  "type":"key","label":"Follow",   "help":"follow/unfollow selected"},
        {"key":"key_search",  "type":"key","label":"Search",   "help":"open channel search"},
        {"key":"key_settings","type":"key","label":"Settings", "help":"open this screen"},
    ]),
    ("System", [
        {"key":"run_on_startup","type":"bool","label":"Run on startup","help":"launch twtui when Windows starts (Windows only)"},
    ]),
]

def build_stream_cmd(channel):
    args = [STREAMLINK, f"twitch.tv/{channel}", SETTINGS["quality"]]
    if SETTINGS["low_latency"]:
        args += ["--twitch-low-latency", "--hls-live-edge", "1"]
    extra = SETTINGS["custom_flags"].strip()
    if extra:
        try:
            args += shlex.split(extra)
        except ValueError:
            pass
    return args


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

def build_theme():
    return {
        "accent":       SETTINGS["color_accent"],
        "cursor":       SETTINGS["color_cursor"],
        "live":         SETTINGS["color_live"],
        "tab":          SETTINGS["color_tab"],
        "open":         SETTINGS["color_open"],
        "highlight_bg": SETTINGS["color_highlight_bg"],
    }

THEME = {}

def rebuild_theme():
    THEME.clear()
    THEME.update(build_theme())

def rebuild_keybinds():
    KEYBINDS["q"] = SETTINGS["key_quit"]
    KEYBINDS["r"] = SETTINGS["key_refresh"]
    KEYBINDS["f"] = SETTINGS["key_follow"]
    KEYBINDS["/"] = SETTINGS["key_search"]
    KEYBINDS["s"] = SETTINGS["key_settings"]

def load_config():
    try:
        data = json.load(open(CONFIG_FILE, encoding="utf-8"))
    except Exception:
        return
    for k in SETTINGS:
        if k in data:
            val = data[k]
            # Validate per type
            for sec_name, fields in SETTINGS_SCHEMA:
                for f in fields:
                    if f["key"] == k:
                        if f["type"] == "bool" and isinstance(val, bool):
                            SETTINGS[k] = val
                        elif f["type"] in ("choice", "color") and val in f.get("choices", []):
                            SETTINGS[k] = val
                        elif f["type"] == "text" and isinstance(val, str):
                            SETTINGS[k] = val
                        elif f["type"] == "int" and isinstance(val, int) and not isinstance(val, bool):
                            SETTINGS[k] = max(f["min"], min(f["max"], val))
                        elif f["type"] == "key" and isinstance(val, str) and len(val) == 1:
                            SETTINGS[k] = val
                        break
    rebuild_theme()
    rebuild_keybinds()

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, indent=2)
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            app_name = "TwitchTUI"
            if SETTINGS.get("run_on_startup"):
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    cmd = f'"{sys.executable}" -m twtui.app'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
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

rebuild_theme()
rebuild_keybinds()
