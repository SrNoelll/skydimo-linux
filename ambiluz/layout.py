"""Geometría de los LEDs alrededor del monitor.

Orden lógico (el que usan efectos, vista previa y muestreo): sentido horario
empezando abajo a la izquierda:
    izquierda (abajo -> arriba), arriba (izq -> der),
    derecha (arriba -> abajo), abajo (der -> izq)
El orden físico del cable se obtiene con `perm` (dirección + desplazamiento).
"""

import numpy as np

LEFT, TOP, RIGHT, BOTTOM = 0, 1, 2, 3
SIDES = {
    "perim3": [LEFT, TOP, RIGHT],
    "perim4": [LEFT, TOP, RIGHT, BOTTOM],
    "sides2": [LEFT, RIGHT],
    "strip": [TOP],
}


class Layout:
    def __init__(self, kind, segments, reverse=False, offset=0):
        if kind == "strip":
            segments = [int(sum(segments))]
        sides = SIDES.get(kind, SIDES["perim3"])
        segments = [max(0, int(s)) for s in segments][:len(sides)]
        while len(segments) < len(sides):
            segments.append(0)
        self.kind = kind
        self.segments = segments
        side, a0, a1 = [], [], []
        for code, n in zip(sides, segments):
            for i in range(n):
                side.append(code)
                a0.append(i / n)
                a1.append((i + 1) / n)
        self.n = n = len(side)
        self.side = np.array(side, dtype=np.int8)
        self.a0 = np.array(a0, dtype=np.float32)
        self.a1 = np.array(a1, dtype=np.float32)
        mid = (self.a0 + self.a1) / 2

        x = np.zeros(n, np.float32)
        y = np.zeros(n, np.float32)
        m = self.side == LEFT
        x[m], y[m] = 0.0, 1.0 - mid[m]
        m = self.side == TOP
        x[m], y[m] = mid[m], 0.0
        m = self.side == RIGHT
        x[m], y[m] = 1.0, mid[m]
        m = self.side == BOTTOM
        x[m], y[m] = 1.0 - mid[m], 1.0
        self.pos = np.stack([x, y], 1)

        self.idx = np.arange(n, dtype=np.float32)
        self.t = (self.idx + 0.5) / max(1, n)            # 0..1 a lo largo de la tira
        self.sym = 1.0 - np.abs(2.0 * self.t - 1.0)      # 0 en extremos, 1 en el centro

        order = np.arange(n)
        if reverse:
            order = order[::-1]
        if n:
            order = np.roll(order, -(int(offset) % n))
        self.perm = order.copy()                          # físico k <- lógico perm[k]

    def rects(self, depth):
        """Rectángulos de muestreo normalizados (x0, y0, x1, y1) por LED."""
        d = float(np.clip(depth, 0.02, 0.5))
        r = np.zeros((self.n, 4), np.float32)
        s, a0, a1 = self.side, self.a0, self.a1
        m = s == LEFT
        r[m] = np.stack([np.zeros(m.sum()), 1 - a1[m], np.full(m.sum(), d), 1 - a0[m]], 1)
        m = s == TOP
        r[m] = np.stack([a0[m], np.zeros(m.sum()), a1[m], np.full(m.sum(), d)], 1)
        m = s == RIGHT
        r[m] = np.stack([np.full(m.sum(), 1 - d), a0[m], np.ones(m.sum()), a1[m]], 1)
        m = s == BOTTOM
        r[m] = np.stack([1 - a1[m], np.full(m.sum(), 1 - d), 1 - a0[m], np.ones(m.sum())], 1)
        return r
