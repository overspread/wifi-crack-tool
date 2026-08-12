"""Compatibility launcher for the offline WiFi defense tool.

This program intentionally does not scan, connect to, authenticate with, or otherwise
interact with real WiFi networks.
"""

from wifi_defense.app import run


if __name__ == "__main__":
    run()
