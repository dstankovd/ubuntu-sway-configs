#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk


def default_id(target):
    result = subprocess.run(["wpctl", "inspect", target], capture_output=True, text=True)
    match = re.search(r"^id (\d+),", result.stdout)
    return int(match.group(1)) if match else -1


class AudioManager(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.sway.AudioManager")
        self.window = None
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True

    def do_activate(self):
        if self.window:
            self.window.present(); self.refresh(); return
        self.hold()
        self.window = Gtk.ApplicationWindow(application=self, title="Audio devices",
            default_width=480, default_height=410, resizable=False)
        self.window.connect("close-request", self.hide)
        css = Gtk.CssProvider()
        css.load_from_data(Path("/home/dimitar/.config/modals/theme.css").read_bytes() + b"""
          * { font-family: "JetBrainsMono Nerd Font"; }
          .title { font-size: 16px; font-weight: bold; }
          .section { font-size: 10px; font-weight: bold; color: @modal_fg_dim; }
          .device { font-size: 12px; }
          .meta { font-size: 10px; color: @modal_fg_dim; }
          .active { font-weight: bold; color: @modal_fg_bright; }
          list { background: transparent; }
          row { padding: 8px 10px; color: @modal_fg; }
          row:selected { background: @modal_selected; color: @modal_fg_bright; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        root.set_margin_top(16); root.set_margin_bottom(14); root.set_margin_start(16); root.set_margin_end(16)
        title = Gtk.Label(label="󰓃  Audio devices", xalign=0); title.set_css_classes(["title"]); root.append(title)
        root.append(Gtk.Separator())
        self.output_list = self.add_section(root, "OUTPUTS")
        self.input_list = self.add_section(root, "INPUTS")
        hint = Gtk.Label(label="Enter / click set default · R refresh · Esc close", xalign=0)
        hint.set_css_classes(["meta"]); root.append(hint)
        self.window.set_child(root)
        keys = Gtk.EventControllerKey(); keys.connect("key-pressed", self.on_key); self.window.add_controller(keys)
        self.refresh()
        if self.daemon_start and self.first_activation:
            self.first_activation = False; self.window.set_visible(False)
        else: self.window.present()

    def add_section(self, root, name):
        label = Gtk.Label(label=name, xalign=0); label.set_css_classes(["section"]); root.append(label)
        scroller = Gtk.ScrolledWindow(min_content_height=105, vexpand=True)
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        listing.set_activate_on_single_click(True); listing.connect("row-activated", self.choose)
        scroller.set_child(listing); root.append(scroller); return listing

    def refresh(self, *_):
        try:
            graph = json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True,
                               check=True, timeout=5).stdout)
            defaults = {"Audio/Sink": default_id("@DEFAULT_AUDIO_SINK@"),
                        "Audio/Source": default_id("@DEFAULT_AUDIO_SOURCE@")}
            devices = {"Audio/Sink": [], "Audio/Source": []}
            for item in graph:
                if item.get("type") != "PipeWire:Interface:Node": continue
                props = item.get("info", {}).get("props", {})
                kind = props.get("media.class")
                if kind not in devices: continue
                name = props.get("node.description") or props.get("node.nick") or props.get("node.name") or str(item["id"])
                devices[kind].append((item["id"], name, props.get("node.name", "")))
            for kind, listing in (("Audio/Sink", self.output_list), ("Audio/Source", self.input_list)):
                while child := listing.get_first_child(): listing.remove(child)
                first = None
                for node_id, name, internal in sorted(devices[kind], key=lambda x: x[1].lower()):
                    row = Gtk.ListBoxRow(); row.node_id = node_id
                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    active = node_id == defaults[kind]
                    icon = "󰓃" if kind == "Audio/Sink" else "󰍬"
                    label = Gtk.Label(label=f"{icon}  {name}", xalign=0, hexpand=True)
                    label.set_css_classes(["device", "active"] if active else ["device"])
                    state = Gtk.Label(label="default" if active else ("virtual" if "easyeffects" in internal else ""))
                    state.set_css_classes(["meta"]); box.append(label); box.append(state); row.set_child(box); listing.append(row)
                    if active or first is None: first = row
                if first: listing.select_row(first)
        except Exception:
            pass

    def choose(self, _listing, row):
        if row:
            subprocess.run(["wpctl", "set-default", str(row.node_id)])
            self.refresh()

    def hide(self, *_): self.window.set_visible(False); return True
    def on_key(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape: self.hide(); return True
        if keyval in (Gdk.KEY_r, Gdk.KEY_R): self.refresh(); return True
        return False


AudioManager().run([sys.argv[0]])
