"""Hardware-free tests: layouts, every effect, music analyzer, translations."""
import numpy as np
import pytest

from ambiluz import i18n, models
from ambiluz.config import DEFAULTS
from ambiluz.effects import (FLOW_EFFECTS, MONO_EFFECTS, MUSIC_STYLES, RACE_STYLES, Effects)
from ambiluz.layout import Layout


class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k, DEFAULTS.get(k))


@pytest.mark.parametrize("model", sorted(models.MODELS))
def test_layouts(model):
    kind, segs = models.MODELS[model]
    for rev in (False, True):
        L = Layout(kind, segs, rev, 3)
        assert L.n == sum(segs)
        assert sorted(L.perm.tolist()) == list(range(L.n))
        r = L.rects(0.15)
        assert r.shape == (L.n, 4) and (r[:, 2] > r[:, 0]).all() and (r[:, 3] > r[:, 1]).all()


@pytest.mark.parametrize("key,options", [("flow_effect", FLOW_EFFECTS), ("mono_effect", MONO_EFFECTS),
                                         ("race_style", RACE_STYLES), ("music_style", MUSIC_STYLES)])
def test_effects(key, options):
    L = Layout("perim3", [17, 31, 17])
    fx = Effects()
    for value, _label in options:
        cfg = Cfg({key: value})
        for i in range(30):
            if key == "flow_effect":
                c = fx.flow(L, cfg, 1 / 30)
            elif key == "mono_effect":
                c = fx.mono(L, cfg, 1 / 30)
            elif key == "race_style":
                c = fx.race(L, cfg, 1 / 30)
            else:
                x = (np.sin(np.arange(2048) * 0.05 * (1 + i % 4)) * 0.3).astype(np.float32)
                c = fx.music(L, cfg, 1 / 30, x, i / 30)
            c = np.asarray(c)
            assert c.shape == (65, 3) and np.isfinite(c).all() and c.min() >= 0


def test_translations_complete():
    import importlib
    en = importlib.import_module("ambiluz.locales.en").T
    for code in i18n.LANGUAGES:
        if code == "es":
            continue
        t = importlib.import_module(f"ambiluz.locales.{code}").T
        assert set(t) == set(en), code
