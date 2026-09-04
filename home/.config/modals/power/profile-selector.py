#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


PROFILES = (
    ("power-saver", "Best battery"),
    ("balanced", "Balanced"),
    ("performance", "Best performance"),
)


class ProfileSelector(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.waybar.PowerProfileSelector")
        self.window = None
        self.rows = []
        self.labels = {}
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True

    @staticmethod
    def get_active_profile():
        try:
            return subprocess.run(
                ["powerprofilesctl", "get"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "balanced"

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            self.profile_list.grab_focus()
            return

        # Only the primary GApplication instance stays resident. Secondary
        # click-launchers forward activation over D-Bus and exit immediately.
        self.hold()
        self.active_profile = self.get_active_profile()
        self.window = Gtk.ApplicationWindow(
            application=self,
            title="Power Profile",
            default_width=390,
            default_height=210,
            resizable=False,
        )
        self.window.connect("close-request", self.on_close_request)

        css = Gtk.CssProvider()
        css.load_from_data(Path("/home/dimitar/.config/modals/theme.css").read_bytes() + b"""
            window { background: @modal_bg; color: @modal_fg_bright; }
            .title {
                font-family: \"JetBrainsMono Nerd Font\";
                font-size: 14px;
                font-weight: bold;
                padding: 12px 14px 7px;
            }
            list { background: transparent; padding: 0 8px 8px; }
            row {
                border-radius: 0;
                padding: 8px 12px;
                color: @modal_fg;
            }
            row:selected { background: @modal_selected; color: @modal_fg_bright; }
            .profile-label {
                font-family: \"JetBrainsMono Nerd Font\";
                font-size: 13px;
            }
            .active-profile { font-weight: bold; color: @modal_fg_bright; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label="Power profile", xalign=0)
        title.add_css_class("title")
        content.append(title)

        self.profile_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.profile_list.set_activate_on_single_click(True)
        self.profile_list.connect("row-activated", self.apply_selected)

        active_row = None
        for profile_id, display_name in PROFILES:
            row = Gtk.ListBoxRow()
            row.profile_id = profile_id
            label = Gtk.Label(xalign=0)
            label.add_css_class("profile-label")
            if profile_id == self.active_profile:
                label.set_text(f"   {display_name}")
                label.add_css_class("active-profile")
                active_row = row
            else:
                label.set_text(f"   {display_name}")
            row.set_child(label)
            self.profile_list.append(row)
            self.rows.append(row)
            self.labels[profile_id] = label

        content.append(self.profile_list)
        self.window.set_child(content)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(keys)

        self.profile_list.select_row(active_row or self.rows[1])
        if self.daemon_start and self.first_activation:
            self.first_activation = False
            self.window.set_visible(False)
        else:
            self.window.present()
            self.profile_list.grab_focus()

    def on_close_request(self, window):
        window.set_visible(False)
        return True

    def on_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.window.set_visible(False)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.apply_selected(self.profile_list, self.profile_list.get_selected_row())
            return True
        return False

    def apply_selected(self, _listbox, row):
        if row is None:
            return
        try:
            subprocess.run(
                ["powerprofilesctl", "set", row.profile_id],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return
        self.active_profile = row.profile_id
        for profile_id, display_name in PROFILES:
            label = self.labels[profile_id]
            if profile_id == self.active_profile:
                label.set_text(f"   {display_name}")
                label.add_css_class("active-profile")
            else:
                label.set_text(f"   {display_name}")
                label.remove_css_class("active-profile")
        self.window.set_visible(False)


ProfileSelector().run([sys.argv[0]])
