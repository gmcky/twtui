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

from twtui.config import SETTINGS, STREAMLINK, FLAGS, STREAMS_FILE

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

def launch(channel):
    cmd = [STREAMLINK, f"twitch.tv/{channel}", *FLAGS]
    hide = SETTINGS["hide_stream_console"]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW if hide else subprocess.CREATE_NEW_CONSOLE
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
            "started": time.time(),
        }
        with _lock:
            _open_streams.append(entry)
        sync_state()
    except Exception:
        pass

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
