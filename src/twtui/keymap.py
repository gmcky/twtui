"""Key mapping tables: hotkeys, layout folding, token normalisation."""

# List-mode single-key hotkeys.
KEYBINDS = {"q": "q", "r": "r", "f": "f", "/": "/", "s": "s"}

# Cyrillic characters that sit under the latin hotkey keys -> that hotkey.
# Latin layouts already match by character, so only Cyrillic needs folding.
FOLD = {"й": "q", "к": "r", "а": "f", "ы": "s"}

# Normalised special-key tokens returned by read_key().
SPECIAL = {
    "UP",
    "DOWN",
    "LEFT",
    "RIGHT",
    "ENTER",
    "ESC",
    "BACKSPACE",
    "TAB",
    "CTRL_F",
    "CTRL_V",
    "CTRL_Q",
}

# Raw control characters -> tokens.
CTRL = {
    "\r": "ENTER",
    "\n": "ENTER",
    "\x1b": "ESC",
    "\x7f": "BACKSPACE",
    "\x08": "BACKSPACE",
    "\t": "TAB",
    "\x06": "CTRL_F",
    "\x16": "CTRL_V",
    "\x11": "CTRL_Q",
}

# Windows getwch arrow codes -> tokens.
WIN_ARROW = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}

# POSIX escape-sequence tails -> tokens.
POSIX_SEQ = {
    "[A": "UP",
    "[B": "DOWN",
    "[C": "RIGHT",
    "[D": "LEFT",
    "OA": "UP",
    "OB": "DOWN",
    "OC": "RIGHT",
    "OD": "LEFT",
}
