"""Stream lifecycle management."""

import atexit
import ctypes
import json
import os
import signal
import subprocess
import sys
import threading
import time

import psutil

from twtui.config import SETTINGS, STREAMS_FILE, build_stream_cmd

_open_streams = []
_lock = threading.Lock()
_handler_routine = None


def _write_state(state):
    try:
        temp = STREAMS_FILE + ".tmp"
        os.makedirs(os.path.dirname(STREAMS_FILE) or ".", exist_ok=True)
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(temp, STREAMS_FILE)
    except Exception:
        pass


LAUNCH_GRACE = 2.5


def stream_alive(entry):
    if not entry:
        return False
    try:
        p = psutil.Process(entry["slink_pid"])
        return p.create_time() == entry["slink_create"]
    except psutil.Error:
        return False


def _record_path_of(cmd):
    # Pull the --record target back out of the built command, if any.
    try:
        return cmd[cmd.index("--record") + 1]
    except (ValueError, IndexError):
        return None


def launch(channel):
    cmd = build_stream_cmd(channel)
    hide = SETTINGS["hide_stream_console"]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW if hide else subprocess.CREATE_NEW_CONSOLE
        )
    else:
        kwargs["start_new_session"] = True
        if hide:
            kwargs["stdout"] = kwargs["stderr"] = subprocess.DEVNULL

    try:
        p = subprocess.Popen(cmd, **kwargs)
        proc = psutil.Process(p.pid)
        entry = {
            "slink_pid": p.pid,
            "slink_create": proc.create_time(),
            "player_pid": None,
            "player_create": None,
            "player_name": None,
            "channel": channel,
            "record_path": _record_path_of(cmd),
            "started": time.time(),
        }
        with _lock:
            _open_streams.append(entry)
        sync_state()
        return entry
    except Exception:
        return None


def sync_state():
    with _lock:
        to_keep = []
        for entry in _open_streams:
            slink_alive = False
            try:
                proc = psutil.Process(entry["slink_pid"])
                if proc.create_time() == entry["slink_create"]:
                    slink_alive = True
                    if entry["player_pid"] is None:
                        children = proc.children(recursive=False)
                        if children:
                            child = children[0]
                            entry["player_pid"] = child.pid
                            entry["player_create"] = child.create_time()
                            entry["player_name"] = child.name()
            except psutil.Error:
                pass

            player_alive = False
            if entry["player_pid"] is not None:
                try:
                    player_proc = psutil.Process(entry["player_pid"])
                    if player_proc.create_time() == entry["player_create"]:
                        player_alive = True
                except psutil.Error:
                    pass

            if slink_alive or player_alive:
                to_keep.append(entry)

        _open_streams.clear()
        _open_streams.extend(to_keep)

        if not to_keep:
            try:
                if os.path.exists(STREAMS_FILE):
                    os.remove(STREAMS_FILE)
            except Exception:
                pass
        else:
            _write_state(to_keep)


def live_channels():
    # Channels backed by a still-running process. Reflects reality after the
    # last sync_state(), so a manually-closed player drops out on its own.
    with _lock:
        return {entry["channel"] for entry in _open_streams}


def kill_tree(pid, create_time):
    try:
        proc = psutil.Process(pid)
        if proc.create_time() != create_time:
            return

        children = proc.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.Error:
                pass
        try:
            proc.terminate()
        except psutil.Error:
            pass

        gone, alive = psutil.wait_procs(children + [proc], timeout=2.0)
        for p in alive:
            try:
                p.kill()
            except psutil.Error:
                pass
    except psutil.Error:
        pass


def kill_streams():
    if not SETTINGS["kill_streams_on_exit"]:
        return
    with _lock:
        if not _open_streams:
            return
        for entry in _open_streams:
            kill_tree(entry["slink_pid"], entry["slink_create"])
        _open_streams.clear()
        try:
            if os.path.exists(STREAMS_FILE):
                os.remove(STREAMS_FILE)
        except Exception:
            pass


def cleanup_on_start():
    try:
        if not os.path.exists(STREAMS_FILE):
            return set()
        with open(STREAMS_FILE, "r", encoding="utf-8") as f:
            prev = json.load(f)
        if not isinstance(prev, list):
            prev = []
    except Exception:
        prev = []

    kill_all = SETTINGS.get("kill_all_streams_on_start", False)
    kill_orphans = SETTINGS.get("kill_orphans_on_start", False)

    survivors = []
    for entry in prev:
        slink_pid = entry.get("slink_pid")
        slink_create = entry.get("slink_create")
        player_pid = entry.get("player_pid")
        player_create = entry.get("player_create")

        slink_alive = False
        if slink_pid is not None:
            try:
                proc = psutil.Process(slink_pid)
                if proc.create_time() == slink_create:
                    slink_alive = True
            except psutil.Error:
                pass

        player_alive = False
        if player_pid is not None:
            try:
                proc = psutil.Process(player_pid)
                if proc.create_time() == player_create:
                    player_alive = True
            except psutil.Error:
                pass

        if kill_all:
            if slink_pid is not None:
                kill_tree(slink_pid, slink_create)
            if player_pid is not None:
                try:
                    p = psutil.Process(player_pid)
                    if p.create_time() == player_create:
                        kill_tree(player_pid, player_create)
                except psutil.Error:
                    pass
            continue
        if kill_orphans and (not slink_alive) and player_alive:
            if player_pid is not None:
                kill_tree(player_pid, player_create)
            continue
        # Still running from a previous session: keep tracking it so the list
        # shows it as open on startup and sync_state() reaps it when it dies.
        if slink_alive or player_alive:
            survivors.append(entry)

    with _lock:
        _open_streams.clear()
        _open_streams.extend(survivors)

    if survivors:
        _write_state(survivors)
    else:
        try:
            if os.path.exists(STREAMS_FILE):
                os.remove(STREAMS_FILE)
        except Exception:
            pass

    return {e["channel"] for e in survivors}


def open_recording(channel):
    """Open the growing recording of a live channel in a second player, giving a
    seekable DVR view. Returns True if a player was spawned."""
    with _lock:
        entry = next(
            (e for e in _open_streams if e["channel"] == channel and e.get("record_path")),
            None,
        )
    if not entry:
        return False
    path = entry["record_path"]
    if not path or not os.path.exists(path):
        return False
    player = SETTINGS.get("player_path", "").strip()
    try:
        if player:
            subprocess.Popen([player, path])
        elif sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def install_exit_handlers():
    atexit.register(kill_streams)

    def sig_handler(signum, frame):
        kill_streams()
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, sig_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGINT, sig_handler)
    except Exception:
        pass

    if sys.platform == "win32":
        global _handler_routine
        WINFUNCTYPE = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

        def handler(event):
            if event in (2, 5, 6):
                kill_streams()
                return False
            return False

        _handler_routine = WINFUNCTYPE(handler)
        try:
            ctypes.windll.kernel32.SetConsoleCtrlHandler(_handler_routine, True)
        except Exception:
            pass
