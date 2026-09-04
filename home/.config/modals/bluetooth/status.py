#!/usr/bin/env python3
import json
import subprocess

def bt(*args, timeout=4):
    return subprocess.run(["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout)

try:
    shown = bt("show")
    powered = "Powered: yes" in shown.stdout
    connected = []
    if powered:
        for line in bt("devices", "Connected").stdout.splitlines():
            parts = line.split(maxsplit=2)
            if len(parts) == 3: connected.append(parts[2])
    if connected:
        output = {"text": "󰂱", "tooltip": "Bluetooth\nConnected: " + ", ".join(connected), "class": "connected"}
    elif powered:
        output = {"text": "󰂯", "tooltip": "Bluetooth on\nNo connected devices", "class": "on"}
    else:
        output = {"text": "󰂲", "tooltip": "Bluetooth off", "class": "off"}
except Exception:
    output = {"text": "󰂲", "tooltip": "Bluetooth unavailable", "class": "unavailable"}
print(json.dumps(output))
