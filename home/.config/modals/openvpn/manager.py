#!/usr/bin/env python3
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

HELPER = "/home/dimitar/.config/modals/openvpn/connect-profile"


def nmcli(*args, timeout=8, input_text=None):
    return subprocess.run(
        ["nmcli", *args], text=True, input=input_text,
        capture_output=True, timeout=timeout,
    )


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
    fields.append(field + ("\\" if escaped else ""))
    return fields


class OpenVpnManager(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.sway.OpenVpnManager")
        self.window = None
        self.profiles = []
        self.rows = []
        self.busy = False
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True

    def do_activate(self):
        if self.window is not None:
            self.show_main()
            self.window.present()
            self.profile_list.grab_focus()
            self.refresh()
            return

        self.hold()
        self.window = Gtk.ApplicationWindow(
            application=self, title="OpenVPN", default_width=510,
            default_height=430, resizable=False,
        )
        self.window.connect("close-request", self.hide)
        self.install_css()
        self.build_main()

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.window.add_controller(keys)

        if self.daemon_start and self.first_activation:
            self.first_activation = False
            self.window.set_visible(False)
        else:
            self.window.present()
        self.refresh()

    def install_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(Path("/home/dimitar/.config/modals/theme.css").read_bytes() + b"""
          window { background: @modal_bg; color: @modal_fg_bright; }
          * { font-family: "JetBrainsMono Nerd Font"; }
          .title { font-size: 16px; font-weight: bold; }
          .subtitle { font-size: 11px; color: @modal_fg_dim; }
          .section { font-size: 11px; font-weight: bold; color: @modal_fg_dim; }
          .status { font-size: 12px; color: @modal_fg; }
          .error { font-size: 11px; color: @modal_error; }
          .hint { font-size: 10px; color: @modal_fg_dim; }
          list { background: transparent; }
          row { padding: 9px 10px; color: @modal_fg; }
          row:selected { background: @modal_selected; color: @modal_fg_bright; }
          .profile { font-size: 12px; }
          .connected { font-weight: bold; color: @modal_fg_bright; }
          .detail-key { font-size: 10px; color: @modal_fg_dim; }
          .detail-value { font-size: 11px; color: @modal_fg; }
          button { border-radius: 0; padding: 6px 10px; }
          entry { border-radius: 0; padding: 7px; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def build_main(self):
        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.main.set_margin_top(16); self.main.set_margin_bottom(12)
        self.main.set_margin_start(16); self.main.set_margin_end(16)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Label(label="󰖂")
        icon.set_css_classes(["title"])
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label="OpenVPN", xalign=0); title.set_css_classes(["title"])
        self.summary = Gtk.Label(label="CHECKING NETWORKMANAGER", xalign=0)
        self.summary.set_css_classes(["subtitle"])
        titles.append(title); titles.append(self.summary)
        heading.append(icon); heading.append(titles)
        self.main.append(heading)
        self.main.append(Gtk.Separator())

        self.details = Gtk.Grid(column_spacing=12, row_spacing=3)
        self.main.append(self.details)

        label = Gtk.Label(label="PROFILES", xalign=0); label.set_css_classes(["section"])
        self.main.append(label)
        scroller = Gtk.ScrolledWindow(min_content_height=175, vexpand=True)
        self.profile_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.profile_list.set_activate_on_single_click(False)
        self.profile_list.connect("row-activated", self.toggle_selected)
        scroller.set_child(self.profile_list)
        self.main.append(scroller)

        self.message = Gtk.Label(xalign=0, wrap=True)
        self.message.set_css_classes(["error"])
        self.main.append(self.message)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        for text, callback in (("Connect", self.toggle_selected),
                               ("Import", self.import_profile),
                               ("Rename", self.rename_selected),
                               ("Delete", self.delete_selected)):
            button = Gtk.Button(label=text)
            button.connect("clicked", callback)
            actions.append(button)
        self.main.append(actions)
        hint = Gtk.Label(label="Enter connect · I import · N rename · Del delete · R refresh", xalign=0)
        hint.set_css_classes(["hint"])
        self.main.append(hint)
        self.window.set_child(self.main)

    def show_main(self):
        self.window.set_child(self.main)

    def hide(self, *_args):
        self.window.set_visible(False)
        return True

    def run_async(self, work, done):
        if self.busy:
            return
        self.busy = True
        self.message.set_text("Working…")
        def runner():
            try:
                result = work()
            except Exception as error:
                result = error
            GLib.idle_add(self.finish_async, done, result)
        threading.Thread(target=runner, daemon=True).start()

    def finish_async(self, done, result):
        self.busy = False
        done(result)
        return False

    def refresh(self, *_args):
        self.run_async(self.read_profiles, self.render_profiles)

    @staticmethod
    def read_profiles():
        result = nmcli("-t", "--escape", "yes", "-f",
                       "UUID,NAME,TYPE,DEVICE,STATE", "connection", "show")
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "NetworkManager is unavailable.")
        profiles = []
        for line in result.stdout.splitlines():
            fields = split_escaped(line)
            if len(fields) >= 5 and fields[2] == "vpn":
                profiles.append({"uuid": fields[0], "name": fields[1],
                                 "device": fields[3], "state": fields[4],
                                 "active": fields[4] == "activated",
                                 "connecting": fields[4] == "activating"})
        profiles.sort(key=lambda p: (not p["active"], p["name"].lower()))
        details = {}
        active = next((p for p in profiles if p["active"]), None)
        if active:
            info = nmcli("-t", "-f", "GENERAL.DEVICES,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                         "connection", "show", "uuid", active["uuid"])
            for line in info.stdout.splitlines():
                key, _, value = line.partition(":")
                details[key] = value.replace("\\:", ":")
        return profiles, details

    def render_profiles(self, result):
        self.message.set_text("")
        if isinstance(result, Exception):
            self.message.set_text(str(result)); self.summary.set_text("NETWORKMANAGER UNAVAILABLE")
            return
        self.profiles, details = result
        while child := self.profile_list.get_first_child():
            self.profile_list.remove(child)
        self.rows = []
        for profile in self.profiles:
            row = Gtk.ListBoxRow(); row.profile = profile
            state = "●" if profile["active"] else ("◌" if profile["connecting"] else "○")
            label = Gtk.Label(label=f"{state}  {profile['name']}", xalign=0)
            label.set_css_classes(["profile", "connected"] if profile["active"] else ["profile"])
            row.set_child(label); self.profile_list.append(row); self.rows.append(row)
        if self.rows:
            self.profile_list.select_row(self.rows[0])
        active = next((p for p in self.profiles if p["active"]), None)
        connecting = next((p for p in self.profiles if p["connecting"]), None)
        if active: self.summary.set_text(f"CONNECTED · {active['name'].upper()}")
        elif connecting: self.summary.set_text(f"CONNECTING · {connecting['name'].upper()}")
        elif self.profiles: self.summary.set_text("DISCONNECTED")
        else: self.summary.set_text("NO VPN PROFILES FOUND")
        while child := self.details.get_first_child(): self.details.remove(child)
        if active:
            values = (("INTERFACE", details.get("GENERAL.DEVICES", active["device"])),
                      ("IPV4", details.get("IP4.ADDRESS[1]", "")),
                      ("GATEWAY", details.get("IP4.GATEWAY", "")),
                      ("DNS", details.get("IP4.DNS[1]", "")))
            for col, (key, value) in enumerate(values):
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                k = Gtk.Label(label=key, xalign=0); k.set_css_classes(["detail-key"])
                v = Gtk.Label(label=value or "—", xalign=0); v.set_css_classes(["detail-value"])
                box.append(k); box.append(v); self.details.attach(box, col, 0, 1, 1)

    def selected(self):
        row = self.profile_list.get_selected_row()
        return row.profile if row else None

    def toggle_selected(self, *_args):
        profile = self.selected()
        if not profile: return
        if profile["active"]:
            self.run_async(lambda: nmcli("connection", "down", "uuid", profile["uuid"], timeout=25), self.action_done)
        else:
            self.show_credentials(profile)

    def show_credentials(self, profile):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(22); box.set_margin_bottom(22); box.set_margin_start(24); box.set_margin_end(24)
        title = Gtk.Label(label=f"Connect · {profile['name']}", xalign=0); title.set_css_classes(["title"])
        note = Gtk.Label(label="Leave both fields blank for certificate-only profiles.", xalign=0)
        note.set_css_classes(["hint"])
        username = Gtk.Entry(placeholder_text="Username")
        password = Gtk.PasswordEntry(placeholder_text="Password", show_peek_icon=True)
        error = Gtk.Label(xalign=0, wrap=True); error.set_css_classes(["error"])
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel"); connect = Gtk.Button(label="Connect")
        cancel.connect("clicked", lambda *_: self.show_main())
        def submit(*_):
            user, secret = username.get_text().strip(), password.get_text()
            if bool(user) != bool(secret): error.set_text("Enter both username and password, or leave both blank."); return
            self.show_main()
            payload = user.replace("\n", "") + "\n" + secret.replace("\n", "") + "\n"
            self.run_async(lambda: subprocess.run([HELPER, profile["uuid"]], input=payload,
                           text=True, capture_output=True, timeout=35), self.action_done)
        connect.connect("clicked", submit); password.connect("activate", submit)
        buttons.append(cancel); buttons.append(connect)
        for widget in (title, note, username, password, error, buttons): box.append(widget)
        self.window.set_child(box); username.grab_focus()

    def action_done(self, result):
        if isinstance(result, Exception): self.message.set_text(str(result))
        elif result.returncode: self.message.set_text(result.stderr.strip() or result.stdout.strip() or "Action failed.")
        else: self.message.set_text("")
        GLib.timeout_add(600, lambda: (self.refresh(), False)[1])

    def import_profile(self, *_args):
        dialog = Gtk.FileDialog(title="Import OpenVPN profile")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        file_filter = Gtk.FileFilter(name="OpenVPN profiles")
        file_filter.add_pattern("*.ovpn"); file_filter.add_pattern("*.conf")
        filters.append(file_filter); dialog.set_filters(filters); dialog.set_default_filter(file_filter)
        dialog.open(self.window, None, self.import_chosen)

    def import_chosen(self, dialog, result):
        try: path = dialog.open_finish(result).get_path()
        except GLib.Error: return
        self.run_async(lambda: nmcli("connection", "import", "type", "openvpn", "file", path, timeout=20), self.action_done)

    def rename_selected(self, *_args):
        profile = self.selected()
        if not profile: return
        dialog = Gtk.AlertDialog(message=f"Rename {profile['name']}")
        # AlertDialog has no text input, so use a compact transient dialog.
        win = Gtk.Window(title="Rename VPN", transient_for=self.window, modal=True, default_width=360)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        entry = Gtk.Entry(text=profile["name"]); entry.select_region(0, -1)
        button = Gtk.Button(label="Rename")
        def commit(*_):
            name = entry.get_text().strip()
            if not name: return
            win.close(); self.run_async(lambda: nmcli("connection", "modify", "uuid", profile["uuid"], "connection.id", name), self.action_done)
        button.connect("clicked", commit); entry.connect("activate", commit)
        box.append(Gtk.Label(label="New profile name", xalign=0)); box.append(entry); box.append(button)
        win.set_child(box); win.present(); entry.grab_focus()

    def delete_selected(self, *_args):
        profile = self.selected()
        if not profile: return
        dialog = Gtk.AlertDialog(message=f"Delete “{profile['name']}”?", detail="This removes the NetworkManager profile.")
        dialog.set_buttons(["Cancel", "Delete"]); dialog.set_cancel_button(0); dialog.set_default_button(0)
        dialog.choose(self.window, None, lambda d, r: self.delete_answer(d, r, profile))

    def delete_answer(self, dialog, result, profile):
        try: answer = dialog.choose_finish(result)
        except GLib.Error: return
        if answer == 1:
            self.run_async(lambda: nmcli("connection", "delete", "uuid", profile["uuid"]), self.action_done)

    def on_key(self, _controller, keyval, _keycode, state):
        if keyval == Gdk.KEY_Escape: self.hide(); return True
        if self.window.get_child() is not self.main: return False
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter): self.toggle_selected(); return True
        if keyval in (Gdk.KEY_r, Gdk.KEY_R): self.refresh(); return True
        if keyval in (Gdk.KEY_i, Gdk.KEY_I): self.import_profile(); return True
        if keyval in (Gdk.KEY_n, Gdk.KEY_N): self.rename_selected(); return True
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace): self.delete_selected(); return True
        return False


OpenVpnManager().run([sys.argv[0]])
