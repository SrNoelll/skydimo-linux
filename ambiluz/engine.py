"""Motor: calcula los colores de cada fotograma y los envía a la tira."""

import math
import threading
import time
import traceback

from .i18n import _
import numpy as np
from gi.repository import Gio

from . import models
from .audio import AudioCapture
from .capture import GLibWorker, ScreenCapture
from .device import DeviceError, SerialDevice, list_ports, max_fps
from .effects import Effects
from .layout import Layout

CHANNELS = {"RGB": [0, 1, 2], "RBG": [0, 2, 1], "GRB": [1, 0, 2],
            "GBR": [1, 2, 0], "BRG": [2, 0, 1], "BGR": [2, 1, 0]}


class BorderDetector:
    """Detecta bandas negras (cine) de forma estable."""

    def __init__(self):
        self.current = None
        self.candidate = None
        self.count = 0

    def update(self, img):
        H, W = img.shape[:2]
        lum = img.max(axis=2)
        bright = lum > 28
        rows = np.flatnonzero(bright.mean(axis=1) > 0.03)
        cols = np.flatnonzero(bright.mean(axis=0) > 0.03)
        if self.current is None or self.current[1] > H or self.current[3] > W:
            self.current = (0, H, 0, W)
        if len(rows) == 0 or len(cols) == 0:
            return self.current                     # pantalla negra: no cambiar
        top, bottom = int(rows[0]), int(rows[-1]) + 1
        left, right = int(cols[0]), int(cols[-1]) + 1
        top = min(top, int(H * 0.4)) // 2 * 2
        left = min(left, int(W * 0.4)) // 2 * 2
        bottom = H - (min(H - bottom, int(H * 0.4)) // 2 * 2)
        right = W - (min(W - right, int(W * 0.4)) // 2 * 2)
        # simétrico: las bandas de cine son iguales arriba y abajo
        v = min(top, H - bottom)
        h = min(left, W - right)
        cand = (v, H - v, h, W - h)
        if cand == self.candidate:
            self.count += 1
        else:
            self.candidate, self.count = cand, 1
        if self.count >= 12 and cand != self.current:
            self.current = cand
        return self.current


class Engine(threading.Thread):
    def __init__(self, cfg):
        super().__init__(name="engine", daemon=True)
        self.cfg = cfg
        self.running = True
        self.worker = GLibWorker()
        self.capture = ScreenCapture(self.worker, cfg)
        self.audio = AudioCapture()
        self.fx = Effects()
        self.border = BorderDetector()

        self.dev = None
        self.detected_model = None
        self.detected_serial = None
        self.device_msg = _("Buscando dispositivo…")
        self.next_connect = 0.0

        self.layout = None
        self._layout_key = None
        self.preview_colors = np.zeros((0, 3), np.float32)
        self.preview_frame = None
        self.border_crop = None
        self.actual_fps = 0.0

        self.test = None                 # (tipo, t_inicio, duración)
        self.locked = False
        self.sleeping = False
        self._fade = 0.0
        self._prev_mode = None
        self._xfade_from = None
        self._xfade_t = 0.0
        self._last_logical = None
        self._sync_prev = None
        self._capture_last_need = 0.0
        self._audio_last_need = 0.0
        self._last_black = 0.0
        self._last_save = 0.0
        self._restart_capture = False
        self.error = ""
        self._subscribe_power_events()

    # ------------------------------------------------------- eventos sistema
    def _subscribe_power_events(self):
        def on_saver(_c, _s, _p, _i, _n, params, *_):
            self.locked = bool(params.unpack()[0])

        def on_sleep(_c, _s, _p, _i, _n, params, *_):
            self.sleeping = bool(params.unpack()[0])
            if not self.sleeping:
                self.next_connect = 0.0

        def sub():
            try:
                sb = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                sb.signal_subscribe(None, "org.freedesktop.ScreenSaver", "ActiveChanged",
                                    None, None, Gio.DBusSignalFlags.NONE, on_saver)
            except Exception:  # noqa: BLE001
                pass
            try:
                yb = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
                yb.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager",
                                    "PrepareForSleep", "/org/freedesktop/login1", None,
                                    Gio.DBusSignalFlags.NONE, on_sleep)
            except Exception:  # noqa: BLE001
                pass

        try:
            self.worker.call(sub)
        except Exception:  # noqa: BLE001
            pass

    # ----------------------------------------------------------- API pública
    def run_test(self, kind, duration=8.0):
        self.test = (kind, time.monotonic(), duration)

    def restart_capture(self, forget_screen=False):
        if forget_screen:
            self.capture.forget_screen()
        self._restart_capture = True

    def reconnect(self):
        self._close_device(_("Reconectando…"))
        self.next_connect = 0.0

    def shutdown(self):
        self.running = False
        self.join(timeout=2)
        try:
            if self.dev and self.layout:
                self.dev.send(bytes(3 * self.layout.n))
        except Exception:  # noqa: BLE001
            pass
        self._close_device(_("Cerrado"))
        self.capture.stop()
        self.audio.stop()
        self.cfg.save()

    # ---------------------------------------------------------- dispositivo
    def _close_device(self, msg):
        if self.dev:
            self.dev.close()
        self.dev = None
        self.device_msg = msg

    def _ensure_device(self, now):
        if self.dev is not None:
            return True
        if now < self.next_connect:
            return False
        self.next_connect = now + 2.0
        port = self.cfg["port"]
        ports = list_ports()
        if port and port != "auto":
            cands = [port]
        else:
            cands = [p["path"] for p in ports if p["likely"]] or [p["path"] for p in ports]
        if not cands:
            self.device_msg = _("No se encuentra la tira (¿está conectada por USB?)")
            return False
        last_err = ""
        for path in cands:
            d = SerialDevice(path)
            try:
                d.open()
                model, serial = d.query()
            except DeviceError as e:
                d.close()
                last_err = str(e)
                continue
            except OSError as e:
                d.close()
                last_err = str(e)
                continue
            self.dev = d
            if model:
                self.detected_model, self.detected_serial = model, serial
            if model and not models.lookup(model) and self.cfg["model"] == "auto":
                self.device_msg = (f"{_('Modelo no reconocido')}: {model} · {path} — "
                                   f"{_('se usa')} {models.DEFAULT_MODEL}; "
                                   f"{_('abre un issue en GitHub para añadirlo')}")
                return True
            self.device_msg = f"{_('Conectado')}: {model or _('modelo desconocido')} · {path}"
            return True
        self.device_msg = last_err or _("No se pudo abrir el puerto")
        return False

    # --------------------------------------------------------------- layout
    def effective_model(self):
        m = self.cfg["model"]
        if m == "auto":
            return self.detected_model or models.DEFAULT_MODEL
        return m

    def _ensure_layout(self):
        m = self.effective_model()
        key = (m, tuple(self.cfg["custom_segments"]), bool(self.cfg["reverse"]), int(self.cfg["offset"]))
        if key != self._layout_key or self.layout is None:
            if m == "custom":
                kind, segs = models.custom_kind(self.cfg["custom_segments"])
            else:
                kind, segs = models.lookup(m) or models.MODELS[models.DEFAULT_MODEL]
            self.layout = Layout(kind, segs, self.cfg["reverse"], self.cfg["offset"])
            self._layout_key = key
            self._sync_prev = None
            self._last_logical = None
            self._xfade_from = None
        return self.layout

    # ----------------------------------------------------------- bucle
    def run(self):
        last = time.monotonic()
        fps_acc, fps_n, fps_t = 0.0, 0, last
        while self.running:
            t0 = time.monotonic()
            dt = min(0.2, max(0.001, t0 - last))
            last = t0
            try:
                self._frame(t0, dt)
                self.error = ""
            except Exception as e:  # noqa: BLE001
                self.error = f"{type(e).__name__}: {e}"
                traceback.print_exc()
                time.sleep(0.2)
            fps_n += 1
            if t0 - fps_t >= 1.0:
                self.actual_fps = fps_n / (t0 - fps_t)
                fps_n, fps_t = 0, t0
            if t0 - self._last_save > 1.5:
                self._last_save = t0
                try:
                    self.cfg.save()
                except OSError:
                    pass
            n = self.layout.n if self.layout else 65
            fps = max(5, min(int(self.cfg["fps"]), max_fps(n)))
            rest = 1.0 / fps - (time.monotonic() - t0)
            if rest > 0:
                time.sleep(rest)

    def _frame(self, now, dt):
        cfg = self.cfg
        self._ensure_device(now)
        L = self._ensure_layout()
        n = L.n
        mode = cfg["mode"]

        test = self.test
        if test and now - test[1] > test[2]:
            self.test = test = None

        suspended = cfg["off_on_lock"] and (self.locked or self.sleeping)
        want_on = bool(cfg["power"]) and not suspended

        # --- recursos: captura de pantalla y audio
        need_capture = want_on and mode == "sync" and not test
        if self._restart_capture:
            self._restart_capture = False
            self.capture.stop()
        if need_capture:
            self._capture_last_need = now
            if self.capture.state == "idle":
                self.capture.start()
        elif self.capture.state != "idle" and now - self._capture_last_need > 3.0:
            self.capture.stop()
            self.preview_frame = None

        need_audio = want_on and mode == "music" and not test
        if need_audio:
            self._audio_last_need = now
            dev = cfg["music_device"]
            if self.audio.state == "idle" or (self.audio.state == "running" and self.audio.device != dev) \
                    or (self.audio.state == "error" and now > self.audio.retry_at):
                self.audio.start(dev)
            self.audio.poll()
        elif self.audio.state != "idle" and now - self._audio_last_need > 3.0:
            self.audio.stop()

        # --- colores lógicos
        if test:
            colors = self._test_pattern(L, now - test[1], test[0])
        elif mode == "sync":
            colors = self._sync(L, dt)
        elif mode == "flow":
            colors = self.fx.flow(L, cfg, dt)
        elif mode == "mono":
            colors = self.fx.mono(L, cfg, dt)
        elif mode == "music":
            colors = self.fx.music(L, cfg, dt, self.audio.window(), now)
        elif mode == "race":
            colors = self.fx.race(L, cfg, dt)
        else:
            colors = np.zeros((n, 3), np.float32)
        colors = np.asarray(colors, np.float32).reshape(n, 3)

        # --- transición suave al cambiar de modo
        key = (mode, bool(test))
        if key != self._prev_mode:
            if self._last_logical is not None and len(self._last_logical) == n:
                self._xfade_from = self._last_logical.copy()
                self._xfade_t = 0.0
            self._prev_mode = key
        if self._xfade_from is not None:
            self._xfade_t += dt
            a = min(1.0, self._xfade_t / 0.5)
            colors = self._xfade_from * (1 - a) + colors * a
            if a >= 1.0:
                self._xfade_from = None
        self._last_logical = colors

        # --- encendido/apagado con fundido
        target = 1.0 if (want_on or test) else 0.0
        step = dt / 0.45
        self._fade += max(-step, min(step, target - self._fade))

        bright = 1.0 if test else cfg["brightness"] / 100.0
        gains = np.array([cfg["wb_r"], cfg["wb_g"], cfg["wb_b"]], np.float32) / 100.0
        final = np.clip(colors * (self._fade * bright) * gains, 0, 255)
        self.preview_colors = final

        if self.dev is None:
            return
        if self._fade <= 0.0 and target == 0.0:
            if now - self._last_black < 0.5:
                return
            self._last_black = now
        phys = final[L.perm][:, CHANNELS.get(cfg["color_order"], CHANNELS["RGB"])]
        data = np.rint(phys).astype(np.uint8).tobytes()
        try:
            self.dev.send(data)
        except (DeviceError, OSError) as e:
            self._close_device(f"{_('Desconectado')} ({e}); {_('reintentando…')}")
            self.next_connect = now + 1.0

    # ------------------------------------------------------ sincronización
    def _sync(self, L, dt):
        cfg = self.cfg
        n = L.n
        frame = self.capture.poll()
        if frame is None:
            prev = self._sync_prev if self._sync_prev is not None else np.zeros((n, 3), np.float32)
            self._sync_prev = prev * math.exp(-dt * 0.5)
            return self._sync_prev
        self.preview_frame = frame
        H, W = frame.shape[:2]
        region = cfg["sync_region"]

        y0, y1, x0, x1 = 0, H, 0, W
        if cfg["sync_blackborder"] or region == "movie":
            y0, y1, x0, x1 = self.border.update(frame)
        self.border_crop = (y0, y1, x0, x1, H, W)
        ch, cw = y1 - y0, x1 - x0
        if region == "top":
            y1 = y0 + ch // 2
        elif region == "bottom":
            y0 = y1 - ch // 2
        elif region == "left":
            x1 = x0 + cw // 2
        elif region == "right":
            x0 = x1 - cw // 2
        ch, cw = max(2, y1 - y0), max(2, x1 - x0)

        depth = cfg["sync_depth"] / 100.0
        if region == "movie":
            depth = max(depth, 0.33)
        r = L.rects(depth)
        px0 = np.clip(x0 + np.floor(r[:, 0] * cw).astype(int), 0, W - 1)
        px1 = np.clip(x0 + np.ceil(r[:, 2] * cw).astype(int), px0 + 1, W)
        py0 = np.clip(y0 + np.floor(r[:, 1] * ch).astype(int), 0, H - 1)
        py1 = np.clip(y0 + np.ceil(r[:, 3] * ch).astype(int), py0 + 1, H)

        f = frame.astype(np.float32)
        S = np.zeros((H + 1, W + 1, 3), np.float32)
        S[1:, 1:] = f.cumsum(0).cumsum(1)
        tot = S[py1, px1] - S[py0, px1] - S[py1, px0] + S[py0, px0]
        area = ((py1 - py0) * (px1 - px0)).astype(np.float32)[:, None]
        c = tot / area

        g = cfg["sync_gamma"] / 10.0
        if abs(g - 1.0) > 0.01:
            c = 255.0 * (np.clip(c, 0, 255) / 255.0) ** g
        sat = cfg["sync_saturation"] / 100.0
        if abs(sat - 1.0) > 0.01:
            gray = c.mean(axis=1, keepdims=True)
            c = np.clip(gray + (c - gray) * sat, 0, 255)
        lvl = cfg["sync_minlevel"] * 2.55
        c[c.max(axis=1) < lvl] = 0

        if cfg["sync_smooth_enabled"] and self._sync_prev is not None and len(self._sync_prev) == n:
            s = cfg["sync_smooth"] / 100.0
            if region == "movie":
                s = min(0.97, s + 0.15)
            keep = (s * 0.94) ** (dt * 30.0)
            c = self._sync_prev * keep + c * (1 - keep)
        self._sync_prev = c
        return c

    # ------------------------------------------------------------ pruebas
    def _test_pattern(self, L, t, kind):
        n = L.n
        out = np.zeros((n, 3), np.float32)
        if kind == "sides":
            cols = {0: (255, 0, 0), 1: (0, 255, 0), 2: (0, 0, 255), 3: (255, 255, 255)}
            for code, col in cols.items():
                out[L.side == code] = col
            if int(t * 3) % 2 == 0:                  # primer LED físico parpadea en blanco
                out[L.perm[0]] = (255, 255, 255)
            return out
        if kind == "sweep":
            k = int(t * 12) % n                         # recorre en orden físico
            out[L.perm[k]] = (255, 255, 255)
            if k > 0:
                out[L.perm[k - 1]] = (80, 80, 80)
            return out
        if kind == "rgb":
            seq = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
            out[:] = seq[int(t / 1.5) % 4]
            return out
        return out
