#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


CAPTURES = (
    ("󰩭", "Select region", "region"),
    ("", "Focused window", "window"),
    ("󰍹", "Current screen", "screen"),
)
CAPTURE_SCRIPT = "/home/dimitar/.config/modals/screenshots/capture"


class ScreenshotMenu(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.sway.ScreenshotMenu")
        self.window = None
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            self.capture_list.grab_focus()
            return

        self.hold()
        self.window = Gtk.ApplicationWindow(
            application=self,
            title="Screenshot",
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
            .capture-label {
                font-family: \"JetBrainsMono Nerd Font\";
                font-size: 13px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label="Screenshot", xalign=0)
        title.add_css_class("title")
        content.append(title)

        self.capture_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.capture_list.set_activate_on_single_click(True)
        self.capture_list.connect("row-activated", self.capture)

        first_row = None
        for icon, name, mode in CAPTURES:
            row = Gtk.ListBoxRow()
            row.mode = mode
            label = Gtk.Label(label=f"{icon}  {name}", xalign=0)
            label.add_css_class("capture-label")
            row.set_child(label)
            self.capture_list.append(row)
            if first_row is None:
                first_row = row

        content.append(self.capture_list)
        self.window.set_child(content)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(keys)
        self.capture_list.select_row(first_row)

        if self.daemon_start and self.first_activation:
            self.first_activation = False
            self.window.set_visible(False)
        else:
            self.window.present()
            self.capture_list.grab_focus()

    def on_close_request(self, window):
        window.set_visible(False)
        return True

    def on_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.window.set_visible(False)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.capture(self.capture_list, self.capture_list.get_selected_row())
            return True
        return False

    def capture(self, _listbox, row):
        if row is None:
            return
        self.window.set_visible(False)
        subprocess.Popen([CAPTURE_SCRIPT, row.mode], start_new_session=True)


ScreenshotMenu().run([sys.argv[0]])
