# Ubuntu Sway configuration

Personal configuration for a minimal Ubuntu/Sway desktop inspired by the
original i3 setup used by ThePrimeagen. The tracked `home/` directory mirrors
the relevant paths below `$HOME`.

## Desktop stack

- Sway with six persistent workspaces and a subtle focused border
- Waybar with system, network, VPN, Bluetooth, audio, battery, and agent usage indicators
- Foot terminal and Fuzzel launcher
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
├── .local/share/easyeffects # Laptop speaker preset
└── Pictures/Wallpapers      # Desktop and blurred lock-screen images
```

The configuration currently contains absolute `/home/dimitar` paths and is
intended for this machine/account. It deliberately excludes credentials,
NetworkManager connection profiles, keyrings, caches, and runtime usage data.

## Required software

The setup uses these Ubuntu packages or equivalent tools:

```text
sway waybar foot fuzzel mako swayidle swaylock
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

Review the files first, then copy the tracked home tree into place:

```bash
cp -a home/. "$HOME/"
systemctl --user daemon-reload
swaymsg reload
```

No secrets are stored in this repository. Wi-Fi and OpenVPN profiles remain
managed by NetworkManager on the local machine.
