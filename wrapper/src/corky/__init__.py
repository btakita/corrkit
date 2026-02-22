"""Thin wrapper that exec's the corky Rust binary."""

import os
import shutil
import sys


def main():
    binary = shutil.which("corky")
    # Avoid infinite recursion: skip ourselves
    this_script = os.path.abspath(sys.argv[0])
    if binary and os.path.abspath(binary) == this_script:
        binary = None
    if binary is None:
        print(
            "corky binary not found. Install it with:\n"
            "  curl -sSf https://raw.githubusercontent.com/btakita/corky/main/install.sh | sh\n",
            file=sys.stderr,
        )
        sys.exit(1)
    os.execvp(binary, [binary] + sys.argv[1:])
