"""Key tables and layout-agnostic resolution.

Single source for turning a raw keystroke into a hotkey action. Any ЙЦУКЕН
key folds to the latin key in the same physical position (fold()), so hotkeys
work under a Cyrillic layout without every call site re-implementing it. Add a
hotkey once and it is layout-agnostic everywhere.
"""

# List-mode single-key hotkeys (action -> bound key char). rebuild_keybinds()
# in config overwrites the bound chars from user settings.
KEYBINDS = {"q": "q", "r": "r", "f": "f", "/": "/", "s": "s"}

# ЙЦУКЕН -> QWERTY by physical position. Only Cyrillic needs folding; a latin
# layout already matches by character.
FOLD = {
    "й": "q",
    "ц": "w",
    "у": "e",
    "к": "r",
    "е": "t",
    "н": "y",
    "г": "u",
    "ш": "i",
    "щ": "o",
    "з": "p",
    "х": "[",
    "ъ": "]",
    "ф": "a",
    "ы": "s",
    "в": "d",
    "а": "f",
    "п": "g",
    "р": "h",
    "о": "j",
    "л": "k",
    "д": "l",
    "ж": ";",
    "э": "'",
    "я": "z",
    "ч": "x",
    "с": "c",
    "м": "v",
    "и": "b",
    "т": "n",
    "ь": "m",
    "б": ",",
    "ю": ".",
    "ё": "`",
}

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


def fold(ch):
    """Latin key in the same physical position as ch, lowercased. Returns None
    for special tokens, empty, or anything not a single character."""
    if not ch or len(ch) != 1:
        return None
    low = ch.lower()
    return FOLD.get(low, low)


def action_of(ch):
    """List-mode hotkey action bound to the physical key ch, or None."""
    key = fold(ch)
    if key is None:
        return None
    for action, bound in KEYBINDS.items():
        if bound == key:
            return action
    return None
