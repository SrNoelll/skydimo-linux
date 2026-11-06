"""Ambiluz: Skydimo monitor ambient-light controller for Linux.

Usage:
  ambiluz                      open the app (or raise the window if already running)
  ambiluz --minimized          start hidden in the system tray
  ambiluz --on | --off | --toggle
  ambiluz --mode sync|flow|mono|music|race
  ambiluz --brightness 70
  ambiluz --color ff0000       (switch to solid-color mode with that color)
  ambiluz --probe              print the detected device and exit
  ambiluz --status             print the state of the running instance
"""

import argparse
import json
import os
import signal
import sys

from . import __version__

MODES = ["sync", "flow", "mono", "music", "race"]


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="ambiluz", description="Skydimo monitor ambient light for Linux (screen sync, music, effects)")
    ap.add_argument("--minimized", action="store_true", help="start hidden in the system tray")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    g.add_argument("--toggle", action="store_true")
    ap.add_argument("--mode", choices=MODES)
    ap.add_argument("--version", action="version", version=f"ambiluz {__version__}")
    ap.add_argument("--brightness", type=int)
    ap.add_argument("--color", help="hex color, e.g. ff8800")
    ap.add_argument("--probe", action="store_true", help="detect the device and exit")
    ap.add_argument("--quit", action="store_true", help="quit the running instance")
    ap.add_argument("--status", action="store_true", help="print the running instance status as JSON")
    return ap.parse_args(argv)


def commands_from(args):
    cmd = {}
    if args.on:
        cmd["power"] = True
    if args.off:
        cmd["power"] = False
    if args.toggle:
        cmd["toggle"] = True
    if args.mode:
        cmd["mode"] = args.mode
        cmd["power"] = True
    if args.brightness is not None:
        cmd["brightness"] = max(0, min(100, args.brightness))
    if args.color:
        c = args.color.lstrip("#")
        if len(c) == 6:
            cmd["mono_color"] = "#" + c.lower()
            cmd["mode"] = "mono"
            cmd["power"] = True
    if args.quit:
        cmd["quit"] = True
    return cmd


def apply_commands(cfg, cmd):
    for k in ("power", "mode", "brightness", "mono_color"):
        if k in cmd:
            cfg.set(k, cmd[k])
    if cmd.get("toggle"):
        cfg.set("power", not cfg["power"])


def probe():
    from .device import DeviceError, SerialDevice, list_ports
    from . import models
    ports = list_ports()
    if not ports:
        print("No USB serial ports found. Is the LED strip plugged in?")
        return 1
    for p in ports:
        print(f"{p['path']}  vid={p['vid']} pid={p['pid']}{'  <- likely Skydimo (CH340)' if p['likely'] else ''}")
        d = SerialDevice(p["path"])
        try:
            d.open()
            m, s = d.query()
            info = models.lookup(m)
            print(f"   model: {m}  serial: {s}  " + (f"LEDs: {sum(info[1])} {info[1]}" if info
                                                  else ("(unknown model - please open an issue)" if m else "(no answer)")))
        except DeviceError as e:
            print("  ", e)
        finally:
            d.close()
    return 0


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.probe:
        return probe()

    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setDesktopFileName("ambiluz")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Ambiluz")
    app.setQuitOnLastWindowClosed(False)

    cmd = commands_from(args)
    server_name = f"ambiluz-{os.getuid()}"

    # ¿Ya hay una instancia? Enviarle la orden y salir.
    sock = QLocalSocket()
    sock.connectToServer(server_name)
    if sock.waitForConnected(400):
        msg = dict(cmd)
        if args.status:
            msg["status"] = True
        elif not cmd and not args.minimized:
            msg["show"] = True
        sock.write(QByteArray(json.dumps(msg).encode()))
        sock.flush()
        sock.waitForBytesWritten(1000)
        if args.status:
            data = b""
            while sock.waitForReadyRead(1500):
                data += bytes(sock.readAll())
                if data.endswith(b"\n"):
                    break
            print(data.decode().strip())
        sock.disconnectFromServer()
        return 0
    if cmd.get("quit") or args.status:
        if args.status:
            print("Ambiluz is not running")
        return 0

    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)

    from .config import Config
    from . import i18n
    cfg = Config()
    i18n.set_lang(cfg["language"])
    from .engine import Engine
    from .gui import ICON_PATH, STYLE, MainWindow, dark_palette

    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(ICON_PATH))

    apply_commands(cfg, cmd)
    engine = Engine(cfg)
    engine.start()

    quitting = {"done": False}

    def do_quit():
        if quitting["done"]:
            return
        quitting["done"] = True
        engine.shutdown()
        app.quit()

    win = MainWindow(cfg, engine, do_quit)

    server = QLocalServer()
    QLocalServer.removeServer(server_name)
    server.listen(server_name)

    def on_conn():
        c = server.nextPendingConnection()

        def read():
            try:
                data = json.loads(bytes(c.readAll()).decode() or "{}")
            except ValueError:
                return
            if data.get("quit"):
                do_quit()
                return
            if data.get("status"):
                fr = engine.preview_frame
                st = {
                    "device": engine.device_msg, "model": engine.effective_model(),
                    "leds": engine.layout.n if engine.layout else 0,
                    "power": cfg["power"], "mode": cfg["mode"], "brightness": cfg["brightness"],
                    "fps": round(engine.actual_fps, 1), "error": engine.error,
                    "capture": [engine.capture.state, engine.capture.message, engine.capture.frame_count],
                    "frame": None if fr is None else [list(fr.shape), float(fr.mean())],
                    "audio": [engine.audio.state, engine.audio.message],
                    "locked": engine.locked,
                }
                c.write(QByteArray((json.dumps(st, ensure_ascii=False) + "\n").encode()))
                c.flush()
                return
            apply_commands(cfg, data)
            win.refresh()
            if data.get("show"):
                win.show_raise()

        c.readyRead.connect(read)

    server.newConnection.connect(on_conn)

    if not args.minimized or win.tray is None:
        win.show()

    signal.signal(signal.SIGINT, lambda *_: do_quit())
    signal.signal(signal.SIGTERM, lambda *_: do_quit())
    from PySide6.QtCore import QTimer
    keep = QTimer()
    keep.timeout.connect(lambda: None)    # deja que Python procese señales
    keep.start(300)

    app.aboutToQuit.connect(do_quit)
    rc = app.exec()
    return rc


if __name__ == "__main__":
    sys.exit(main())
