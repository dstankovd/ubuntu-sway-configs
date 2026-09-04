#!/usr/bin/env python3
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk


def command(*args, timeout=15, input_text=None):
    return subprocess.run(["nmcli", *args], text=True, input=input_text,
                          capture_output=True, timeout=timeout)


def split_escaped(line):
    fields, field, escaped = [], "", False
    for char in line:
        if escaped:
            field += char; escaped = False
        elif char == "\\": escaped = True
        elif char == ":": fields.append(field); field = ""
        else: field += char
    fields.append(field)
    return fields


def wifi_icon(signal):
    if signal >= 75: return "󰤨"
    if signal >= 50: return "󰤥"
    if signal >= 25: return "󰤢"
    return "󰤟"


class WifiManager(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.sway.WifiManager")
        self.window = None
        self.networks = []
        self.busy = False
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True

    def do_activate(self):
        if self.window:
            self.show_main(); self.window.present(); self.listbox.grab_focus(); self.refresh()
            return
        self.hold()
        self.window = Gtk.ApplicationWindow(application=self, title="Wi-Fi",
            default_width=510, default_height=500, resizable=False)
        self.window.connect("close-request", self.hide)
        self.install_css(); self.build_main()
        keys = Gtk.EventControllerKey(); keys.connect("key-pressed", self.on_key)
        self.window.add_controller(keys)
        if self.daemon_start and self.first_activation:
            self.first_activation = False; self.window.set_visible(False)
        else: self.window.present()
        self.refresh()

    def install_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(Path("/home/dimitar/.config/modals/theme.css").read_bytes() + b"""
          window { background: @modal_bg; color: @modal_fg_bright; }
          * { font-family: "JetBrainsMono Nerd Font"; }
          .title { font-size: 16px; font-weight: bold; }
          .subtitle, .hint { font-size: 10px; color: @modal_fg_dim; }
          .section { font-size: 11px; font-weight: bold; color: @modal_fg_dim; }
          .error { font-size: 11px; color: @modal_error; }
          list { background: transparent; }
          row { padding: 8px 10px; color: @modal_fg; }
          row:selected { background: @modal_selected; color: @modal_fg_bright; }
          .network { font-size: 12px; }
          .network-meta { font-size: 10px; color: @modal_fg_dim; }
          .connected { font-weight: bold; color: @modal_fg_bright; }
          button { border-radius: 0; padding: 6px 10px; }
          entry { border-radius: 0; padding: 7px; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def build_main(self):
        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        for name in ("top", "bottom", "start", "end"):
            getattr(self.main, f"set_margin_{name}")(16 if name in ("top", "start", "end") else 12)
        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.hero_icon = Gtk.Label(label="󰤨"); self.hero_icon.set_css_classes(["title"])
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label="Wi-Fi", xalign=0); title.set_css_classes(["title"])
        self.summary = Gtk.Label(label="SCANNING", xalign=0); self.summary.set_css_classes(["subtitle"])
        labels.append(title); labels.append(self.summary); heading.append(self.hero_icon); heading.append(labels)
        self.main.append(heading); self.main.append(Gtk.Separator())
        section = Gtk.Label(label="AVAILABLE NETWORKS", xalign=0); section.set_css_classes(["section"])
        self.main.append(section)
        scroller = Gtk.ScrolledWindow(vexpand=True, min_content_height=300)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(False)
        self.listbox.connect("row-activated", self.activate_selected)
        scroller.set_child(self.listbox); self.main.append(scroller)
        self.message = Gtk.Label(xalign=0, wrap=True); self.message.set_css_classes(["error"])
        self.main.append(self.message)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        for label, callback in (("Connect", self.activate_selected),
                                ("Disconnect", self.disconnect), ("Refresh", self.refresh)):
            button = Gtk.Button(label=label); button.connect("clicked", callback); actions.append(button)
        self.main.append(actions)
        hint = Gtk.Label(label="Enter connect · D disconnect · R rescan · Esc close", xalign=0)
        hint.set_css_classes(["hint"]); self.main.append(hint)
        self.window.set_child(self.main)

    def show_main(self): self.window.set_child(self.main)
    def hide(self, *_): self.window.set_visible(False); return True

    def run_async(self, work, done):
        if self.busy: return
        self.busy = True; self.message.set_text("Working…")
        def runner():
            try: value = work()
            except Exception as error: value = error
            GLib.idle_add(self.finish_async, done, value)
        threading.Thread(target=runner, daemon=True).start()

    def finish_async(self, done, value):
        self.busy = False; done(value); return False

    def refresh(self, *_): self.run_async(self.scan, self.render)

    @staticmethod
    def scan():
        devices = command("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status")
        if devices.returncode: raise RuntimeError(devices.stderr.strip() or "NetworkManager unavailable.")
        device, active = "", ""
        for line in devices.stdout.splitlines():
            fields = split_escaped(line)
            if len(fields) >= 4 and fields[1] == "wifi" and not fields[0].startswith("p2p-"):
                device = fields[0]
                if fields[2] == "connected": active = fields[3]
                break
        if not device: raise RuntimeError("No Wi-Fi adapter found.")

        saved = set()
        profiles = command("-t", "--escape", "yes", "-f", "NAME,TYPE", "connection", "show")
        for line in profiles.stdout.splitlines():
            fields = split_escaped(line)
            if len(fields) >= 2 and fields[1] == "802-11-wireless": saved.add(fields[0])

        result = command("-t", "--escape", "yes", "-f", "IN-USE,SSID,SIGNAL,SECURITY,BSSID",
                         "device", "wifi", "list", "ifname", device, "--rescan", "yes", timeout=18)
        if result.returncode: raise RuntimeError(result.stderr.strip() or "Wi-Fi scan failed.")
        networks = {}
        for line in result.stdout.splitlines():
            fields = split_escaped(line)
            if len(fields) < 5 or not fields[1]: continue
            try: strength = int(fields[2])
            except ValueError: strength = 0
            item = {"ssid": fields[1], "signal": strength, "security": fields[3],
                    "bssid": fields[4], "active": fields[0].strip() == "*",
                    "saved": fields[1] in saved, "device": device}
            old = networks.get(item["ssid"])
            if not old or item["active"] or strength > old["signal"]: networks[item["ssid"]] = item
        connectivity = command("-t", "networking", "connectivity", "check").stdout.strip()
        ordered = sorted(networks.values(), key=lambda n: (not n["active"], -n["signal"], n["ssid"].lower()))
        return ordered, active, connectivity

    def render(self, value):
        self.message.set_text("")
        if isinstance(value, Exception):
            self.message.set_text(str(value)); self.summary.set_text("NETWORKMANAGER UNAVAILABLE"); return
        self.networks, active, connectivity = value
        while child := self.listbox.get_first_child(): self.listbox.remove(child)
        first = None
        for network in self.networks:
            row = Gtk.ListBoxRow(); row.network = network
            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            icon = Gtk.Label(label=wifi_icon(network["signal"]))
            names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            name = Gtk.Label(label=network["ssid"], xalign=0); name.set_css_classes(["network", "connected"] if network["active"] else ["network"])
            flags = []
            if network["active"]: flags.append("connected")
            elif network["saved"]: flags.append("saved")
            flags.append(network["security"] or "open")
            meta = Gtk.Label(label=" · ".join(flags), xalign=0); meta.set_css_classes(["network-meta"])
            strength = Gtk.Label(label=f"{network['signal']}%")
            strength.set_css_classes(["network-meta"])
            names.append(name); names.append(meta); content.append(icon); content.append(names); content.append(strength)
            row.set_child(content); self.listbox.append(row)
            if first is None: first = row
        if first: self.listbox.select_row(first)
        if active:
            state = {"full": "INTERNET", "limited": "LIMITED CONNECTIVITY",
                     "portal": "SIGN-IN REQUIRED", "none": "NO INTERNET"}.get(connectivity, connectivity.upper())
            self.summary.set_text(f"{active.upper()} · {state}"); self.hero_icon.set_text("󰤨")
        else:
            self.summary.set_text("DISCONNECTED"); self.hero_icon.set_text("󰤭")

    def selected(self):
        row = self.listbox.get_selected_row()
        return row.network if row else None

    def activate_selected(self, *_):
        network = self.selected()
        if not network or network["active"]: return
        if network["saved"]:
            self.run_async(lambda: command("--wait", "20", "connection", "up", "id", network["ssid"], timeout=25), self.action_done)
        elif not network["security"] or network["security"] == "--":
            self.run_async(lambda: command("--wait", "20", "device", "wifi", "connect", network["ssid"], "ifname", network["device"], timeout=25), self.action_done)
        else: self.show_password(network)

    def show_password(self, network):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(22); box.set_margin_bottom(22); box.set_margin_start(24); box.set_margin_end(24)
        title = Gtk.Label(label=f"Connect · {network['ssid']}", xalign=0); title.set_css_classes(["title"])
        password = Gtk.PasswordEntry(placeholder_text="Wi-Fi password", show_peek_icon=True)
        error = Gtk.Label(xalign=0); error.set_css_classes(["error"])
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel"); connect = Gtk.Button(label="Connect")
        cancel.connect("clicked", lambda *_: self.show_main())
        def submit(*_):
            secret = password.get_text()
            if not secret: error.set_text("Enter the network password."); return
            self.show_main()
            self.run_async(lambda: command("--ask", "--wait", "20", "device", "wifi", "connect",
                network["ssid"], "ifname", network["device"], timeout=25, input_text=secret + "\n"), self.action_done)
        connect.connect("clicked", submit); password.connect("activate", submit)
        buttons.append(cancel); buttons.append(connect)
        for widget in (title, Gtk.Label(label=network["security"], xalign=0), password, error, buttons): box.append(widget)
        self.window.set_child(box); password.grab_focus()

    def disconnect(self, *_):
        active = next((n for n in self.networks if n["active"]), None)
        if active: self.run_async(lambda: command("device", "disconnect", active["device"]), self.action_done)

    def action_done(self, result):
        if isinstance(result, Exception): self.message.set_text(str(result))
        elif result.returncode: self.message.set_text(result.stderr.strip() or result.stdout.strip() or "Connection failed.")
        else: self.message.set_text("")
        GLib.timeout_add(800, lambda: (self.refresh(), False)[1])

    def on_key(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            if self.window.get_child() is not self.main: self.show_main()
            else: self.hide()
            return True
        if self.window.get_child() is not self.main: return False
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter): self.activate_selected(); return True
        if keyval in (Gdk.KEY_r, Gdk.KEY_R): self.refresh(); return True
        if keyval in (Gdk.KEY_d, Gdk.KEY_D): self.disconnect(); return True
        return False


WifiManager().run([sys.argv[0]])
