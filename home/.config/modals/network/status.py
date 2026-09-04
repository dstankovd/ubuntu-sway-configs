#!/usr/bin/env python3
import json
import subprocess


def run(*args):
    return subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=6)


try:
    devices = run("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status")
    if devices.returncode:
        raise RuntimeError
    active = None
    for line in devices.stdout.splitlines():
        fields = line.split(":", 3)
        if len(fields) == 4 and fields[2] == "connected" and fields[1] in ("wifi", "ethernet"):
            active = fields
            if fields[1] == "wifi": break
    connectivity = run("-t", "networking", "connectivity").stdout.strip()
    if not active:
        output = {"text": "󰤭", "tooltip": "Network disconnected", "class": "disconnected"}
    else:
        device, kind, _, name = active
        if kind == "wifi":
            icon = "󰤨" if connectivity == "full" else "󰤯"
            tooltip = f"{name}\nWi-Fi"
        else:
            icon, tooltip = "󰈀", f"{name}\nEthernet"
        labels = {"full": "Internet connected", "limited": "Limited connectivity",
                  "portal": "Sign-in required", "none": "No internet"}
        tooltip += "\n" + labels.get(connectivity, connectivity)
        output = {"text": icon, "tooltip": tooltip,
                  "class": "connected" if connectivity == "full" else "limited"}
except (OSError, subprocess.TimeoutExpired, RuntimeError):
    output = {"text": "󰤭", "tooltip": "NetworkManager unavailable", "class": "unavailable"}

print(json.dumps(output))
