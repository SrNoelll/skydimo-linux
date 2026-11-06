"""Efectos de luz: flujo, monocromo, carrera (跑马灯) y música.

Todas las funciones devuelven un array (n, 3) float en 0..255 en orden lógico.
"""

import math
from collections import defaultdict

import numpy as np

from .i18n import _

PALETTES = {
    "Arcoíris": ["#ff0000", "#ff8000", "#ffff00", "#00ff00", "#00ffff", "#0040ff", "#8000ff", "#ff00c0"],
    "Aurora": ["#00ffa0", "#00c8ff", "#7a00ff", "#00ff60"],
    "Océano": ["#001aff", "#0080ff", "#00e5ff", "#00ffb0"],
    "Atardecer": ["#ff2a00", "#ff7b00", "#ff00a0", "#7a00ff"],
    "Fuego": ["#ff0000", "#ff4000", "#ff9000", "#ffd000"],
    "Bosque": ["#00ff20", "#60ff00", "#00a040", "#c0ff00"],
    "Neón": ["#ff00ff", "#00ffff", "#ff0080", "#8000ff"],
    "Hielo": ["#ffffff", "#a0e0ff", "#0080ff", "#c0f0ff"],
    "Lava": ["#ff0000", "#a00000", "#ff5000", "#600000"],
    "Pastel": ["#ff9ec7", "#9ecbff", "#b8ff9e", "#fff59e", "#d59eff"],
    "Ciberpunk": ["#ff0090", "#00f0ff", "#ffe600", "#7000ff"],
    "Navidad": ["#ff0000", "#00ff00", "#ffffff"],
    "Policía": ["#ff0000", "#0000ff"],
}

FLOW_EFFECTS = [
    ("rainbow", _("Arcoíris")),
    ("gradient", _("Degradado")),
    ("aurora", _("Aurora")),
    ("wave", _("Ola")),
    ("breath", _("Respiración")),
    ("cycle", _("Ciclo de color")),
    ("twinkle", _("Destellos")),
    ("fire", _("Fuego")),
]

MONO_EFFECTS = [
    ("static", _("Fijo")),
    ("breath", _("Respiración")),
    ("heartbeat", _("Latido")),
    ("candle", _("Vela")),
    ("blink", _("Parpadeo")),
]

RACE_STYLES = [
    ("race", _("Carrera de caballos")),
    ("marquee", _("Marquesina")),
    ("comet", _("Cometa")),
    ("scanner", _("Escáner")),
    ("blocks", _("Bloques")),
]

MUSIC_STYLES = [
    ("spectrum", _("Espectro")),
    ("pulse", _("Pulso")),
    ("vu", _("Vúmetro")),
    ("ripple", _("Ondas")),
    ("flowbeat", _("Arcoíris rítmico")),
    ("bass", _("Graves")),
]


def hex_rgb(h):
    h = (h or "#ffffff").lstrip("#")
    if len(h) != 6:
        return np.array([255.0, 255.0, 255.0], np.float32)
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def palette_array(name):
    return np.array([hex_rgb(c) for c in PALETTES.get(name, PALETTES["Arcoíris"])], np.float32)


def palette_sample(pal, x):
    """Muestra la paleta cíclica con interpolación lineal. x arbitrario."""
    k = len(pal)
    x = np.mod(np.asarray(x, np.float32), 1.0) * k
    i0 = np.floor(x).astype(int) % k
    i1 = (i0 + 1) % k
    f = (x - np.floor(x))[..., None]
    return pal[i0] * (1 - f) + pal[i1] * f


def hsv(h, s=1.0, v=1.0):
    h = np.asarray(h, np.float32)
    s = np.broadcast_to(np.asarray(s, np.float32), h.shape)
    v = np.broadcast_to(np.asarray(v, np.float32), h.shape)
    h6 = np.mod(h, 1.0) * 6.0
    i = np.floor(h6).astype(int) % 6
    f = h6 - np.floor(h6)
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1) * 255.0


class Analyzer:
    """FFT + control automático de ganancia + detección de golpes."""
    N = 2048
    SR = 44100

    def __init__(self, nbands=32):
        self.nb = nbands
        freqs = np.fft.rfftfreq(self.N, 1 / self.SR)
        edges = np.geomspace(40, 16000, nbands + 1)
        self.bins = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            a = int(np.searchsorted(freqs, lo))
            b = max(int(np.searchsorted(freqs, hi)), a + 1)
            self.bins.append((a, b))
        centers = np.sqrt(edges[:-1] * edges[1:])
        self.tilt = (centers / 1000.0) ** 0.45
        self.win = np.hanning(self.N).astype(np.float32)
        self.reset()

    def reset(self):
        self.peak = 1e-3
        self.band_peak = np.full(self.nb, 1e-3, np.float32)
        self.bands = np.zeros(self.nb, np.float32)
        self.level = 0.0
        self.bass = 0.0
        self.bass_avg = 0.0
        self.beat = False
        self.beat_env = 0.0
        self.last_beat = 0.0
        self.silent = True

    def update(self, x, sens, smooth, dt, now):
        if x is None or len(x) < self.N:
            x = np.zeros(self.N, np.float32)
        x = x[-self.N:]
        rms = float(np.sqrt(np.mean(x * x)))
        spec = np.abs(np.fft.rfft(x * self.win))
        raw = np.array([spec[a:b].mean() for a, b in self.bins], np.float32) * self.tilt
        self.silent = rms < 3e-4
        if self.silent:
            raw[:] = 0
        m = float(raw.max())
        self.peak = max(m, self.peak * math.exp(-dt * 0.3), 1e-3)
        # per-band peaks so treble is as visible as bass, blended with the global peak
        self.band_peak = np.maximum(raw, self.band_peak * math.exp(-dt * 0.15))
        ref = np.maximum(0.45 * self.peak + 0.55 * self.band_peak, self.peak * 0.08)
        gain = 0.55 + sens * 1.6
        norm = np.clip(raw / ref * gain * 1.25, 0, 1) ** 1.2
        decay = math.exp(-dt * (2.0 + (1.0 - smooth) * 20.0))
        self.bands = np.maximum(norm, self.bands * decay)
        lvl = float(np.clip(norm.mean() * 2.0, 0, 1))
        self.level = max(lvl, self.level * decay)
        bass = float(norm[:5].mean())
        self.bass = max(bass, self.bass * decay)
        a = 1 - math.exp(-dt * 1.5)
        self.bass_avg += (bass - self.bass_avg) * a
        self.beat = (bass > max(0.3, self.bass_avg * 1.4)) and (now - self.last_beat > 0.18)
        if self.beat:
            self.last_beat = now
            self.beat_env = 1.0
        else:
            self.beat_env *= math.exp(-dt * 6.0)


class Effects:
    def __init__(self):
        self.phase = defaultdict(float)
        self.state = {}
        self.rng = np.random.default_rng()
        self.analyzer = Analyzer()

    def _ph(self, key, rate, dt):
        self.phase[key] = (self.phase[key] + rate * dt) % 1e5
        return self.phase[key]

    # ------------------------------------------------------------------ flujo
    def flow(self, L, cfg, dt):
        n = L.n
        eff = cfg["flow_effect"]
        sp = cfg["flow_speed"] / 100.0
        sc = cfg["flow_scale"] / 100.0
        dirn = -1.0 if cfg["flow_reverse"] else 1.0
        pal = palette_array(cfg["flow_palette"])
        cycles = 0.25 + sc * 2.75
        rate = 0.02 + sp * 0.6
        ph = self._ph("flow_" + eff, rate, dt)
        x = L.t * cycles - dirn * ph

        if eff == "rainbow":
            return hsv(x)
        if eff == "gradient":
            return palette_sample(pal, x)
        if eff == "aurora":
            a = np.sin(2 * np.pi * (L.t * 1.3 * cycles + dirn * ph * 0.7))
            b = np.sin(2 * np.pi * (L.t * 0.7 * cycles - dirn * ph * 0.4) + 1.3)
            idx = (a + b + 2) / 4 + ph * 0.05
            v = 0.3 + 0.7 * (0.5 + 0.5 * np.sin(2 * np.pi * (L.t * 2 * cycles + dirn * ph * 0.9)))
            return palette_sample(pal, idx) * v[:, None]
        if eff == "wave":
            v = (0.5 + 0.5 * np.sin(2 * np.pi * x)) ** 2
            col = palette_sample(pal, np.array([ph * 0.08]))[0]
            return np.outer(v, col)
        if eff == "breath":
            k = len(pal)
            f = ph % 1.0
            v = math.sin(math.pi * f) ** 2
            col = pal[int(ph) % k]
            return np.tile(col * v, (n, 1))
        if eff == "cycle":
            col = palette_sample(pal, np.array([ph * 0.25]))[0]
            return np.tile(col, (n, 1))
        if eff == "twinkle":
            lv = self.state.get("twinkle")
            if lv is None or len(lv) != n:
                lv = np.zeros((n, 3), np.float32)
            lv *= math.exp(-dt * (1.0 + sp * 5.0))
            prob = (0.2 + sp * 2.5) * dt * (0.4 + sc)
            mask = self.rng.random(n) < prob
            if mask.any():
                lv[mask] = pal[self.rng.integers(len(pal), size=int(mask.sum()))]
            self.state["twinkle"] = lv
            return lv.copy()
        if eff == "fire":
            return self._fire(L, sp, sc)
        return hsv(x)

    def _fire(self, L, sp, sc):
        n = L.n
        H = (n + 1) // 2
        heat = self.state.get("fire")
        if heat is None or len(heat) != H:
            heat = np.zeros(H, np.float32)
        cooling = 40 + (1 - sc) * 60
        sparking = 0.35 + sp * 0.5
        for _ in range(1 + int(sp * 2)):
            heat -= self.rng.random(H) * (((cooling * 10) / H) + 2) / 255.0
            np.clip(heat, 0, 1, out=heat)
            for k in range(H - 1, 1, -1):
                heat[k] = (heat[k - 1] + 2 * heat[k - 2]) / 3.0
            if self.rng.random() < sparking:
                y = int(self.rng.integers(0, min(3, H)))
                heat[y] = min(1.0, heat[y] + self.rng.uniform(0.6, 1.0))
        self.state["fire"] = heat
        t3 = heat * 3.0
        col = np.stack([np.clip(t3, 0, 1), np.clip(t3 - 1, 0, 1) * 0.85,
                        np.clip(t3 - 2, 0, 1) * 0.6], 1) * 255
        out = np.zeros((n, 3), np.float32)
        out[:H] = col
        out[n - 1 - np.arange(H)] = np.maximum(out[n - 1 - np.arange(H)], col)
        return out

    # ------------------------------------------------------------- monocromo
    def mono(self, L, cfg, dt):
        n = L.n
        c = hex_rgb(cfg["mono_color"])
        eff = cfg["mono_effect"]
        sp = cfg["mono_speed"] / 100.0
        v = 1.0
        if eff == "breath":
            ph = self._ph("mbreath", 0.08 + sp * 0.8, dt)
            v = 0.04 + 0.96 * (0.5 - 0.5 * math.cos(2 * math.pi * ph)) ** 2
        elif eff == "heartbeat":
            ph = self._ph("mheart", 0.4 + sp * 1.2, dt)
            f = ph % 1.0
            v = 0.05 + max(math.exp(-((f - 0.1) / 0.045) ** 2),
                           0.7 * math.exp(-((f - 0.3) / 0.055) ** 2))
        elif eff == "candle":
            st = self.state.setdefault("candle", [0.8, 0.8])
            if self.rng.random() < dt * (3 + sp * 15):
                st[1] = self.rng.uniform(0.45, 1.0)
            st[0] += (st[1] - st[0]) * min(1.0, dt * (6 + sp * 20))
            v = st[0]
        elif eff == "blink":
            ph = self._ph("mblink", 0.3 + sp * 4.0, dt)
            v = 1.0 if (ph % 1.0) < 0.5 else 0.0
        return np.tile(c * min(1.0, v), (n, 1))

    # --------------------------------------------------------------- carrera
    def race(self, L, cfg, dt):
        n = L.n
        style = cfg["race_style"]
        sp = cfg["race_speed"] / 100.0
        count = max(1, int(cfg["race_count"]))
        length = cfg["race_length"] / 100.0
        pal = palette_array(cfg["race_palette"])
        dirn = -1.0 if cfg["race_reverse"] else 1.0
        idx = L.idx
        leds_per_s = 3 + sp * 60
        out = np.zeros((n, 3), np.float32)

        if style == "race":
            st = self.state.get("race")
            if st is None or len(st["pos"]) != count or st["n"] != n:
                st = {"n": n, "pos": np.zeros(count),
                      "vel": np.ones(count), "target": np.ones(count)}
                st["pos"] = self.rng.random(count) * 2.0
                self.state["race"] = st
            change = self.rng.random(count) < dt * 0.6
            st["target"][change] = self.rng.uniform(0.75, 1.3, int(change.sum()))
            st["vel"] += (st["target"] - st["vel"]) * min(1.0, dt * 1.5)
            st["pos"] = (st["pos"] + leds_per_s * st["vel"] * dt) % n
            tail = 1.5 + length * n * 0.4
            for h in range(count):
                head = st["pos"][h] if dirn > 0 else (n - 1 - st["pos"][h])
                d = ((head - idx) * dirn) % n
                inten = np.where(d < tail, (1 - d / tail) ** 2, 0.0)
                inten = np.maximum(inten, np.clip(1 - (n - d), 0, 1))
                out += inten[:, None] * pal[h % len(pal)]
            return np.clip(out, 0, 255)

        if style == "marquee":
            gap = 3 + int(length * 7)
            ph = self._ph("marquee", leds_per_s * 0.25, dt)
            u = idx - dirn * ph
            pos = np.mod(u, gap)
            w = max(1.0, gap / 3.0)
            v = np.clip(w - pos, 0, 1) * np.clip(pos + 1, 0, 1)
            group = np.floor(u / gap).astype(int)
            return pal[group % len(pal)] * v[:, None]

        if style == "comet":
            ph = self._ph("comet", leds_per_s / max(1, n), dt)
            tail = 2 + length * n * 0.6
            col = palette_sample(pal, np.array([ph * 0.15]))[0]
            for c in range(count):
                head = ((ph + c / count) % 1.0) * n
                if dirn < 0:
                    head = n - 1 - head
                d = ((head - idx) * dirn) % n
                inten = np.clip(1 - d / tail, 0, 1) ** 1.6
                inten = np.maximum(inten, np.clip(1 - (n - d), 0, 1))
                ccol = palette_sample(pal, np.array([ph * 0.15 + c / count]))[0] if count > 1 else col
                out += inten[:, None] * ccol
            return np.clip(out, 0, 255)

        if style == "scanner":
            buf = self.state.get("scanner")
            if buf is None or len(buf) != n:
                buf = np.zeros((n, 3), np.float32)
            buf *= math.exp(-dt * (2 + (1 - length) * 12))
            ph = self._ph("scanner", leds_per_s / max(1, 2 * n), dt)
            tri = 1 - abs((ph % 1.0) * 2 - 1)
            pos = tri * (n - 1)
            head = np.clip(1 - np.abs(idx - pos), 0, 1)
            col = palette_sample(pal, np.array([ph * 0.1]))[0]
            buf = np.maximum(buf, head[:, None] * col)
            self.state["scanner"] = buf
            return buf.copy()

        if style == "blocks":
            ph = self._ph("blocks", leds_per_s / max(1, n), dt)
            x = (idx / n) * count * (1 + length * 3) - dirn * ph * count
            k = np.floor(x).astype(int)
            f = x - np.floor(x)
            edge = np.clip(np.minimum(f, 1 - f) * 8, 0, 1)
            return pal[k % len(pal)] * edge[:, None]

        return out

    # ---------------------------------------------------------------- música
    def music(self, L, cfg, dt, samples, now):
        an = self.analyzer
        an.update(samples, cfg["music_sensitivity"] / 100.0,
                  cfg["music_smooth"] / 100.0, dt, now)
        n = L.n
        style = cfg["music_style"]
        mode = cfg["music_colormode"]
        pal = palette_array(cfg["music_palette"])
        fixed = hex_rgb(cfg["music_color"])

        def color_at(x):
            x = np.atleast_1d(np.asarray(x, np.float32))
            if mode == "fixed":
                return np.tile(fixed, (len(x), 1))
            if mode == "palette":
                return palette_sample(pal, x)
            return hsv(x * 0.8)

        if style == "spectrum":
            pos = L.sym * (an.nb - 1)
            v = np.interp(pos, np.arange(an.nb), an.bands)
            return color_at(L.sym) * v[:, None]

        if style == "pulse":
            hue = self.state.get("m_hue", 0.0)
            if an.beat:
                hue = (hue + 0.13) % 1.0
            self.state["m_hue"] = hue
            v = min(1.0, 0.25 * an.level + 0.85 * max(an.level, an.beat_env))
            return color_at(hue + L.t * 0.12) * v

        if style == "vu":
            lvl = an.level
            pk = self.state.get("m_peak", 0.0)
            pk = max(lvl, pk - dt * 0.35)
            self.state["m_peak"] = pk
            half = max(1, n / 2)
            fill = np.clip((lvl - L.sym) * half + 1, 0, 1)
            if mode == "rainbow":
                col = hsv(0.33 * (1 - L.sym))
            else:
                col = color_at(L.sym)
            out = col * fill[:, None]
            near = np.abs(L.sym - pk) < (1.0 / half)
            if pk > 0.05:
                out[near] = 255
            return out

        if style == "ripple":
            rip = self.state.setdefault("m_ripples", [])
            hue = self.state.get("m_hue", 0.0)
            if an.beat:
                hue = (hue + 0.12) % 1.0
                rip.append([1.0, hue, 0.5 + 0.5 * an.bass])
            self.state["m_hue"] = hue
            out = np.zeros((n, 3), np.float32) + color_at(hue) * (0.12 * an.level)
            for r in rip:
                r[0] -= dt * 1.1
                inten = np.exp(-((L.sym - r[0]) / 0.09) ** 2) * r[2]
                out = out + color_at(r[1]) * inten[:, None]
            self.state["m_ripples"] = [r for r in rip if r[0] > -0.2]
            return np.clip(out, 0, 255)

        if style == "flowbeat":
            ph = self._ph("m_flow", 0.04 + an.level * 1.2, dt)
            v = 0.2 + 0.8 * max(an.level, an.beat_env)
            return color_at(L.t * 1.0 - ph) * v

        if style == "bass":
            ph = self._ph("m_bass", 0.03, dt)
            v = an.bass ** 1.3
            return color_at(ph + L.t * 0.1) * v

        return np.zeros((n, 3), np.float32)
