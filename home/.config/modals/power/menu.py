#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


ACTIONS = (
    ("", "Lock", ["swaylock", "-f"]),
    ("", "Suspend", ["/home/dimitar/.config/sway/suspend"]),
    ("", "Reboot", ["systemctl", "reboot"]),
    ("", "Shut down", ["systemctl", "poweroff"]),
)


class PowerMenu(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.waybar.PowerMenu")
        self.window = None
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            self.action_list.grab_focus()
            return

        # Keep only the primary instance resident. Later launches forward their
        # activation over D-Bus and exit immediately.
        self.hold()
        self.window = Gtk.ApplicationWindow(
            application=self,
            title="Power Menu",
            default_width=390,
            default_height=245,
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
            .action-label {
                font-family: \"JetBrainsMono Nerd Font\";
                font-size: 13px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label="Session", xalign=0)
        title.add_css_class("title")
        content.append(title)

        self.action_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.action_list.set_activate_on_single_click(True)
        self.action_list.connect("row-activated", self.run_action)

        first_row = None
        for icon, name, command in ACTIONS:
            row = Gtk.ListBoxRow()
            row.command = command
            label = Gtk.Label(label=f"{icon}  {name}", xalign=0)
            label.add_css_class("action-label")
            row.set_child(label)
            self.action_list.append(row)
            if first_row is None:
                first_row = row

        content.append(self.action_list)
        self.window.set_child(content)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(keys)
        self.action_list.select_row(first_row)

        if self.daemon_start and self.first_activation:
            self.first_activation = False
            self.window.set_visible(False)
        else:
            self.window.present()
            self.action_list.grab_focus()

    def on_close_request(self, window):
        window.set_visible(False)
        return True

    def on_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.window.set_visible(False)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.run_action(self.action_list, self.action_list.get_selected_row())
            return True
        return False

    def run_action(self, _listbox, row):
        if row is None:
            return
        self.window.set_visible(False)
        subprocess.Popen(row.command, start_new_session=True)


PowerMenu().run([sys.argv[0]])
