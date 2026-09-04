#!/usr/bin/env python3

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


BINDINGS = (
    ("Super + Enter", "Open terminal"),
    ("Super + D", "Open application launcher"),
    ("Super + L", "Lock screen"),
    ("Super + Escape", "Open power menu"),
    ("Super + /", "Open keybind cheat sheet"),
    ("Super + Shift + O", "Open OpenVPN manager"),
    ("Super + Shift + W", "Open Wi-Fi manager"),
    ("Super + Shift + A", "Open Codex usage and limits"),
    ("Super + Shift + B", "Open Bluetooth manager"),
    ("Super + Shift + M", "Open audio device selector"),
    ("Print", "Open screenshot menu"),
    ("Alt + Shift", "Switch keyboard language"),
    ("Alt + Tab", "Focus next tab or container"),
    ("Alt + Shift + Tab", "Focus previous tab or container"),
    ("Super + Shift + Q", "Close focused window"),
    ("Super + Shift + E", "Exit Sway session"),
    ("Super + Shift + C", "Reload Sway configuration"),
    ("Super + H / J / K", "Focus left / down / up"),
    ("Super + Right", "Focus right"),
    ("Super + Arrow keys", "Move focus by direction"),
    ("Super + Shift + H/J/K/L", "Move window by direction"),
    ("Super + Shift + Arrows", "Move window by direction"),
    ("Super + 1…0", "Switch to workspace 1…10"),
    ("Super + Shift + 1…0", "Move window to workspace 1…10"),
    ("Super + B", "Split layout horizontally"),
    ("Super + V", "Split layout vertically"),
    ("Super + S", "Stacking layout"),
    ("Super + W", "Tabbed layout"),
    ("Super + E", "Toggle split layout"),
    ("Super + F", "Toggle fullscreen"),
    ("Super + Shift + Space", "Toggle floating window"),
    ("Super + Space", "Switch focus between tiling and floating"),
    ("Super + A", "Focus parent container"),
    ("Super + R", "Enter resize mode"),
    ("Super + Shift + -", "Move window to scratchpad"),
    ("Super + -", "Show or hide scratchpad window"),
    ("Super + Shift + S", "Lock and suspend"),
    ("Super + N", "Dismiss newest notification"),
    ("Super + Shift + N", "Restore latest notification"),
    ("Super + Ctrl + N", "Dismiss all notifications"),
    ("Volume mute", "Toggle speaker mute"),
    ("Volume down / up", "Adjust volume by 5%"),
    ("Mic mute", "Toggle microphone mute"),
    ("Brightness down / up", "Adjust brightness by 10%"),
    ("Sleep key", "Lock and suspend"),
)


class KeybindCheatsheet(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.sway.KeybindCheatsheet")
        self.window = None
        self.daemon_start = "--daemon" in sys.argv
        self.first_activation = True

    def do_activate(self):
        if self.window is not None:
            self.search.set_text("")
            self.window.present()
            self.search.grab_focus()
            return

        self.hold()
        self.window = Gtk.ApplicationWindow(
            application=self,
            title="Keybind Cheat Sheet",
            default_width=620,
            default_height=570,
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
                padding: 13px 14px 8px;
            }
            entry {
                margin: 0 12px 10px;
                padding: 7px 9px;
                border: 1px solid @modal_border;
                border-radius: 0;
                background: @modal_bg_deep;
                color: @modal_fg_bright;
                font-family: \"JetBrainsMono Nerd Font\";
                font-size: 12px;
            }
            entry:focus { border-color: @modal_focus; }
            scrolledwindow { border-top: 1px solid @modal_hover; }
            list { background: transparent; }
            row { padding: 7px 14px; }
            row:hover, row:selected { background: @modal_selected; }
            .shortcut {
                color: @modal_fg_bright;
                font-family: \"JetBrainsMono Nerd Font\";
                font-size: 12px;
                font-weight: bold;
            }
            .action {
                color: @modal_fg;
                font-family: \"JetBrainsMono Nerd Font\";
                font-size: 12px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label="Keybinds", xalign=0)
        title.add_css_class("title")
        content.append(title)

        self.search = Gtk.SearchEntry(placeholder_text="Search action or keybind…")
        self.search.connect("search-changed", self.on_search_changed)
        content.append(self.search)

        self.binding_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.binding_list.set_filter_func(self.filter_row)
        for shortcut, action in BINDINGS:
            row = Gtk.ListBoxRow(activatable=False, selectable=False)
            row.search_text = f"{shortcut} {action}".casefold()

            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
            key = Gtk.Label(label=shortcut, xalign=0)
            key.set_size_request(220, -1)
            key.add_css_class("shortcut")
            description = Gtk.Label(label=action, xalign=0, hexpand=True)
            description.add_css_class("action")
            line.append(key)
            line.append(description)
            row.set_child(line)
            self.binding_list.append(row)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.binding_list)
        content.append(scroll)
        self.window.set_child(content)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(keys)

        if self.daemon_start and self.first_activation:
            self.first_activation = False
            self.window.set_visible(False)
        else:
            self.window.present()
            self.search.grab_focus()

    def filter_row(self, row):
        query = self.search.get_text().strip().casefold()
        return not query or all(term in row.search_text for term in query.split())

    def on_search_changed(self, _entry):
        self.binding_list.invalidate_filter()

    def on_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.window.set_visible(False)
            return True
        return False

    def on_close_request(self, window):
        window.set_visible(False)
        return True


KeybindCheatsheet().run([sys.argv[0]])
