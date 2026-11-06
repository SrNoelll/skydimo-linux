"""Captura de audio del sistema (lo que suena) con GStreamer + PipeWire/Pulse."""

import json
import subprocess
import threading
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from .i18n import _
import numpy as np  # noqa: E402

RATE = 44100
RING = 4096


def list_sources():
    """[(valor, etiqueta)] de fuentes de audio disponibles."""
    out = [("@DEFAULT_MONITOR@", _("Lo que suena en el PC (salida predeterminada)")),
           ("@DEFAULT_SOURCE@", _("Micrófono predeterminado"))]
    try:
        txt = subprocess.run(["pactl", "-f", "json", "list", "sources"],
                             capture_output=True, text=True, timeout=3).stdout
        for s in json.loads(txt or "[]"):
            name = s.get("name")
            desc = s.get("description") or name
            if name:
                out.append((name, desc))
    except Exception:  # noqa: BLE001
        pass
    return out


class AudioCapture:
    def __init__(self):
        self.state = "idle"
        self.message = ""
        self.device = None
        self._pipeline = None
        self._lock = threading.Lock()
        self._buf = np.zeros(RING, np.float32)
        self._last = 0.0
        self.retry_at = 0.0

    def start(self, device):
        self.stop()
        self.device = device
        try:
            desc = (f'pulsesrc device="{device}" client-name=Ambiluz '
                    f'buffer-time=40000 latency-time=10000 ! audioconvert ! audioresample ! '
                    f'audio/x-raw,format=F32LE,channels=1,rate={RATE} ! '
                    f'appsink name=sink emit-signals=true sync=false max-buffers=20 drop=true')
            p = Gst.parse_launch(desc)
            sink = p.get_by_name("sink")
            sink.connect("new-sample", self._on_sample)
            if p.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError(_("no se pudo abrir la fuente de audio"))
            self._pipeline = p
            self.state = "running"
            self.message = _("Escuchando audio")
        except Exception as e:  # noqa: BLE001
            self.state = "error"
            self.message = f"Audio: {e}"
            self.retry_at = time.monotonic() + 5

    def _on_sample(self, sink):
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK
        buf = sample.get_buffer()
        ok, info = buf.map(Gst.MapFlags.READ)
        if ok:
            try:
                x = np.frombuffer(info.data, np.float32).copy()
            finally:
                buf.unmap(info)
            with self._lock:
                if len(x) >= RING:
                    self._buf = x[-RING:]
                else:
                    self._buf = np.concatenate((self._buf[len(x):], x))
                self._last = time.monotonic()
        return Gst.FlowReturn.OK

    def window(self, n=2048):
        with self._lock:
            if time.monotonic() - self._last > 0.5:
                return np.zeros(n, np.float32)
            return self._buf[-n:].copy()

    def poll(self):
        p = self._pipeline
        if p is None:
            return
        msg = p.get_bus().pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if msg is not None:
            text = _("fin de la fuente")
            if msg.type == Gst.MessageType.ERROR:
                text = msg.parse_error()[0].message
            self.stop()
            self.state = "error"
            self.message = f"Audio: {text}"
            self.retry_at = time.monotonic() + 3

    def stop(self):
        p, self._pipeline = self._pipeline, None
        if p is not None:
            p.set_state(Gst.State.NULL)
        self.state = "idle"
        self.message = ""
