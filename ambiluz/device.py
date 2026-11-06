"""Comunicación serie con controladores Skydimo (CH340, 115200 8N1).

Protocolo (variante Adalight):
    'A' 'd' 'a' 0x00 count_hi count_lo  R G B  R G B ...
Consulta de modelo: se envía "Moni-A" y responde "MODELO,serie\\r\\n".
El controlador apaga los LEDs si deja de recibir tramas, así que hay que
reenviar continuamente.
"""

import errno
import fcntl
import glob
import os
import select
import termios
import time

from .i18n import _

SERIAL_VID = "1a86"
SERIAL_PIDS = {"7523"}
BAUD = 115200


def _usb_ids(tty):
    p = os.path.realpath(f"/sys/class/tty/{tty}/device")
    for _ in range(6):
        vid = os.path.join(p, "idVendor")
        if os.path.exists(vid):
            try:
                with open(vid) as f:
                    v = f.read().strip()
                with open(os.path.join(p, "idProduct")) as f:
                    pr = f.read().strip()
                return v, pr
            except OSError:
                return None, None
        p = os.path.dirname(p)
    return None, None


def list_ports():
    out = []
    for dev in sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")):
        vid, pid = _usb_ids(os.path.basename(dev))
        out.append({
            "path": dev,
            "vid": vid,
            "pid": pid,
            "likely": vid == SERIAL_VID and pid in SERIAL_PIDS,
        })
    return out


class DeviceError(Exception):
    pass


class SerialDevice:
    def __init__(self, path):
        self.path = path
        self.fd = None
        self.model = None
        self.serial = None

    # ------------------------------------------------------------------
    def open(self):
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        except PermissionError as e:
            raise DeviceError(
                f"{_('Sin permiso para')} {self.path}. "
                + _("Ejecuta el instalador para añadir la regla udev o añade tu usuario al grupo del puerto.")) from e
        except OSError as e:
            raise DeviceError(f"{_('No se puede abrir')} {self.path}: {e.strerror}") from e
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise DeviceError(f"{self.path} {_('está en uso por otro programa')}")
        try:
            fcntl.ioctl(fd, termios.TIOCEXCL)
        except OSError:
            pass
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0                                   # iflag
        attrs[1] = 0                                   # oflag
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0                                   # lflag
        attrs[4] = attrs[5] = termios.B115200
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        termios.tcflush(fd, termios.TCIOFLUSH)
        self.fd = fd

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    # ------------------------------------------------------------------
    def query(self, tries=3, timeout=0.35):
        """Pregunta el modelo. Devuelve (modelo, serie_hex) o (None, None)."""
        for _ in range(tries):
            termios.tcflush(self.fd, termios.TCIFLUSH)
            self._write_all(b"Moni-A")
            buf = b""
            end = time.monotonic() + timeout
            while time.monotonic() < end and b"\n" not in buf:
                r, _, _ = select.select([self.fd], [], [], 0.03)
                if r:
                    try:
                        buf += os.read(self.fd, 128)
                    except BlockingIOError:
                        pass
            if b"," in buf:
                model, _, rest = buf.partition(b",")
                serial = rest.split(b"\r")[0].split(b"\n")[0]
                self.model = model.decode("ascii", "replace").strip()
                self.serial = serial.hex().upper()
                return self.model, self.serial
            time.sleep(0.1)
        return None, None

    # ------------------------------------------------------------------
    def _write_all(self, data, timeout=0.5):
        view = memoryview(data)
        end = time.monotonic() + timeout
        while view:
            try:
                n = os.write(self.fd, view)
                view = view[n:]
            except BlockingIOError:
                pass
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EINTR):
                    pass
                else:
                    raise DeviceError(f"{_('Error de escritura')}: {e.strerror}") from e
            if view:
                left = end - time.monotonic()
                if left <= 0:
                    raise DeviceError(_("Tiempo de escritura agotado"))
                select.select([], [self.fd], [], left)

    def send(self, rgb_bytes):
        n = len(rgb_bytes) // 3
        header = bytes((0x41, 0x64, 0x61, 0x00, (n >> 8) & 0xFF, n & 0xFF))
        self._write_all(header + bytes(rgb_bytes))


def max_fps(n_leds):
    """FPS máximos que caben en 115200 baudios (10 bits por byte), con margen."""
    frame = 6 + 3 * max(1, n_leds)
    return max(5, int(BAUD / 10 / frame * 0.85))
