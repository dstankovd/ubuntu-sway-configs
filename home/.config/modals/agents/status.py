#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

COLLECTOR = "/home/dimitar/.config/modals/agents/codex-usage-collector"
STATE = Path("/home/dimitar/.local/state/sway/agents/codex.json")


def refresh():
    result = subprocess.run([COLLECTOR, "--limits-only"], capture_output=True,
                            text=True, timeout=25)
    if result.returncode or not result.stdout.strip():
        return
    record = json.loads(result.stdout)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(dir=STATE.parent, prefix=".codex-", text=True)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(record, handle)
        os.replace(path, STATE)
    finally:
        if os.path.exists(path): os.unlink(path)


try:
    if not STATE.exists() or time.time() - STATE.stat().st_mtime > 900:
        refresh()
    record = json.loads(STATE.read_text())
    limits = record.get("limits") or []
    primary = round(float(limits[0].get("percent", 0)) * 100) if limits else 0
    weekly = round(float(limits[1].get("percent", 0)) * 100) if len(limits) > 1 else None
    tooltip = f"Codex · {record.get('tierLabel', '').title()}\n5h usage: {primary}%"
    if weekly is not None: tooltip += f"\nWeekly usage: {weekly}%"
    tooltip += f"\nToday: {record.get('todayPrompts', 0)} prompts"
    css = "critical" if primary >= 90 else "warning" if primary >= 70 else "normal"
    output = {"text": "󰚩", "tooltip": tooltip, "class": css,
              "percentage": primary}
except Exception:
    output = {"text": "󰚩", "tooltip": "Codex usage unavailable", "class": "unavailable"}

print(json.dumps(output))
