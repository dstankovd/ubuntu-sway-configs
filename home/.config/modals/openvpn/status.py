#!/usr/bin/env python3
import json
import subprocess


def split_escaped(line):
    fields, field, escaped = [], "", False
    for char in line:
        if escaped:
            field += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append(field)
            field = ""
        else:
            field += char
    fields.append(field)
    return fields


try:
    result = subprocess.run(
        ["nmcli", "-t", "--escape", "yes", "-f", "NAME,TYPE,DEVICE,STATE",
         "connection", "show"],
        capture_output=True, text=True, timeout=4,
    )
    if result.returncode:
        raise RuntimeError

    profiles = []
    for line in result.stdout.splitlines():
        fields = split_escaped(line)
        if len(fields) >= 4 and fields[1] == "vpn":
            profiles.append({"name": fields[0], "device": fields[2], "state": fields[3]})

    active = next((p for p in profiles if p["state"] == "activated"), None)
    connecting = next((p for p in profiles if p["state"] == "activating"), None)
    if active:
        tooltip = f"OpenVPN: {active['name']}\nConnected"
        if active["device"]:
            tooltip += f" via {active['device']}"
        output = {"text": "󰖂", "tooltip": tooltip, "class": "connected"}
    elif connecting:
        output = {"text": "󰖂", "tooltip": f"OpenVPN: {connecting['name']}\nConnecting…", "class": "connecting"}
    elif profiles:
        output = {"text": "󰖂", "tooltip": f"OpenVPN disconnected\n{len(profiles)} profile(s) available", "class": "disconnected"}
    else:
        output = {"text": "󰖂", "tooltip": "OpenVPN disconnected\nNo profiles imported", "class": "disconnected"}
except (OSError, subprocess.TimeoutExpired, RuntimeError):
    output = {"text": "󰖂", "tooltip": "NetworkManager unavailable", "class": "unavailable"}

print(json.dumps(output))
