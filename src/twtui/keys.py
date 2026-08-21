"""Cross-platform terminal key input.

read_key() returns a normalised token: one of the SPECIAL names, a single
printable character, or None to ignore. term_setup()/term_restore() put the
POSIX terminal into cbreak mode around the loop (no-ops on Windows).
"""

import os
import sys

from twtui.keymap import CTRL, POSIX_SEQ, WIN_ARROW


def _norm(ch):
    if ch in CTRL:
        return CTRL[ch]
    return ch if ch.isprintable() else None


if sys.platform == "win32":
    import msvcrt

    def term_setup():
        return None

    def term_restore(_state):
        pass

    def read_key():
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return WIN_ARROW.get(msvcrt.getwch())
        return _norm(ch)
else:
    import select
    import termios
    import tty

    def term_setup():
        fd = sys.stdin.fileno()
        state = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return state

    def term_restore(state):
        if state is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, state)

    def read_key():
        fd = sys.stdin.fileno()
        b = os.read(fd, 1)
        if b == b"\x1b":
            # ESC alone vs an escape sequence: brief peek for the continuation.
            r, _, _ = select.select([fd], [], [], 0.03)
            if not r:
                return "ESC"
            seq = os.read(fd, 2).decode("latin-1", "ignore")
            return POSIX_SEQ.get(seq)
        o = b[0]
        if o < 0x80:
            return _norm(chr(o))
        # utf-8 lead byte: read the continuation bytes and decode.
        n = 2 if o < 0xE0 else 3 if o < 0xF0 else 4
        try:
            return _norm((b + os.read(fd, n - 1)).decode("utf-8"))
        except Exception:
            return None
