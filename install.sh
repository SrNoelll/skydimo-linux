#!/usr/bin/env bash
# Ambiluz installer — Skydimo monitor ambient light for Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash
#
# Options:  --yes (no questions)  --no-deps  --no-udev  --uninstall
set -euo pipefail

REPO="SrNoelll/skydimo-linux"
BRANCH="main"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/ambiluz"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
UDEV_RULE="/etc/udev/rules.d/60-ambiluz.rules"

YES=0; DEPS=1; UDEV=1; UNINSTALL=0
for a in "$@"; do
  case "$a" in
    -y|--yes) YES=1 ;;
    --no-deps) DEPS=0 ;;
    --no-udev) UDEV=0 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
  esac
done

c_b=$'\e[1m'; c_g=$'\e[32m'; c_y=$'\e[33m'; c_r=$'\e[31m'; c_0=$'\e[0m'
say()  { printf '%s\n' "${c_b}==>${c_0} $*"; }
ok()   { printf '%s\n' "${c_g}✔${c_0} $*"; }
warn() { printf '%s\n' "${c_y}!${c_0} $*"; }
die()  { printf '%s\n' "${c_r}✘ $*${c_0}"; exit 1; }
ask() {  # ask "question" -> 0 = yes
  [ "$YES" = 1 ] && return 0
  local ans=""
  if [ -r /dev/tty ]; then read -r -p "$1 [Y/n] " ans </dev/tty || true; else return 0; fi
  [[ -z "$ans" || "$ans" =~ ^[YySs] ]]
}
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

# ------------------------------------------------------------------ uninstall
if [ "$UNINSTALL" = 1 ]; then
  say "Removing Ambiluz"
  "$BIN/ambiluz" --quit >/dev/null 2>&1 || true
  rm -rf "$DEST" "$BIN/ambiluz" "$APPS/ambiluz.desktop" "$ICONS/ambiluz.svg" \
         "$HOME/.config/autostart/ambiluz.desktop"
  if [ -f "$UDEV_RULE" ] && ask "Remove the udev rule $UDEV_RULE?"; then
    $SUDO rm -f "$UDEV_RULE" && $SUDO udevadm control --reload-rules || true
  fi
  ok "Uninstalled (your settings stay in ~/.config/ambiluz)."
  exit 0
fi

# ---------------------------------------------------------------- distro/deps
. /etc/os-release 2>/dev/null || true
ids=" ${ID:-} ${ID_LIKE:-} "
PM=""; PKGS=""
if   [[ "$ids" == *" arch "* || "$ids" == *archlinux* || "$ids" == *manjaro* || "$ids" == *cachyos* || "$ids" == *endeavouros* ]]; then
  PM="pacman"; PKGS="pyside6 python-numpy python-gobject gst-plugins-base gst-plugins-good gst-plugin-pipewire xdg-desktop-portal"
elif [[ "$ids" == *debian* || "$ids" == *ubuntu* ]]; then
  PM="apt"; PKGS="python3-pyside6.qtwidgets python3-pyside6.qtgui python3-pyside6.qtcore python3-pyside6.qtnetwork python3-numpy python3-gi gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-pulseaudio gstreamer1.0-pipewire xdg-desktop-portal python3-venv python3-pip"
elif [[ "$ids" == *fedora* || "$ids" == *rhel* || "$ids" == *nobara* ]]; then
  PM="dnf"; PKGS="python3-pyside6 python3-numpy python3-gobject gstreamer1-plugins-base gstreamer1-plugins-good pipewire-gstreamer xdg-desktop-portal"
elif [[ "$ids" == *suse* ]]; then
  PM="zypper"; PKGS="python3-pyside6 python3-numpy python3-gobject typelib-1_0-Gst-1_0 gstreamer-plugins-base gstreamer-plugins-good gstreamer-plugin-pipewire xdg-desktop-portal"
fi

PY=/usr/bin/python3
[ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 is required"

check_gi()  { "$PY" -c "import gi; gi.require_version('Gst','1.0'); gi.require_version('GstApp','1.0'); from gi.repository import Gst, GstApp, Gio" >/dev/null 2>&1; }
check_qt()  { "$1" -c "import PySide6.QtWidgets, PySide6.QtNetwork, numpy" >/dev/null 2>&1; }
check_gst() { command -v gst-inspect-1.0 >/dev/null || return 0
              gst-inspect-1.0 pipewiresrc >/dev/null 2>&1 && gst-inspect-1.0 pulsesrc >/dev/null 2>&1; }

if [ "$DEPS" = 1 ]; then
  if check_gi && check_qt "$PY" && check_gst; then
    ok "All dependencies are already installed"
  elif [ -n "$PM" ]; then
    say "Installing dependencies with $PM"
    echo "    $PKGS"
    if ask "Install them now (needs sudo)?"; then
      case "$PM" in
        pacman) $SUDO pacman -S --needed --noconfirm $PKGS ;;
        apt)    $SUDO apt-get update -qq; $SUDO apt-get install -y $PKGS || \
                  { warn "Some packages were not found, retrying without Qt (pip fallback)";
                    $SUDO apt-get install -y $(echo $PKGS | tr ' ' '\n' | grep -v pyside6); } ;;
        dnf)    $SUDO dnf install -y $PKGS ;;
        zypper) $SUDO zypper --non-interactive install $PKGS || true ;;
      esac
    fi
  else
    warn "Unknown distribution. Please install: PySide6, numpy, PyGObject, GStreamer (base, good, pipewire) and xdg-desktop-portal."
  fi
fi
check_gi  || die "PyGObject / GStreamer introspection missing (python3-gi + GStreamer typelibs)."
check_gst || warn "GStreamer pipewiresrc or pulsesrc plugin not found: screen or music sync may not work."

# --------------------------------------------------------------------- source
TMP=""
SRC="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -z "$SRC" ] || [ ! -f "$SRC/ambiluz/__main__.py" ]; then
  say "Downloading Ambiluz from GitHub ($REPO)"
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar -xz -C "$TMP" --strip-components=1
  SRC="$TMP"
fi

say "Installing to $DEST"
"$BIN/ambiluz" --quit >/dev/null 2>&1 || true
mkdir -p "$DEST" "$BIN" "$APPS" "$ICONS"
rm -rf "$DEST/ambiluz"
cp -r "$SRC/ambiluz" "$DEST/"
find "$DEST" -name '__pycache__' -prune -exec rm -rf {} +
cp "$SRC/ambiluz/icon.svg" "$ICONS/ambiluz.svg"

# Qt fallback: private virtualenv with PySide6 from pip
RUNPY="$PY"
if ! check_qt "$PY"; then
  say "PySide6 not available from your distro: creating a private environment (pip)"
  "$PY" -m venv --system-site-packages "$DEST/venv" || die "python3-venv is required"
  "$DEST/venv/bin/pip" install -q --upgrade pip
  "$DEST/venv/bin/pip" install -q "PySide6>=6.5" numpy || die "pip install PySide6 failed"
  RUNPY="$DEST/venv/bin/python"
fi

cat > "$BIN/ambiluz" <<EOF
#!/bin/sh
cd "$DEST" && exec "$RUNPY" -m ambiluz "\$@"
EOF
chmod +x "$BIN/ambiluz"

cat > "$APPS/ambiluz.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Ambiluz
GenericName=Monitor ambient light
Comment=Skydimo LED strip: screen sync, music and effects
Exec=$BIN/ambiluz
Icon=ambiluz
Categories=Utility;Settings;HardwareSettings;
Keywords=skydimo;ambilight;led;rgb;backlight;adalight;
StartupNotify=false
Actions=Toggle;Sync;Music;

[Desktop Action Toggle]
Name=On / Off
Exec=$BIN/ambiluz --toggle

[Desktop Action Sync]
Name=Screen sync
Exec=$BIN/ambiluz --mode sync

[Desktop Action Music]
Name=Music mode
Exec=$BIN/ambiluz --mode music
EOF
update-desktop-database "$APPS" >/dev/null 2>&1 || true
gtk-update-icon-cache -q "${ICONS%/scalable/apps}" >/dev/null 2>&1 || true
ok "Installed the app, menu entry and 'ambiluz' command"

# --------------------------------------------------------------- serial access
if [ "$UDEV" = 1 ] && [ ! -f "$UDEV_RULE" ]; then
  say "Serial port access"
  echo "    A udev rule lets your user open the Skydimo controller (CH340, 1a86:7523) without extra groups."
  if ask "Install the udev rule (needs sudo)?"; then
    printf '%s\n' '# Ambiluz: Skydimo LED controllers (CH340 USB-serial)' \
      'SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0660", TAG+="uaccess"' \
      | $SUDO tee "$UDEV_RULE" >/dev/null
    $SUDO udevadm control --reload-rules && $SUDO udevadm trigger --subsystem-match=tty || true
    ok "udev rule installed (unplug and replug the strip if it is connected)"
  fi
fi

if command -v dpkg >/dev/null && dpkg -s brltty >/dev/null 2>&1; then
  warn "'brltty' is installed. On Debian/Ubuntu it grabs CH340 devices and the strip disappears."
  if ask "Remove brltty (only needed for braille displays)?"; then $SUDO apt-get remove -y brltty || true; fi
fi

case ":$PATH:" in *":$BIN:"*) ;; *) warn "$BIN is not in your PATH; use the menu entry or $BIN/ambiluz" ;; esac
echo
ok "${c_b}Done!${c_0} Open ${c_b}Ambiluz${c_0} from your app menu, or run: ${c_b}ambiluz${c_0}"
