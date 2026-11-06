"""Interfaz gráfica (PySide6)."""

import os
import shutil
import sys

from .i18n import LANGUAGE_CHOICES, _
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QIcon, QImage, QPainter,
                           QPainterPath, QPalette, QPen, QRadialGradient)
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QComboBox,
                               QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QMainWindow, QMenu,
                               QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
                               QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

from . import models
from .audio import list_sources
from .device import list_ports
from .effects import (FLOW_EFFECTS, MONO_EFFECTS, MUSIC_STYLES, PALETTES, RACE_STYLES)
from .layout import BOTTOM, LEFT, RIGHT, TOP

ICON_PATH = os.path.join(os.path.dirname(__file__), "icon.svg")
ACCENT = "#7c5cff"

MODES = [
    ("sync", _("Sincronizar pantalla"), "🖥"),
    ("flow", _("Flujo"), "🌈"),
    ("mono", _("Monocromo"), "🎨"),
    ("music", _("Música"), "🎵"),
    ("race", _("Carrera de luces"), "🏇"),
]
MODE_NAMES = {m: name for m, name, _ in MODES}

SWATCHES = ["#ff0000", "#ff6a00", "#ffb000", "#ffee00", "#7dff00", "#00ff40",
            "#00ffc8", "#00b4ff", "#0040ff", "#7a00ff", "#ff00d0", "#ff0060",
            "#ffffff", "#ffd8a8", "#ff8a2a"]

STYLE = f"""
QMainWindow, QWidget#central {{ background: #0f1016; }}
QWidget {{ color: #e6e7ee; font-size: 10.5pt; }}
QLabel#title {{ font-size: 17pt; font-weight: 700; }}
QLabel#sub {{ color: #8b8fa3; }}
QListWidget#sidebar {{ background: #15161d; border: none; border-radius: 14px; padding: 6px; outline: 0; }}
QListWidget#sidebar::item {{ padding: 11px 12px; border-radius: 9px; margin: 2px 0; color: #c9cbd6; }}
QListWidget#sidebar::item:hover {{ background: #20222c; }}
QListWidget#sidebar::item:selected {{ background: {ACCENT}; color: white; }}
QGroupBox {{ background: #15161d; border: 1px solid #23252f; border-radius: 12px; margin-top: 18px; padding: 14px 12px 10px 12px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; top: 2px; padding: 0 4px; color: #9aa0b4; font-weight: 600; }}
QSlider::groove:horizontal {{ height: 6px; background: #2a2c38; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QPushButton {{ background: #232530; border: 1px solid #30333f; border-radius: 9px; padding: 7px 12px; }}
QPushButton:hover {{ background: #2c2f3c; }}
QPushButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QPushButton#power {{ font-weight: 700; padding: 8px 18px; border-radius: 18px; }}
QPushButton#power:checked {{ background: #22c55e; border-color: #22c55e; color: #08130c; }}
QComboBox, QSpinBox {{ background: #232530; border: 1px solid #30333f; border-radius: 8px; padding: 5px 8px; }}
QComboBox QAbstractItemView {{ background: #1b1c24; selection-background-color: {ACCENT}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; }}
QScrollArea {{ border: none; background: transparent; }}
QStatusBar {{ color: #8b8fa3; }}
"""


def dark_palette():
    p = QPalette()
    for role, col in [(QPalette.Window, "#0f1016"), (QPalette.WindowText, "#e6e7ee"),
                      (QPalette.Base, "#1b1c24"), (QPalette.AlternateBase, "#20222c"),
                      (QPalette.Text, "#e6e7ee"), (QPalette.Button, "#232530"),
                      (QPalette.ButtonText, "#e6e7ee"), (QPalette.Highlight, ACCENT),
                      (QPalette.HighlightedText, "#ffffff"), (QPalette.ToolTipBase, "#1b1c24"),
                      (QPalette.ToolTipText, "#e6e7ee")]:
        p.setColor(role, QColor(col))
    return p


# ---------------------------------------------------------------------------
class StripPreview(QWidget):
    """Monitor dibujado con los LEDs en vivo y la imagen capturada."""

    def __init__(self, engine, cfg):
        super().__init__()
        self.engine, self.cfg = engine, cfg
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        t = QTimer(self)
        t.timeout.connect(self.update)
        t.start(33)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#0b0c11"))
        L = self.engine.layout
        cols = self.engine.preview_colors
        frame = self.engine.preview_frame if self.cfg["mode"] == "sync" else None

        aspect = 16 / 9
        if frame is not None:
            aspect = frame.shape[1] / frame.shape[0]
        margin = 34
        aw, ah = self.width() - 2 * margin, self.height() - 2 * margin - 22
        mw = min(aw, ah * aspect)
        mh = mw / aspect
        mon = QRectF((self.width() - mw) / 2, margin, mw, mh)

        # glow
        if L is not None and len(cols) == L.n:
            p.setPen(Qt.NoPen)
            off = 16
            for i in range(L.n):
                c = cols[i]
                if c.max() < 2:
                    continue
                pt = self._led_point(mon, L, i, off)
                rad = max(mon.width(), mon.height()) * 0.09 + 10
                g = QRadialGradient(pt, rad)
                q = QColor(int(c[0]), int(c[1]), int(c[2]), 150)
                g.setColorAt(0.0, q)
                q2 = QColor(q)
                q2.setAlpha(0)
                g.setColorAt(1.0, q2)
                p.setBrush(g)
                p.drawEllipse(pt, rad, rad)

        # soporte
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2a2c38"))
        p.drawRect(QRectF(mon.center().x() - 8, mon.bottom(), 16, 16))
        p.drawRoundedRect(QRectF(mon.center().x() - 46, mon.bottom() + 14, 92, 7), 3, 3)

        # pantalla
        path = QPainterPath()
        path.addRoundedRect(mon, 6, 6)
        p.setBrush(QColor("#191b24"))
        p.setPen(QPen(QColor("#34374a"), 3))
        p.drawPath(path)
        if frame is not None:
            h, w = frame.shape[:2]
            img = QImage(np.ascontiguousarray(frame).data, w, h, 3 * w, QImage.Format_RGB888).copy()
            p.save()
            p.setClipPath(path)
            p.drawImage(mon.adjusted(2, 2, -2, -2), img)
            bc = self.engine.border_crop
            if bc and (bc[0] > 0 or bc[2] > 0):
                y0, y1, x0, x1, H, W = bc
                r = mon.adjusted(2, 2, -2, -2)
                crop = QRectF(r.left() + r.width() * x0 / W, r.top() + r.height() * y0 / H,
                              r.width() * (x1 - x0) / W, r.height() * (y1 - y0) / H)
                p.setPen(QPen(QColor(ACCENT), 1.5, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRect(crop)
            p.restore()
        else:
            p.setPen(QColor("#4b4f63"))
            p.drawText(mon, Qt.AlignCenter, MODE_NAMES.get(self.cfg["mode"], ""))

        # LEDs
        if L is not None and len(cols) == L.n:
            p.setPen(Qt.NoPen)
            for i in range(L.n):
                c = cols[i]
                pt = self._led_point(mon, L, i, 9)
                p.setBrush(QColor(int(c[0]), int(c[1]), int(c[2])) if c.max() >= 2 else QColor("#262833"))
                p.drawEllipse(pt, 3.2, 3.2)
        p.end()

    @staticmethod
    def _led_point(mon, L, i, off):
        x, y = L.pos[i]
        s = L.side[i]
        px = mon.left() + x * mon.width()
        py = mon.top() + y * mon.height()
        if s == LEFT:
            px -= off
        elif s == RIGHT:
            px += off
        elif s == TOP:
            py -= off
        elif s == BOTTOM:
            py += off
        return QPointF(px, py)


# ---------------------------------------------------------------------------
class Binder:
    """Crea controles enlazados a claves de configuración."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.refreshers = []

    def slider(self, key, lo, hi, fmt=lambda v: f"{v}%", on_change=None):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        lab = QLabel()
        lab.setMinimumWidth(52)
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def changed(v):
            self.cfg.set(key, int(v))
            lab.setText(fmt(v))
            if on_change:
                on_change(v)

        def refresh():
            s.blockSignals(True)
            s.setValue(int(self.cfg[key]))
            s.blockSignals(False)
            lab.setText(fmt(int(self.cfg[key])))

        s.valueChanged.connect(changed)
        refresh()
        self.refreshers.append(refresh)
        h.addWidget(s, 1)
        h.addWidget(lab)
        return w

    def combo(self, key, options, on_change=None):
        c = QComboBox()
        for val, label in options:
            c.addItem(label, val)

        def changed(_i):
            self.cfg.set(key, c.currentData())
            if on_change:
                on_change(c.currentData())

        def refresh():
            c.blockSignals(True)
            i = c.findData(self.cfg[key])
            c.setCurrentIndex(max(0, i))
            c.blockSignals(False)

        c.currentIndexChanged.connect(changed)
        refresh()
        self.refreshers.append(refresh)
        return c

    def check(self, key, text, on_change=None):
        b = QCheckBox(text)

        def changed(v):
            self.cfg.set(key, bool(v))
            if on_change:
                on_change(bool(v))

        def refresh():
            b.blockSignals(True)
            b.setChecked(bool(self.cfg[key]))
            b.blockSignals(False)

        b.toggled.connect(changed)
        refresh()
        self.refreshers.append(refresh)
        return b

    def choice_grid(self, key, options, cols=3):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(8)
        grp = QButtonGroup(w)
        grp.setExclusive(True)
        buttons = {}
        for i, (val, label) in enumerate(options):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setMinimumHeight(38)
            grp.addButton(b)
            buttons[val] = b
            g.addWidget(b, i // cols, i % cols)
            b.clicked.connect(lambda _=False, v=val: self.cfg.set(key, v))

        def refresh():
            b = buttons.get(self.cfg[key])
            if b:
                b.setChecked(True)

        refresh()
        self.refreshers.append(refresh)
        return w

    def color(self, key):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        btn = QPushButton(_("Elegir color…"))
        btn.setMinimumHeight(38)
        top.addWidget(btn, 1)
        v.addLayout(top)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, hexc in enumerate(SWATCHES):
            s = QPushButton()
            s.setFixedSize(30, 30)
            s.setStyleSheet(f"background:{hexc}; border-radius:15px; border:2px solid #2a2c38;")
            s.clicked.connect(lambda _=False, c=hexc: (self.cfg.set(key, c), refresh()))
            grid.addWidget(s, i // 8, i % 8)
        v.addLayout(grid)

        def refresh():
            c = self.cfg[key]
            q = QColor(c)
            fg = "#000" if q.lightness() > 140 else "#fff"
            btn.setText(f"{_('Color')}: {c.upper()}  ({_('elegir…')})")
            btn.setStyleSheet(f"background:{c}; color:{fg}; border-radius:9px; font-weight:600;")

        def pick():
            col = QColorDialog.getColor(QColor(self.cfg[key]), w, _("Elige un color"))
            if col.isValid():
                self.cfg.set(key, col.name())
                refresh()

        btn.clicked.connect(pick)
        refresh()
        self.refreshers.append(refresh)
        return w

    def refresh_all(self):
        for r in self.refreshers:
            r()


def group(title, rows):
    g = QGroupBox(title)
    f = QFormLayout(g)
    f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    f.setHorizontalSpacing(16)
    f.setVerticalSpacing(10)
    for row in rows:
        if isinstance(row, tuple):
            f.addRow(row[0], row[1])
        else:
            f.addRow(row)
    return g


def note(text):
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setObjectName("sub")
    return lab


# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, cfg, engine, on_quit):
        super().__init__()
        self.cfg, self.engine, self.on_quit = cfg, engine, on_quit
        self.b = Binder(cfg)
        self.setWindowTitle(_("Ambiluz · luces de monitor"))
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(1060, 760)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 8)
        root.setSpacing(12)

        # cabecera
        head = QHBoxLayout()
        titles = QVBoxLayout()
        t = QLabel("Ambiluz")
        t.setObjectName("title")
        self.dev_label = QLabel("")
        self.dev_label.setObjectName("sub")
        titles.addWidget(t)
        titles.addWidget(self.dev_label)
        head.addLayout(titles, 1)
        head.addWidget(QLabel(_("Brillo")))
        bw = self.b.slider("brightness", 0, 100)
        bw.setMinimumWidth(240)
        head.addWidget(bw)
        self.power = QPushButton()
        self.power.setObjectName("power")
        self.power.setCheckable(True)
        self.power.toggled.connect(self._power_toggled)
        head.addSpacing(10)
        head.addWidget(self.power)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        for m, name, emo in MODES + [("settings", _("Ajustes"), "⚙")]:
            it = QListWidgetItem(f"{emo}   {name}")
            it.setData(Qt.UserRole, m)
            self.sidebar.addItem(it)
        body.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setSpacing(10)
        self.preview = StripPreview(engine, cfg)
        right.addWidget(self.preview, 3)
        self.stack = QStackedWidget()
        self.pages = {}
        for m, builder in [("sync", self._page_sync), ("flow", self._page_flow),
                           ("mono", self._page_mono), ("music", self._page_music),
                           ("race", self._page_race), ("settings", self._page_settings)]:
            page = builder()
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setWidget(page)
            sc.setFrameShape(QFrame.NoFrame)
            self.pages[m] = self.stack.addWidget(sc)
        right.addWidget(self.stack, 7)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        self.status = self.statusBar()
        self.sidebar.currentRowChanged.connect(self._side_changed)
        self._select_mode_row(cfg["mode"])

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(400)
        self._tick()
        self._make_tray()
        self.refresh()

    # ---------------------------------------------------------- páginas
    def _page_sync(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 6, 0)
        self.sync_status = note("")
        v.addWidget(group(_("Zona de la pantalla"), [
            self.b.choice_grid("sync_region", [
                ("full", _("Pantalla completa")), ("top", _("Mitad superior")),
                ("bottom", _("Mitad inferior")), ("left", _("Mitad izquierda")),
                ("right", _("Mitad derecha")), ("movie", _("Modo película"))], cols=3),
        ]))
        again = QPushButton(_("Elegir otra pantalla…"))
        again.clicked.connect(lambda: self.engine.restart_capture(forget_screen=True))
        retry = QPushButton(_("Reintentar captura"))
        retry.clicked.connect(lambda: self.engine.restart_capture(False))
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.addWidget(again)
        btns.addWidget(retry)
        btns.addStretch(1)
        bw = QWidget()
        bw.setLayout(btns)
        v.addWidget(group(_("Imagen"), [
            (_("Suavizado"), self.b.slider("sync_smooth", 0, 100)),
            self.b.check("sync_smooth_enabled", _("Coloración suave (transiciones sin parpadeo)")),
            self.b.check("sync_blackborder", _("Detectar bandas negras automáticamente")),
            (_("Saturación"), self.b.slider("sync_saturation", 50, 200)),
            (_("Profundidad"), self.b.slider("sync_depth", 3, 40)),
            (_("Gamma"), self.b.slider("sync_gamma", 5, 30, lambda x: f"{x / 10:.1f}")),
            (_("Umbral de negro"), self.b.slider("sync_minlevel", 0, 30)),
            bw, self.sync_status,
        ]))
        v.addStretch(1)
        return w

    def _page_flow(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 6, 0)
        v.addWidget(group(_("Efecto"), [self.b.choice_grid("flow_effect", FLOW_EFFECTS, cols=4)]))
        v.addWidget(group(_("Ajustes"), [
            (_("Paleta"), self.b.combo("flow_palette", [(k, _(k)) for k in PALETTES])),
            (_("Velocidad"), self.b.slider("flow_speed", 0, 100)),
            (_("Tamaño"), self.b.slider("flow_scale", 0, 100)),
            self.b.check("flow_reverse", _("Sentido inverso")),
            note(_("La paleta se usa en Degradado, Aurora, Ola, Respiración, Ciclo y Destellos.")),
        ]))
        v.addStretch(1)
        return w

    def _page_mono(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 6, 0)
        v.addWidget(group(_("Color"), [self.b.color("mono_color")]))
        v.addWidget(group(_("Efecto"), [
            self.b.choice_grid("mono_effect", MONO_EFFECTS, cols=5),
            (_("Velocidad"), self.b.slider("mono_speed", 0, 100)),
        ]))
        v.addStretch(1)
        return w

    def _page_music(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 6, 0)
        v.addWidget(group(_("Estilo"), [self.b.choice_grid("music_style", MUSIC_STYLES, cols=3)]))
        self.music_src = QComboBox()
        self.music_src.currentIndexChanged.connect(
            lambda _i: self.music_src.currentData() and self.cfg.set("music_device", self.music_src.currentData()))
        refresh_src = QPushButton("↻")
        refresh_src.setFixedWidth(40)
        refresh_src.clicked.connect(self._fill_sources)
        srow = QHBoxLayout()
        srow.setContentsMargins(0, 0, 0, 0)
        srow.addWidget(self.music_src, 1)
        srow.addWidget(refresh_src)
        sw = QWidget()
        sw.setLayout(srow)
        self.music_status = note("")
        v.addWidget(group(_("Sonido"), [
            (_("Fuente"), sw),
            (_("Sensibilidad"), self.b.slider("music_sensitivity", 0, 100)),
            (_("Suavizado"), self.b.slider("music_smooth", 0, 100)),
            self.music_status,
        ]))
        v.addWidget(group(_("Colores"), [
            (_("Modo de color"), self.b.combo("music_colormode", [
                ("rainbow", _("Arcoíris")), ("palette", _("Paleta")), ("fixed", _("Color fijo"))])),
            (_("Paleta"), self.b.combo("music_palette", [(k, _(k)) for k in PALETTES])),
            (_("Color fijo"), self.b.color("music_color")),
        ]))
        v.addStretch(1)
        self._fill_sources()
        return w

    def _fill_sources(self):
        self.music_src.blockSignals(True)
        self.music_src.clear()
        for val, label in list_sources():
            self.music_src.addItem(label, val)
        i = self.music_src.findData(self.cfg["music_device"])
        if i < 0:
            self.music_src.addItem(self.cfg["music_device"], self.cfg["music_device"])
            i = self.music_src.count() - 1
        self.music_src.setCurrentIndex(i)
        self.music_src.blockSignals(False)

    def _page_race(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 6, 0)
        v.addWidget(group(_("Estilo"), [self.b.choice_grid("race_style", RACE_STYLES, cols=3)]))
        v.addWidget(group(_("Ajustes"), [
            (_("Paleta"), self.b.combo("race_palette", [(k, _(k)) for k in PALETTES])),
            (_("Velocidad"), self.b.slider("race_speed", 0, 100)),
            (_("Cantidad"), self.b.slider("race_count", 1, 10, lambda x: str(x))),
            (_("Longitud"), self.b.slider("race_length", 0, 100)),
            self.b.check("race_reverse", _("Sentido inverso")),
        ]))
        v.addStretch(1)
        return w

    def _page_settings(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 6, 0)

        self.port_combo = QComboBox()
        self.port_combo.currentIndexChanged.connect(self._port_changed)
        rescan = QPushButton(_("Buscar"))
        rescan.clicked.connect(self._fill_ports)
        prow = QHBoxLayout()
        prow.setContentsMargins(0, 0, 0, 0)
        prow.addWidget(self.port_combo, 1)
        prow.addWidget(rescan)
        pw = QWidget()
        pw.setLayout(prow)

        model_opts = [("auto", _("Automático (detectar)"))] + \
            [(m, f"{m}  ({sum(s)} LEDs)") for m, (_k, s) in models.MODELS.items()] + \
            [("custom", _("Personalizado"))]
        self.custom_box = QWidget()
        cb = QHBoxLayout(self.custom_box)
        cb.setContentsMargins(0, 0, 0, 0)
        self.custom_spins = []
        for i, name in enumerate([_("Izq."), _("Arriba"), _("Der."), _("Abajo")]):
            sp = QSpinBox()
            sp.setRange(0, 300)
            sp.valueChanged.connect(self._custom_changed)
            cb.addWidget(QLabel(name))
            cb.addWidget(sp)
            self.custom_spins.append(sp)
        self.device_info = note("")
        v.addWidget(group(_("Dispositivo"), [
            (_("Puerto"), pw),
            (_("Modelo"), self.b.combo("model", model_opts, on_change=lambda _v: self._update_custom_vis())),
            (_("LEDs por lado"), self.custom_box),
            self.device_info,
        ]))

        v.addWidget(group(_("Instalación"), [
            (_("Dirección"), self.b.combo("reverse", [
                (False, _("Izquierda → derecha (sentido horario)")),
                (True, _("Derecha → izquierda (antihorario)"))])),
            (_("Desplazamiento"), self._offset_spin()),
            (_("Orden de color"), self.b.combo("color_order", [(k, k) for k in
                                                           ["RGB", "GRB", "BRG", "RBG", "GBR", "BGR"]])),
            note(_("Usa las pruebas para comprobar la colocación: en «Identificar lados» la izquierda debe verse ROJA, "
                   "arriba VERDE y la derecha AZUL. Si están intercambiadas, cambia la dirección.")),
        ]))

        tests = QHBoxLayout()
        tests.setContentsMargins(0, 0, 0, 0)
        for label, kind in [(_("Identificar lados"), "sides"), (_("Recorrido LED a LED"), "sweep"),
                            (_("Prueba R/G/B/Blanco"), "rgb")]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, k=kind: self.engine.run_test(k, 8.0 if k != "sweep" else 9.0))
            tests.addWidget(b)
        stop = QPushButton(_("Parar prueba"))
        stop.clicked.connect(lambda: setattr(self.engine, "test", None))
        tests.addWidget(stop)
        tw = QWidget()
        tw.setLayout(tests)
        v.addWidget(group(_("Calibración"), [tw]))

        v.addWidget(group(_("Color y rendimiento"), [
            (_("Rojo"), self.b.slider("wb_r", 0, 100)),
            (_("Verde"), self.b.slider("wb_g", 0, 100)),
            (_("Azul"), self.b.slider("wb_b", 0, 100)),
            (_("Fotogramas/s"), self.b.slider("fps", 10, 45, lambda x: f"{x} fps")),
        ]))

        v.addWidget(group(_("Sistema"), [
            self.b.check("autostart", _("Iniciar al encender el PC (en la bandeja)"),
                         on_change=self._autostart_changed),
            self.b.check("off_on_lock", _("Apagar las luces al bloquear la pantalla o suspender")),
            (_("Idioma (requiere reiniciar)"), self.b.combo("language", LANGUAGE_CHOICES)),
            self.b.check("close_to_tray", _("Al cerrar la ventana, seguir en la bandeja del sistema")),
        ]))
        v.addStretch(1)
        self._fill_ports()
        self._update_custom_vis()
        return w

    def _offset_spin(self):
        sp = QSpinBox()
        sp.setRange(-200, 200)

        def refresh():
            sp.blockSignals(True)
            sp.setValue(int(self.cfg["offset"]))
            sp.blockSignals(False)

        sp.valueChanged.connect(lambda x: self.cfg.set("offset", int(x)))
        refresh()
        self.b.refreshers.append(refresh)
        return sp

    def _fill_ports(self):
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem(_("Automático"), "auto")
        for p in list_ports():
            tag = "  (Skydimo/CH340)" if p["likely"] else ""
            self.port_combo.addItem(p["path"] + tag, p["path"])
        i = self.port_combo.findData(self.cfg["port"])
        if i < 0:
            self.port_combo.addItem(self.cfg["port"], self.cfg["port"])
            i = self.port_combo.count() - 1
        self.port_combo.setCurrentIndex(i)
        self.port_combo.blockSignals(False)

    def _port_changed(self, _i):
        val = self.port_combo.currentData()
        if val and val != self.cfg["port"]:
            self.cfg.set("port", val)
            self.engine.reconnect()

    def _custom_changed(self, _v):
        self.cfg.set("custom_segments", [s.value() for s in self.custom_spins])

    def _update_custom_vis(self):
        custom = self.cfg["model"] == "custom"
        self.custom_box.setEnabled(custom)
        segs = list(self.cfg["custom_segments"]) + [0, 0, 0, 0]
        for s, val in zip(self.custom_spins, segs):
            s.blockSignals(True)
            s.setValue(int(val))
            s.blockSignals(False)

    def _autostart_changed(self, on):
        set_autostart(on)

    # ---------------------------------------------------------- lógica
    def _select_mode_row(self, mode):
        for i in range(self.sidebar.count()):
            if self.sidebar.item(i).data(Qt.UserRole) == mode:
                self.sidebar.blockSignals(True)
                self.sidebar.setCurrentRow(i)
                self.sidebar.blockSignals(False)
                self.stack.setCurrentIndex(self.pages[mode])
                return

    def _side_changed(self, row):
        m = self.sidebar.item(row).data(Qt.UserRole)
        self.stack.setCurrentIndex(self.pages[m])
        if m != "settings":
            self.cfg.set("mode", m)
            self.cfg.set("power", True)
            self.refresh()

    def _power_toggled(self, on):
        self.cfg.set("power", bool(on))
        self._update_power_btn()
        self._sync_tray()

    def _update_power_btn(self):
        on = bool(self.cfg["power"])
        self.power.blockSignals(True)
        self.power.setChecked(on)
        self.power.blockSignals(False)
        self.power.setText(_("●  Encendido") if on else _("○  Apagado"))

    def refresh(self):
        self.b.refresh_all()
        self._update_power_btn()
        cur = self.sidebar.currentItem()
        if cur is None or cur.data(Qt.UserRole) != "settings":
            self._select_mode_row(self.cfg["mode"])
        self._sync_tray()

    def _tick(self):
        e = self.engine
        model = e.effective_model()
        n = e.layout.n if e.layout else 0
        self.dev_label.setText(f"{e.device_msg}  ·  {model} · {n} LEDs")
        serial = f" · {_('nº serie')} {e.detected_serial}" if e.detected_serial else ""
        self.device_info.setText(f"{_('Detectado')}: {e.detected_model or '—'}{serial}")
        cap = e.capture
        txt = cap.message or (_("Captura en pausa") if cap.state == "idle" else "")
        if cap.state == "error":
            txt = "⚠ " + txt + " — " + _("pulsa «Reintentar captura».")
        self.sync_status.setText(txt)
        a = e.audio
        self.music_status.setText(a.message or "")
        extra = ""
        if e.test:
            extra = " · " + _("prueba en curso")
        elif self.cfg["off_on_lock"] and (e.locked or e.sleeping):
            extra = " · " + _("en pausa (pantalla bloqueada)")
        err = f" · error: {e.error}" if e.error else ""
        self.status.showMessage(f"{MODE_NAMES.get(self.cfg['mode'], '')} · {e.actual_fps:.0f} fps{extra}{err}")
        if self.power.isChecked() != bool(self.cfg["power"]):
            self._update_power_btn()

    # ---------------------------------------------------------- bandeja
    def _make_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon(ICON_PATH), self)
        self.tray.setToolTip("Ambiluz")
        menu = QMenu()
        act_show = QAction(_("Mostrar ventana"), self)
        act_show.triggered.connect(self.show_raise)
        menu.addAction(act_show)
        self.act_power = QAction(_("Encendido"), self)
        self.act_power.setCheckable(True)
        self.act_power.toggled.connect(lambda on: (self.cfg.set("power", on), self._update_power_btn()))
        menu.addAction(self.act_power)
        menu.addSeparator()
        self.mode_group = QActionGroup(self)
        self.mode_actions = {}
        for m, name, emo in MODES:
            a = QAction(f"{emo}  {name}", self)
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, mm=m: (self.cfg.set("mode", mm), self.cfg.set("power", True),
                                                        self.refresh()))
            self.mode_group.addAction(a)
            menu.addAction(a)
            self.mode_actions[m] = a
        menu.addSeparator()
        act_quit = QAction(_("Salir"), self)
        act_quit.triggered.connect(self.on_quit)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._tray_menu = menu

    def _sync_tray(self):
        if not getattr(self, "tray", None):
            return
        self.act_power.blockSignals(True)
        self.act_power.setChecked(bool(self.cfg["power"]))
        self.act_power.blockSignals(False)
        a = self.mode_actions.get(self.cfg["mode"])
        if a:
            a.setChecked(True)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_raise()

    def show_raise(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, ev):
        if self.cfg["close_to_tray"] and self.tray is not None:
            ev.ignore()
            self.hide()
        else:
            ev.accept()
            self.on_quit()


def launcher_cmd():
    exe = shutil.which("ambiluz")
    if exe:
        return exe
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f"sh -c 'cd \"{pkg_parent}\" && exec {sys.executable} -m ambiluz \"$@\"' ambiluz"


AUTOSTART = os.path.expanduser("~/.config/autostart/ambiluz.desktop")


def set_autostart(on):
    if on:
        os.makedirs(os.path.dirname(AUTOSTART), exist_ok=True)
        with open(AUTOSTART, "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Ambiluz\n"
                    "Comment=Luces de monitor sincronizadas\n"
                    f"Exec={launcher_cmd()} --minimized\n"
                    "Icon=ambiluz\nX-GNOME-Autostart-enabled=true\nX-KDE-autostart-after=panel\n")
    else:
        try:
            os.remove(AUTOSTART)
        except FileNotFoundError:
            pass
