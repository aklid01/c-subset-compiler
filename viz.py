"""
Visualizer Entrypoint.
Initializes the visualizer session and launches the Textual TUI.
"""

from __future__ import annotations

import io
import os
import sys

from app.session import VizSession
from app.tui import VisualizerApp


def main():
    # Force UTF-8 mode on Windows consoles to support the Greek symbol 'ε'
    if sys.platform.startswith("win"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    input_file = "input/input.txt"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        source = f.read()

    session = VizSession(source)
    app = VisualizerApp(session)
    app.run()


if __name__ == "__main__":
    main()
