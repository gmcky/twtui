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
    # Quick setup
    "preset": "Balanced",
    # General
    "kill_streams_on_exit": False,
    "kill_orphans_on_start": False,
    "kill_all_streams_on_start": False,
    "confirm_before_quit": False,
    # Streamlink (playback)
    "quality": "best",
    "low_latency": True,
    "hide_stream_console": False,
    "custom_flags": "",
    "twitch_codecs":   "h264",     # --twitch-supported-codecs
    "hls_live_edge":   3,          # --hls-live-edge (used only when low_latency off)
    "player_path":     "",         # --player PATH (empty = streamlink default)
    "player_args":     "",         # --player-args
    # Network (reliability / advanced)
    "retry_streams":   0,          # --retry-streams SECS (0 = off; wait for live)
    "retry_max":       0,          # --retry-max N (0 = unlimited when retrying)
    "retry_open":      1,          # --retry-open N
    "stream_timeout":  60,         # --stream-timeout SECS
    "ringbuffer_size": "16M",      # --ringbuffer-size
    "segment_threads": 1,          # --stream-segment-threads
    "http_proxy":      "",         # --http-proxy URL
    "ip_version":      "auto",     # auto | ipv4 | ipv6  -> --ipv4 / --ipv6
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

CODEC_CHOICES      = ["h264", "av1,h264", "h265,h264", "av1,h265,h264"]
RINGBUFFER_CHOICES = ["16M", "32M", "64M", "128M"]
IPVER_CHOICES      = ["auto", "ipv4", "ipv6"]

PRESET_CHOICES = ["Custom", "Balanced", "Low latency", "High quality",
                  "Data saver", "Unstable connection"]

# Keys a preset fully specifies. A preset is "active" when every one of these
# equals the preset's fingerprint; otherwise the preset is "Custom".
BUNDLE_KEYS = ["quality", "low_latency", "hls_live_edge", "twitch_codecs",
               "retry_streams", "retry_max", "retry_open", "stream_timeout",
               "ringbuffer_size", "segment_threads", "ip_version"]

PRESETS = {
    "Balanced": {
        "quality":"best", "low_latency":True, "hls_live_edge":3, "twitch_codecs":"h264",
        "retry_streams":0, "retry_max":0, "retry_open":1, "stream_timeout":60,
        "ringbuffer_size":"16M", "segment_threads":1, "ip_version":"auto",
    },
    "Low latency": {
        "quality":"best", "low_latency":True, "hls_live_edge":3, "twitch_codecs":"h264",
        "retry_streams":0, "retry_max":0, "retry_open":1, "stream_timeout":60,
        "ringbuffer_size":"16M", "segment_threads":2, "ip_version":"auto",
    },
    "High quality": {
        "quality":"best", "low_latency":False, "hls_live_edge":3, "twitch_codecs":"av1,h264",
        "retry_streams":0, "retry_max":0, "retry_open":1, "stream_timeout":60,
        "ringbuffer_size":"64M", "segment_threads":2, "ip_version":"auto",
    },
    "Data saver": {
        "quality":"480p", "low_latency":False, "hls_live_edge":3, "twitch_codecs":"h264",
        "retry_streams":0, "retry_max":0, "retry_open":1, "stream_timeout":60,
        "ringbuffer_size":"16M", "segment_threads":1, "ip_version":"auto",
    },
    "Unstable connection": {
        "quality":"720p", "low_latency":False, "hls_live_edge":3, "twitch_codecs":"h264",
        "retry_streams":5, "retry_max":0, "retry_open":3, "stream_timeout":180,
        "ringbuffer_size":"64M", "segment_threads":3, "ip_version":"auto",
    },
}

def apply_preset(name):
    """Overwrite the bundled settings with a named preset."""
    bundle = PRESETS.get(name)
    if not bundle:
        return
    SETTINGS.update(bundle)
    SETTINGS["preset"] = name


def detect_preset():
    """Return the preset name whose fingerprint matches current settings, else 'Custom'."""
    for name, bundle in PRESETS.items():
        if all(SETTINGS.get(k) == v for k, v in bundle.items()):
            return name
    return "Custom"


SETTINGS_SCHEMA = [
    ("Quick setup", [
        {"key":"preset", "type":"preset", "choices":PRESET_CHOICES,
         "label":"Preset", "help":"one-pick bundle; editing any streamlink setting = Custom"},
    ]),
    ("General", [
        {"key": "kill_streams_on_exit",     "type": "bool",   "label": "Kill streams on exit",        "help": "close all open streams when you quit"},
        {"key": "kill_orphans_on_start",    "type": "bool",   "label": "Kill ended streams on start", "help": "on launch, close players whose stream already ended"},
        {"key": "kill_all_streams_on_start","type": "bool",   "label": "Kill all streams on start",   "help": "on launch, close every stream left from last session"},
        {"key": "confirm_before_quit",      "type": "bool",   "label": "Confirm before quit",         "help": "ask before quitting if streams are open"},
    ]),
    ("Streamlink", [
        {"key":"quality",       "type":"choice","choices":QUALITY_CHOICES,"label":"Quality",       "help":"stream quality passed to streamlink"},
        {"key":"low_latency",   "type":"bool",  "label":"Low latency",    "help":"--twitch-low-latency (nearer live edge, manages edge itself)"},
        {"key":"twitch_codecs", "type":"choice","choices":CODEC_CHOICES,  "label":"Codecs",         "help":"--twitch-supported-codecs preference order"},
        {"key":"hls_live_edge", "type":"int","min":1,"max":6,"step":1,     "label":"Live edge",      "help":"segments behind live (ignored when low latency on)"},
        {"key":"player_path",   "type":"text",  "label":"Player path",    "help":"custom player exe (blank = streamlink default)"},
        {"key":"player_args",   "type":"text",  "label":"Player args",    "help":"extra args passed to the player"},
        {"key":"hide_stream_console","type":"bool","label":"Hide streamlink console","help":"run streams without a console window"},
        {"key":"custom_flags",  "type":"text",  "label":"Custom flags",   "help":"extra streamlink args, space-separated"},
    ]),
    ("Network", [
        {"key":"retry_streams",   "type":"int","min":0,"max":60, "step":1,"unit":"s","label":"Retry streams", "help":"wait+retry until channel is live (0 = off)"},
        {"key":"retry_max",       "type":"int","min":0,"max":20, "step":1,          "label":"Retry max",      "help":"max stream-fetch retries (0 = unlimited while retrying)"},
        {"key":"retry_open",      "type":"int","min":1,"max":10, "step":1,          "label":"Retry open",     "help":"attempts to open the stream"},
        {"key":"stream_timeout",  "type":"int","min":30,"max":300,"step":10,"unit":"s","label":"Stream timeout","help":"inactivity timeout before giving up"},
        {"key":"ringbuffer_size", "type":"choice","choices":RINGBUFFER_CHOICES,     "label":"Buffer size",    "help":"--ringbuffer-size (bigger = smoother, more RAM)"},
        {"key":"segment_threads", "type":"int","min":1,"max":10, "step":1,          "label":"Segment threads","help":"parallel segment downloads (faster on fast links)"},
        {"key":"http_proxy",      "type":"text","label":"HTTP proxy", "help":"--http-proxy URL (blank = none)"},
        {"key":"ip_version",      "type":"choice","choices":IPVER_CHOICES,          "label":"IP version",     "help":"force IPv4/IPv6 or auto"},
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
    s = SETTINGS
    args = [STREAMLINK, f"twitch.tv/{channel}", s["quality"]]

    # Latency: low_latency manages its own live edge; only pass a manual
    # --hls-live-edge when low_latency is OFF.
    if s["low_latency"]:
        args += ["--twitch-low-latency"]
    else:
        args += ["--hls-live-edge", str(s["hls_live_edge"])]

    # Codecs (only if not the plain default, to keep the cmd clean).
    if s["twitch_codecs"] and s["twitch_codecs"] != "h264":
        args += ["--twitch-supported-codecs", s["twitch_codecs"]]

    # Player.
    if s["player_path"].strip():
        args += ["--player", s["player_path"].strip()]
    if s["player_args"].strip():
        args += ["--player-args", s["player_args"].strip()]

    # Reliability. Each 0/default value means "omit the flag".
    if s["retry_streams"] > 0:
        args += ["--retry-streams", str(s["retry_streams"])]
        # retry_max only meaningful while retrying; 0 -> unlimited (omit flag).
        if s["retry_max"] > 0:
            args += ["--retry-max", str(s["retry_max"])]
    if s["retry_open"] != 1:
        args += ["--retry-open", str(s["retry_open"])]
    if s["stream_timeout"] != 60:
        args += ["--stream-timeout", str(s["stream_timeout"])]
    if s["ringbuffer_size"] != "16M":
        args += ["--ringbuffer-size", s["ringbuffer_size"]]
    if s["segment_threads"] > 1:
        args += ["--stream-segment-threads", str(s["segment_threads"])]

    # Network.
    if s["http_proxy"].strip():
        args += ["--http-proxy", s["http_proxy"].strip()]
    if s["ip_version"] == "ipv4":
        args += ["--ipv4"]
    elif s["ip_version"] == "ipv6":
        args += ["--ipv6"]

    # Custom flags LAST so a power user can override anything above.
    extra = s["custom_flags"].strip()
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
    SETTINGS["preset"] = detect_preset()
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
