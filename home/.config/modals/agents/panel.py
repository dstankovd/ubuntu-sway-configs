#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

COLLECTOR = "/home/dimitar/.config/modals/agents/codex-usage-collector"
STATE = Path("/home/dimitar/.local/state/sway/agents/codex.json")


def compact(value):
    value = int(value or 0)
    if value >= 1_000_000: return f"{value / 1_000_000:.1f}M"
    if value >= 1_000: return f"{value / 1_000:.1f}K"
    return str(value)


def reset_text(value):
    if not value: return "reset unknown"
    try:
        target = datetime.fromisoformat(value).astimezone()
        seconds = max(0, int((target - datetime.now().astimezone()).total_seconds()))
        if seconds < 3600: relative = f"{max(1, seconds // 60)}m"
        elif seconds < 86400: relative = f"{seconds // 3600}h {seconds % 3600 // 60}m"
        else: relative = f"{seconds // 86400}d {seconds % 86400 // 3600}h"
        return f"resets in {relative} · {target:%a %H:%M}"
    except Exception: return "reset unknown"


class AgentsPanel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.sway.AgentsPanel")
        self.window = None
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True
        self.refreshing = False

    def do_activate(self):
        if self.window:
            self.window.present(); self.refresh(False); return
        self.hold()
        self.window = Gtk.ApplicationWindow(application=self, title="Agent usage",
            default_width=480, default_height=500, resizable=False)
        self.window.connect("close-request", self.hide)
        self.install_css()
        keys = Gtk.EventControllerKey(); keys.connect("key-pressed", self.on_key)
        self.window.add_controller(keys)
        if self.daemon_start and self.first_activation:
            self.first_activation = False; self.window.set_visible(False)
        else: self.window.present()
        self.render_cached(); self.refresh(False)

    def install_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(Path("/home/dimitar/.config/modals/theme.css").read_bytes() + b"""
          window { background: @modal_bg; color: @modal_fg_bright; }
          * { font-family: "JetBrainsMono Nerd Font"; }
          .title { font-size: 16px; font-weight: bold; }
          .subtitle, .caption { font-size: 10px; color: @modal_fg_dim; }
          .section { font-size: 11px; font-weight: bold; color: @modal_fg_dim; }
          .metric { font-size: 12px; }
          .value { font-size: 14px; font-weight: bold; }
          .error { font-size: 11px; color: @modal_error; }
          progressbar trough { min-height: 7px; background: @modal_hover; border-radius: 0; }
          progressbar progress { min-height: 7px; background: @modal_focus; border-radius: 0; }
          button { border-radius: 0; padding: 6px 10px; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def hide(self, *_): self.window.set_visible(False); return True

    def render_cached(self):
        try: self.render(json.loads(STATE.read_text()))
        except Exception: self.render(None)

    def set_content(self, root):
        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(root)
        self.window.set_child(scroller)

    def render(self, record):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
        root.set_margin_top(16); root.set_margin_bottom(14); root.set_margin_start(18); root.set_margin_end(18)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        mark = Gtk.Label(label="󰚩"); mark.set_css_classes(["title"])
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        title = Gtk.Label(label="Codex", xalign=0); title.set_css_classes(["title"])
        plan = Gtk.Label(label=(record.get("tierLabel", "") if record else "").upper() or "USAGE", xalign=0)
        plan.set_css_classes(["subtitle"]); names.append(title); names.append(plan)
        refresh = Gtk.Button(label="  Refresh"); refresh.connect("clicked", lambda *_: self.refresh(True))
        head.append(mark); head.append(names); head.append(refresh); root.append(head); root.append(Gtk.Separator())
        if not record:
            error = Gtk.Label(label="Usage data is not available yet.", xalign=0); error.set_css_classes(["error"])
            root.append(error); self.set_content(root); return
        if record.get("usageStatusText"):
            error = Gtk.Label(label=record["usageStatusText"], xalign=0); error.set_css_classes(["error"]); root.append(error)
        section = Gtk.Label(label="LIMITS", xalign=0); section.set_css_classes(["section"]); root.append(section)
        limits = record.get("limits") or []
        if not limits:
            root.append(Gtk.Label(label="No rate-limit data returned", xalign=0))
        for limit in limits:
            used = max(0.0, min(1.0, float(limit.get("percent", 0))))
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            label = Gtk.Label(label=limit.get("label", "Limit"), xalign=0, hexpand=True); label.set_css_classes(["metric"])
            percent = Gtk.Label(label=f"{round(used * 100)}% used"); percent.set_css_classes(["metric"])
            line.append(label); line.append(percent); root.append(line)
            bar = Gtk.ProgressBar(fraction=used); root.append(bar)
            reset = Gtk.Label(label=reset_text(limit.get("resetsAt")), xalign=0); reset.set_css_classes(["caption"]); root.append(reset)
        root.append(Gtk.Separator())
        section = Gtk.Label(label="TODAY", xalign=0); section.set_css_classes(["section"]); root.append(section)
        stats = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True)
        for label, value in (("TOKENS", compact(record.get("todayTotalTokens"))),
                             ("PROMPTS", record.get("todayPrompts", 0)),
                             ("SESSIONS", record.get("todaySessions", 0))):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            number = Gtk.Label(label=str(value), xalign=0); number.set_css_classes(["value"])
            name = Gtk.Label(label=label, xalign=0); name.set_css_classes(["caption"])
            box.append(number); box.append(name); stats.append(box)
        root.append(stats); root.append(Gtk.Separator())
        section = Gtk.Label(label="LAST 7 DAYS", xalign=0); section.set_css_classes(["section"]); root.append(section)
        days = record.get("recentDays") or []
        maximum = max([int(day.get("messageCount", 0)) for day in days] or [1]) or 1
        for day in days:
            count = int(day.get("messageCount", 0)); line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            try: label = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%a")
            except Exception: label = day.get("date", "")
            name = Gtk.Label(label=label, xalign=0, width_chars=3); name.set_css_classes(["caption"])
            bar = Gtk.ProgressBar(fraction=count / maximum, hexpand=True)
            value = Gtk.Label(label=compact(count), xalign=1, width_chars=7); value.set_css_classes(["caption"])
            line.append(name); line.append(bar); line.append(value); root.append(line)
        hint = Gtk.Label(label="R / Enter refresh · Esc close", xalign=0); hint.set_css_classes(["caption"]); root.append(hint)
        self.set_content(root)

    def refresh(self, force):
        if self.refreshing: return
        self.refreshing = True
        def work():
            args = [COLLECTOR, "--force" if force else "--limits-only"]
            try:
                result = subprocess.run(args, capture_output=True, text=True, timeout=35)
                if result.returncode: raise RuntimeError(result.stderr.strip() or "Collector failed")
                record = json.loads(result.stdout)
                STATE.parent.mkdir(parents=True, exist_ok=True)
                fd, path = tempfile.mkstemp(dir=STATE.parent, prefix=".codex-", text=True)
                with os.fdopen(fd, "w") as handle: json.dump(record, handle)
                os.replace(path, STATE)
                GLib.idle_add(self.finished, record)
            except Exception as error: GLib.idle_add(self.finished, error)
        threading.Thread(target=work, daemon=True).start()

    def finished(self, result):
        self.refreshing = False
        if not isinstance(result, Exception): self.render(result)
        subprocess.Popen(["pkill", "-RTMIN+8", "waybar"])
        return False

    def on_key(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape: self.hide(); return True
        if keyval in (Gdk.KEY_r, Gdk.KEY_R, Gdk.KEY_Return, Gdk.KEY_KP_Enter): self.refresh(True); return True
        return False


AgentsPanel().run([sys.argv[0]])
