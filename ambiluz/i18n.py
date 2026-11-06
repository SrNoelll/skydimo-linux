"""Translations.

Source strings are Spanish; every other language lives in ambiluz/locales/<code>.py
as a dict  {spanish_source: translation}.  To add a language, copy locales/en.py,
translate the values and add the code to LANGUAGES below.
"""

import importlib
import locale
import os

LANGUAGES = ["es", "en", "zh", "ja", "ru", "fr"]
NATIVE = {"es": "Español", "en": "English", "zh": "简体中文", "ja": "日本語",
          "ru": "Русский", "fr": "Français"}
LANGUAGE_CHOICES = [("auto", "Auto / System")] + [(c, NATIVE[c]) for c in LANGUAGES]

_table = {}
current = "es"


def detect():
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        v = os.environ.get(var)
        if v and v not in ("C", "POSIX"):
            return v.split(":")[0][:2].lower()
    try:
        return (locale.getlocale()[0] or "en")[:2].lower()
    except ValueError:
        return "en"


def set_lang(lang):
    global _table, current
    if lang in (None, "", "auto"):
        lang = detect()
    if lang not in LANGUAGES:
        lang = "en"
    current = lang
    if lang == "es":
        _table = {}
        return
    try:
        _table = importlib.import_module(f".locales.{lang}", __package__).T
    except ImportError:
        _table = importlib.import_module(".locales.en", __package__).T


def _(text):
    return _table.get(text, text)


set_lang("auto")
