# Contributing

Thanks for helping! Ambiluz is small and easy to hack on.

## Run from source

```bash
git clone https://github.com/SrNoelll/skydimo-linux.git
cd skydimo-linux
python3 -m ambiluz          # needs PySide6, numpy, PyGObject and GStreamer (see README)
```

## Project layout

| File | What it does |
|---|---|
| `ambiluz/device.py` | Serial protocol (CH340, 115200 8N1, `Ada` header, `Moni-A` model query) |
| `ambiluz/models.py` | Known Skydimo models and LEDs per side |
| `ambiluz/layout.py` | LED geometry around the screen |
| `ambiluz/capture.py` | Screen capture through xdg-desktop-portal + PipeWire |
| `ambiluz/audio.py` | System audio capture (PipeWire / PulseAudio) |
| `ambiluz/effects.py` | Flow, solid color, light-chase and music effects |
| `ambiluz/engine.py` | Frame loop: picks the mode, post-processes and sends frames |
| `ambiluz/gui.py` | Qt interface and tray icon |
| `ambiluz/locales/` | Translations |

## Add a model

Add a line to `MODELS` in `ambiluz/models.py` with the string the strip answers to `Moni-A`
(shown by `ambiluz --probe`) and its LEDs per side.

## Add or improve a translation

Copy `ambiluz/locales/en.py` to `ambiluz/locales/<code>.py`, translate the values (keys are the
Spanish source strings) and add the code to `LANGUAGES` in `ambiluz/i18n.py`.

## Add an effect

Effects are plain functions in `ambiluz/effects.py` that return an `(n, 3)` array of RGB values
(0–255) in logical LED order. Register it in the matching `*_EFFECTS`/`*_STYLES` list.
