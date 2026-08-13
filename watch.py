#!/usr/bin/env python3
"""Entry shim so the app runs from a clone without installing (src layout)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from twtui.app import main

if __name__ == "__main__":
    main()
