"""Lets the app start with `python -m fontsleuth`."""

import sys

from fontsleuth.app import Application

if __name__ == "__main__":
    sys.exit(Application.run(sys.argv))
