"""Captura de pantalla en Wayland/X11 vía xdg-desktop-portal + PipeWire.

Funciona en KDE Plasma, GNOME, Hyprland, Sway, etc. La primera vez el
sistema muestra un diálogo para elegir la pantalla; se guarda un
"restore_token" para no volver a preguntar.
"""

import concurrent.futures
import os
import re
import subprocess
import queue
import secrets
import threading

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gio, GLib, Gst, GstApp  # noqa: E402

from .i18n import _
import numpy as np  # noqa: E402

PORTAL = "org.freedesktop.portal.Desktop"
PPATH = "/org/freedesktop/portal/desktop"
SC_IFACE = "org.freedesktop.portal.ScreenCast"


class GLibWorker:
    """Hilo con su propio contexto GLib para recibir señales D-Bus."""

    def __init__(self):
        self.ctx = GLib.MainContext.new()
        self.loop = GLib.MainLoop.new(self.ctx, False)
        ready = threading.Event()

        def run():
            self.ctx.push_thread_default()
            ready.set()
            self.loop.run()

        self.thread = threading.Thread(target=run, name="glib", daemon=True)
        self.thread.start()
        ready.wait()

    def call(self, fn, *args, timeout=10):
        fut = concurrent.futures.Future()

        def cb():
            try:
                fut.set_result(fn(*args))
            except Exception as e:  # noqa: BLE001
                fut.set_exception(e)
            return False

        src = GLib.idle_source_new()
        src.set_callback(cb)
        src.attach(self.ctx)
        return fut.result(timeout)


class CaptureError(Exception):
    pass


class ScreenCapture:
    WIDTH = 160

    def __init__(self, worker, cfg):
        self.worker = worker
        self.cfg = cfg
        self.state = "idle"          # idle | starting | running | error
        self.message = ""
        self.frame = None
        self.frame_count = 0
        self._lock = threading.Lock()
        self._pipeline = None
        self._sink = None
        self._fd = None
        self._session = None
        self._gen = 0
        self._bus = None

    # ------------------------------------------------------------ portal
    def _dbus(self):
        if self._bus is None:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return self._bus

    def _request(self, method, build_args):
        bus = self._dbus()
        sender = bus.get_unique_name()[1:].replace(".", "_")
        token = "ambiluz" + secrets.token_hex(6)
        path = f"{PPATH}/request/{sender}/{token}"
        q = queue.Queue()

        def on_response(_conn, _sender, _path, _iface, _sig, params, *_ud):
            q.put(params.unpack())

        sub = self.worker.call(
            bus.signal_subscribe, PORTAL, "org.freedesktop.portal.Request",
            "Response", path, None, Gio.DBusSignalFlags.NONE, on_response)
        try:
            bus.call_sync(PORTAL, PPATH, SC_IFACE, method, build_args(token),
                          None, Gio.DBusCallFlags.NONE, -1, None)
            try:
                code, results = q.get(timeout=300)
            except queue.Empty:
                raise CaptureError(_("El diálogo de captura no respondió"))
        finally:
            try:
                self.worker.call(bus.signal_unsubscribe, sub)
            except Exception:  # noqa: BLE001
                pass
        if code == 1:
            raise CaptureError(_("Permiso de captura cancelado"))
        if code != 0:
            raise CaptureError(_("El portal rechazó la captura de pantalla"))
        return results

    def _open_session(self):
        V = GLib.Variant
        res = self._request("CreateSession", lambda tok: V("(a{sv})", ({
            "handle_token": V("s", tok),
            "session_handle_token": V("s", "ambiluz" + secrets.token_hex(6)),
        },)))
        session = res["session_handle"]
        self._session = session

        restore = self.cfg["restore_token"] or ""

        def select_args(tok):
            opts = {
                "handle_token": V("s", tok),
                "types": V("u", 1),            # monitor
                "multiple": V("b", False),
                "cursor_mode": V("u", 1),      # oculto
                "persist_mode": V("u", 2),     # recordar hasta revocar
            }
            if restore:
                opts["restore_token"] = V("s", restore)
            return V("(oa{sv})", (session, opts))

        self._request("SelectSources", select_args)
        res = self._request("Start", lambda tok: V("(osa{sv})", (
            session, "", {"handle_token": V("s", tok)})))
        streams = res.get("streams") or []
        if not streams:
            raise CaptureError(_("No se seleccionó ninguna pantalla"))
        if res.get("restore_token"):
            self.cfg.set("restore_token", res["restore_token"])
        node, props = streams[0]
        size = props.get("size") or (1920, 1080)

        bus = self._dbus()
        ret, fdlist = bus.call_with_unix_fd_list_sync(
            PORTAL, PPATH, SC_IFACE, "OpenPipeWireRemote",
            V("(oa{sv})", (session, {})), GLib.VariantType("(h)"),
            Gio.DBusCallFlags.NONE, -1, None, None)
        fd = fdlist.get(ret.unpack()[0])
        return fd, int(node), size

    def _close_session(self):
        if self._session:
            try:
                self._dbus().call_sync(PORTAL, self._session, "org.freedesktop.portal.Session",
                                       "Close", None, None, Gio.DBusCallFlags.NONE, 2000, None)
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    # ---------------------------------------------------------- pipeline
    def _pipewire_source(self, fd, node):
        src = Gst.ElementFactory.make("pipewiresrc")
        if src is None:
            raise CaptureError(_("Falta el plugin pipewiresrc (gst-plugin-pipewire)"))
        src.set_property("fd", fd)
        src.set_property("path", str(node))
        src.set_property("do-timestamp", True)
        for prop, val in (("keepalive-time", 1000), ("always-copy", False)):
            if src.find_property(prop) is not None:
                src.set_property(prop, val)
        return src

    # ------------------------------------------------------------- X11
    @staticmethod
    def is_x11():
        st = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if st == "x11":
            return True
        return st != "wayland" and not os.environ.get("WAYLAND_DISPLAY") and bool(os.environ.get("DISPLAY"))

    @staticmethod
    def x11_monitors():
        """[(name, x, y, w, h, primary)] from xrandr."""
        mons = []
        try:
            txt = subprocess.run(["xrandr", "--listmonitors"], capture_output=True,
                                 text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            return mons
        for line in txt.splitlines():
            m = re.match(r"\s*\d+:\s+\+?(\*?)(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(\d+)\+(\d+)", line)
            if m:
                mons.append((m.group(2), int(m.group(5)), int(m.group(6)),
                             int(m.group(3)), int(m.group(4)), m.group(1) == "*"))
        return mons

    def _x11_source(self):
        src = Gst.ElementFactory.make("ximagesrc")
        if src is None:
            raise CaptureError("GStreamer ximagesrc plugin missing (gst-plugins-good)")
        src.set_property("use-damage", False)
        src.set_property("show-pointer", False)
        mons = self.x11_monitors()
        if mons:
            idx = int(self.cfg["x11_monitor"])
            if idx < 0 or idx >= len(mons):
                idx = next((i for i, m in enumerate(mons) if m[5]), 0)
            name, x, y, w, h, _p = mons[idx]
            src.set_property("startx", x)
            src.set_property("starty", y)
            src.set_property("endx", x + w - 1)
            src.set_property("endy", y + h - 1)
            return src, (w, h), name
        return src, (1920, 1080), "X11"

    def forget_screen(self):
        if self.is_x11():
            n = max(1, len(self.x11_monitors()))
            cur = int(self.cfg["x11_monitor"])
            self.cfg.set("x11_monitor", (cur + 1) % n if cur >= 0 else 1 % n)
        else:
            self.cfg.set("restore_token", "")

    def _build_pipeline(self, src, size):
        w, h = size
        W = self.WIDTH
        H = max(8, int(round(W * h / max(1, w) / 2)) * 2)
        p = Gst.Pipeline.new("ambiluz-capture")
        rate = Gst.ElementFactory.make("videorate")
        rate.set_property("drop-only", True)
        rate.set_property("max-rate", 30)
        scale = Gst.ElementFactory.make("videoscale")
        scale.set_property("method", 0)            # vecino más cercano: barato
        scale.set_property("add-borders", False)
        caps1 = Gst.ElementFactory.make("capsfilter")
        caps1.set_property("caps", Gst.Caps.from_string(
            f"video/x-raw,width={W},height={H},pixel-aspect-ratio=1/1"))
        conv = Gst.ElementFactory.make("videoconvert")
        caps2 = Gst.ElementFactory.make("capsfilter")
        caps2.set_property("caps", Gst.Caps.from_string("video/x-raw,format=RGB"))
        sink = Gst.ElementFactory.make("appsink")
        sink.set_property("max-buffers", 1)
        sink.set_property("drop", True)
        sink.set_property("sync", False)
        for e in (src, rate, scale, caps1, conv, caps2, sink):
            p.add(e)
        src.link(rate)
        rate.link(scale)
        scale.link(caps1)
        caps1.link(conv)
        conv.link(caps2)
        caps2.link(sink)
        return p, sink

    # --------------------------------------------------------------- API
    def start(self):
        with self._lock:
            if self.state in ("starting", "running"):
                return
            self.state = "starting"
            self.message = _("Esperando permiso para capturar la pantalla…")
            self._gen += 1
            gen = self._gen
        threading.Thread(target=self._start_thread, args=(gen,), daemon=True).start()

    def _start_thread(self, gen):
        try:
            label = ""
            if self.is_x11():
                fd = None
                src, size, label = self._x11_source()
            else:
                fd, node, size = self._open_session()
                src = self._pipewire_source(fd, node)
            pipeline, sink = self._build_pipeline(src, size)
            with self._lock:
                if gen != self._gen:            # se paró mientras tanto
                    raise CaptureError("cancelado")
                self._fd = fd
                self._pipeline = pipeline
                self._sink = sink
            if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise CaptureError(_("No se pudo iniciar la captura (PipeWire)"))
            with self._lock:
                if gen == self._gen:
                    self.state = "running"
                    self.message = f"{_('Capturando pantalla')} {label} ({size[0]}×{size[1]})".replace("  ", " ")
        except Exception as e:  # noqa: BLE001
            with self._lock:
                stale = gen != self._gen
            self._teardown()
            if not stale:
                with self._lock:
                    self.state = "error"
                    self.message = str(e)

    def _teardown(self):
        with self._lock:
            p, self._pipeline, self._sink = self._pipeline, None, None
            fd, self._fd = self._fd, None
        if p is not None:
            p.set_state(Gst.State.NULL)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        self._close_session()

    def stop(self):
        with self._lock:
            self._gen += 1
        self._teardown()
        with self._lock:
            self.state = "idle"
            self.message = ""
            self.frame = None

    def poll(self):
        """Devuelve el último fotograma (H, W, 3) uint8 o None."""
        with self._lock:
            p, sink = self._pipeline, self._sink
        if p is None or sink is None:
            return self.frame
        bus = p.get_bus()
        msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if msg is not None:
            if msg.type == Gst.MessageType.ERROR:
                err, _dbg = msg.parse_error()
                text = f"{_('La captura se detuvo')}: {err.message}"
            else:
                text = _("La captura de pantalla se detuvo")
            self.stop()
            self.state = "error"
            self.message = text
            return None
        sample = sink.try_pull_sample(0)
        if sample is not None:
            buf = sample.get_buffer()
            s = sample.get_caps().get_structure(0)
            w, h = s.get_value("width"), s.get_value("height")
            ok, info = buf.map(Gst.MapFlags.READ)
            if ok:
                try:
                    data = np.frombuffer(info.data, np.uint8)
                    stride = len(data) // h
                    img = data[: stride * h].reshape(h, stride)[:, : w * 3].reshape(h, w, 3).copy()
                finally:
                    buf.unmap(info)
                self.frame = img
                self.frame_count += 1
        return self.frame
