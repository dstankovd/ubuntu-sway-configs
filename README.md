# Ubuntu Sway configuration

Personal configuration for a minimal Ubuntu/Sway desktop inspired by the
original i3 setup used by ThePrimeagen. The tracked `home/` directory mirrors
the relevant paths below `$HOME`.

## Desktop stack

- Sway with six persistent workspaces and a subtle focused border
- Waybar with system, network, VPN, Bluetooth, audio, battery, and agent usage indicators
- Foot terminal, Fuzzel launcher, and Starship Bash prompt
- Mako notifications
- Swaylock and Swayidle
- Grim, Slurp, Swappy, and wl-clipboard for annotated screenshots
- GTK4 modal panels for power, keybinds, networking, Bluetooth, audio devices, and usage limits
- xdg-desktop-portal-wlr for screen sharing
- Blueman pairing agent and Udiskie removable-drive automounting via user services
- EasyEffects speaker processing preset

## Layout

```text
home/
├── .config/                 # Sway, Waybar, applications, modals, and services
├── .local/share/easyeffects # ThinkPad presets and speaker-correction impulses
└── Pictures/Wallpapers      # Desktop and blurred lock-screen images
```

The configuration currently contains absolute `/home/dimitar` paths and is
intended for this machine/account. It deliberately excludes credentials,
NetworkManager connection profiles, keyrings, caches, and runtime usage data.

## Required software

The setup uses these Ubuntu packages or equivalent tools:

```text
sway waybar foot fuzzel starship mako swayidle swaylock
brightnessctl power-profiles-daemon playerctl
grim slurp swappy wl-clipboard
python3-gi gir1.2-gtk-4.0 jq
network-manager network-manager-openvpn-gnome
blueman udiskie nautilus
xdg-desktop-portal xdg-desktop-portal-gtk xdg-desktop-portal-wlr
easyeffects mate-polkit gnome-keyring libsecret-tools
```

Also required:

- JetBrainsMono Nerd Font
- `sway-audio-idle-inhibit` at `~/.local/bin/sway-audio-idle-inhibit`

## Restore

Review the files first, then symlink the managed configuration into place:

```bash
python3 install.py --dry-run
python3 install.py
systemctl --user daemon-reload
swaymsg reload
```

The installer backs up replaced paths under
`~/.local/state/ubuntu-sway-configs/backups/` and is safe to rerun. Keep this
checkout in place: the live configuration points into it. Application directories
are linked as directories so edits and atomic saves appear in `git diff`.
Shared directories use individual file links to avoid taking over unrelated files.
EasyEffects saves its current settings in the linked `home/.config/easyeffects/`
directory, so changing effects or window settings can also modify the working tree.

The ThinkPad T14s Gen 2 Intel presets were generated from the matching Lenovo
ALC257 tuning (`17AA:22D1`) using
[speaker-tuning-to-easyeffects](https://github.com/antoinecellerier/speaker-tuning-to-easyeffects).
Warm is selected. Sway starts EasyEffects in service mode at login.
The original IdeaPad preset remains available for comparison.

The brightness helper uses logind's active-session backlight API; it does not
require direct sysfs write access or membership in the `video` group.

No secrets are stored in this repository. Wi-Fi and OpenVPN profiles remain
managed by NetworkManager on the local machine.
