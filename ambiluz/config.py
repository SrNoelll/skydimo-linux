import json
import os
import threading

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "ambiluz")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    # general
    "power": True,
    "mode": "sync",                 # sync | flow | mono | music | race
    "brightness": 80,
    # dispositivo / instalación
    "port": "auto",
    "model": "auto",                # auto | SK0127 | ... | custom
    "custom_segments": [17, 31, 17, 0],
    "reverse": False,
    "offset": 0,
    "color_order": "RGB",
    "fps": 30,
    "wb_r": 100, "wb_g": 100, "wb_b": 100,
    # sincronización con pantalla
    "sync_region": "full",          # full | top | bottom | left | right | movie
    "sync_smooth": 45,
    "sync_smooth_enabled": True,
    "sync_blackborder": True,
    "sync_depth": 12,
    "sync_saturation": 115,
    "sync_gamma": 15,               # /10
    "sync_minlevel": 3,
    "restore_token": "",
    "x11_monitor": -1,
    # flujo
    "flow_effect": "rainbow",
    "flow_palette": "Aurora",
    "flow_speed": 35,
    "flow_scale": 35,
    "flow_reverse": False,
    # monocromo
    "mono_color": "#ff8a2a",
    "mono_effect": "static",
    "mono_speed": 30,
    # música
    "music_style": "spectrum",
    "music_sensitivity": 55,
    "music_smooth": 45,
    "music_colormode": "rainbow",   # rainbow | palette | fixed
    "music_palette": "Neón",
    "music_color": "#00aaff",
    "music_device": "@DEFAULT_MONITOR@",
    # carrera (跑马灯)
    "race_style": "race",
    "race_speed": 45,
    "race_count": 4,
    "race_length": 30,
    "race_palette": "Arcoíris",
    "race_reverse": False,
    # sistema
    "off_on_lock": True,
    "autostart": False,
    "close_to_tray": True,
    "language": "auto",
}


class Config:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self.data = dict(DEFAULTS)
        self.lock = threading.RLock()
        self.dirty = False
        self.version = 0
        try:
            with open(path) as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in DEFAULTS:
                    self.data[k] = v
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.data.get(k, DEFAULTS.get(k))

    def set(self, k, v):
        with self.lock:
            if self.data.get(k) != v:
                self.data[k] = v
                self.dirty = True
                self.version += 1

    def save(self, force=False):
        with self.lock:
            if not (self.dirty or force):
                return
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
            self.dirty = False
