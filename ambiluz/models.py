"""Tabla de modelos Skydimo conocidos (respuesta a "Moni-A" -> modelo).

kind:
  perim3  -> izquierda, arriba, derecha (sin tira inferior)
  perim4  -> izquierda, arriba, derecha, abajo
  sides2  -> dos barras laterales (izquierda, derecha)
  strip   -> tira o lámpara lineal
"""

MODELS = {
    # Tiras de monitor de 3 lados (serie SK01)
    "SK0121": ("perim3", [13, 25, 13]),
    "SK0124": ("perim3", [14, 26, 14]),
    "SK0127": ("perim3", [17, 31, 17]),
    "SK0132": ("perim3", [20, 37, 20]),
    "SK0134": ("perim3", [15, 41, 15]),
    "SK0149": ("perim3", [19, 69, 19]),
    "SKA124": ("perim3", [18, 34, 18]),
    "SKA127": ("perim3", [20, 41, 20]),
    "SKA132": ("perim3", [25, 45, 25]),
    "SKA134": ("perim3", [21, 51, 21]),
    # Tiras de 4 lados (serie SK0L)
    "SK0L21": ("perim4", [13, 25, 13, 25]),
    "SK0L24": ("perim4", [14, 26, 14, 26]),
    "SK0L27": ("perim4", [17, 31, 17, 31]),
    "SK0L32": ("perim4", [20, 37, 20, 37]),
    "SK0L34": ("perim4", [15, 41, 15, 41]),
    # Barras laterales
    "SK0201": ("sides2", [20, 20]),
    "SK0202": ("sides2", [30, 30]),
    "SK0204": ("sides2", [25, 25]),
    # Lámparas / tiras lineales
    "SK0F01": ("strip", [29, 29]),
    "SK0F02": ("strip", [25, 25]),
    "SK0402": ("strip", [72]),
    "SK0403": ("strip", [96]),
}

DEFAULT_MODEL = "SK0127"


def lookup(model):
    return MODELS.get((model or "").strip().upper())


def custom_kind(segments):
    """Deduce el tipo a partir de [izq, arriba, der, abajo] personalizados."""
    left, top, right, bottom = (list(segments) + [0, 0, 0, 0])[:4]
    if bottom > 0 and top > 0:
        return "perim4", [left, top, right, bottom]
    if top > 0 and (left > 0 or right > 0):
        return "perim3", [left, top, right]
    if top == 0 and left > 0 and right > 0:
        return "sides2", [left, right]
    return "strip", [max(1, left + top + right + bottom)]
