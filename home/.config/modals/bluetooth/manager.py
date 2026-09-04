#!/usr/bin/env python3
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

def bt(*args, timeout=12):
    return subprocess.run(["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout)

class BluetoothManager(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.sway.BluetoothManager")
        self.window = None; self.busy = False; self.devices = []
        self.daemon_start = "--daemon" in sys.argv; self.first_activation = True

    def do_activate(self):
        if self.window:
            self.window.present(); self.refresh(False); return
        self.hold()
        self.window = Gtk.ApplicationWindow(application=self, title="Bluetooth",
            default_width=500, default_height=480, resizable=False)
        self.window.connect("close-request", self.hide)
        css = Gtk.CssProvider()
        css.load_from_data(Path("/home/dimitar/.config/modals/theme.css").read_bytes() + b"""
          * { font-family: "JetBrainsMono Nerd Font"; }
          .title { font-size: 16px; font-weight: bold; }
          .subtitle, .hint { font-size: 10px; color: @modal_fg_dim; }
          .device { font-size: 12px; }
          .active { font-weight: bold; color: @modal_fg_bright; }
          .error { font-size: 10px; color: @modal_error; }
          list { background: transparent; }
          row { padding: 8px 10px; color: @modal_fg; }
          row:selected { background: @modal_selected; color: @modal_fg_bright; }
          button { border-radius: 0; padding: 6px 9px; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        root.set_margin_top(16); root.set_margin_bottom(13); root.set_margin_start(16); root.set_margin_end(16)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Label(label="󰂯"); icon.set_css_classes(["title"])
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        title = Gtk.Label(label="Bluetooth", xalign=0); title.set_css_classes(["title"])
        self.summary = Gtk.Label(label="CHECKING ADAPTER", xalign=0); self.summary.set_css_classes(["subtitle"])
        labels.append(title); labels.append(self.summary); head.append(icon); head.append(labels); root.append(head)
        root.append(Gtk.Separator())
        scroller = Gtk.ScrolledWindow(vexpand=True, min_content_height=300)
        self.listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listing.set_activate_on_single_click(False); self.listing.connect("row-activated", self.toggle_connection)
        scroller.set_child(self.listing); root.append(scroller)
        self.message = Gtk.Label(xalign=0, wrap=True); self.message.set_css_classes(["error"]); root.append(self.message)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        for label, callback in (("Connect", self.toggle_connection), ("Pair", self.pair),
                                ("Trust", self.trust), ("Scan", lambda *_: self.refresh(True)),
                                ("Power", self.toggle_power)):
            button = Gtk.Button(label=label); button.connect("clicked", callback); actions.append(button)
        root.append(actions)
        hint = Gtk.Label(label="Enter connect · P pair · T trust · R scan · Esc close", xalign=0)
        hint.set_css_classes(["hint"]); root.append(hint); self.window.set_child(root)
        keys = Gtk.EventControllerKey(); keys.connect("key-pressed", self.on_key); self.window.add_controller(keys)
        self.refresh(False)
        if self.daemon_start and self.first_activation:
            self.first_activation = False; self.window.set_visible(False)
        else: self.window.present()

    def run_async(self, work, done):
        if self.busy: return
        self.busy = True; self.message.set_text("Working…")
        def runner():
            try: result = work()
            except Exception as error: result = error
            GLib.idle_add(self.finish, done, result)
        threading.Thread(target=runner, daemon=True).start()
    def finish(self, done, result): self.busy = False; done(result); return False

    @staticmethod
    def inventory(scan):
        shown = bt("show"); powered = "Powered: yes" in shown.stdout
        if scan and powered: bt("--timeout", "7", "scan", "on", timeout=10)
        devices = []
        if powered:
            for line in bt("devices").stdout.splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) != 3: continue
                mac, name = parts[1], parts[2]
                info = bt("info", mac).stdout
                def flag(key): return f"{key}: yes" in info
                devices.append({"mac": mac, "name": name, "paired": flag("Paired"),
                    "trusted": flag("Trusted"), "connected": flag("Connected")})
        devices.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
        return powered, devices

    def refresh(self, scan=False): self.run_async(lambda: self.inventory(scan), self.render)
    def render(self, result):
        self.message.set_text("")
        if isinstance(result, Exception): self.message.set_text(str(result)); return
        powered, self.devices = result
        self.summary.set_text("POWERED OFF" if not powered else
            (f"{sum(d['connected'] for d in self.devices)} CONNECTED" if any(d["connected"] for d in self.devices) else "POWERED ON"))
        while child := self.listing.get_first_child(): self.listing.remove(child)
        first = None
        for device in self.devices:
            row = Gtk.ListBoxRow(); row.device = device
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            label = Gtk.Label(label=("󰂱" if device["connected"] else "󰂯") + "  " + device["name"], xalign=0, hexpand=True)
            label.set_css_classes(["device", "active"] if device["connected"] else ["device"])
            flags = (["connected"] if device["connected"] else []) + (["paired"] if device["paired"] else []) + (["trusted"] if device["trusted"] else [])
            meta = Gtk.Label(label=" · ".join(flags)); meta.set_css_classes(["hint"])
            box.append(label); box.append(meta); row.set_child(box); self.listing.append(row)
            if first is None: first = row
        if first: self.listing.select_row(first)
        elif powered: self.message.set_text("No devices found. Select Scan to discover nearby devices.")
        subprocess.Popen(["pkill", "-RTMIN+9", "waybar"])

    def selected(self):
        row = self.listing.get_selected_row(); return row.device if row else None
    def action(self, *args, timeout=25):
        self.run_async(lambda: bt(*args, timeout=timeout), self.action_done)
    def action_done(self, result):
        if isinstance(result, Exception): self.message.set_text(str(result))
        elif result.returncode: self.message.set_text(result.stderr.strip() or result.stdout.strip() or "Bluetooth action failed.")
        GLib.timeout_add(700, lambda: (self.refresh(False), False)[1])
    def toggle_connection(self, *_):
        device = self.selected()
        if device: self.action("disconnect" if device["connected"] else "connect", device["mac"])
    def pair(self, *_):
        device = self.selected()
        if device: self.action("pair", device["mac"], timeout=40)
    def trust(self, *_):
        device = self.selected()
        if device: self.action("trust", device["mac"])
    def toggle_power(self, *_):
        powered = "Powered: yes" in bt("show").stdout; self.action("power", "off" if powered else "on")
    def hide(self, *_): self.window.set_visible(False); return True
    def on_key(self, _c, key, _code, _state):
        if key == Gdk.KEY_Escape: self.hide(); return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter): self.toggle_connection(); return True
        if key in (Gdk.KEY_r, Gdk.KEY_R): self.refresh(True); return True
        if key in (Gdk.KEY_p, Gdk.KEY_P): self.pair(); return True
        if key in (Gdk.KEY_t, Gdk.KEY_T): self.trust(); return True
        return False

BluetoothManager().run([sys.argv[0]])
