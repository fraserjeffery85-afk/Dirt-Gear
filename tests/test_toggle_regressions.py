"""Regression tests for v1.0.4 layer-toggle bugs.

1. A visible layer with no pixel data (e.g. some smart objects) must not turn
   the preview white -- psd-tools treats it as transparent.
2. A request carrying an older `rev` must not put back visibility the user
   already changed (requests can be served out of order).
3. Random on/off toggles: the fast preview matches the exact render.

Run: python tests/test_toggle_regressions.py   (needs psd-tools 1.19)"""
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
import app  # noqa: E402
from psd_tools import PSDImage  # noqa: E402


def ok(condition, message):
    if not condition:
        raise SystemExit('FAIL ' + message)
    print('PASS', message)


def diff(doc):
    fast = doc.fast_composite(False, 512)
    exact = doc.composite_default(False).resize(fast.size, Image.Resampling.BOX)
    return np.abs(np.asarray(fast, dtype=np.int16) - np.asarray(exact, dtype=np.int16)).mean()


with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp) / 'like-user.psd'
    subprocess.run([sys.executable, str(ROOT / 'tests/make_like_user_psd.py'), str(base)], check=True)

    psd = PSDImage.open(base)
    x = next(l for l in psd.descendants() if l.name == 'X')
    for channel in x._channels:
        channel.data = b''
    x.visible = True
    empty = Path(tmp) / 'empty-layer.psd'
    psd.save(empty)
    doc = app.Document(empty, 'empty-layer.psd')
    ok(doc.fast_failed is None and diff(doc) < 3, 'pixel-less visible layer does not blank the preview')

    doc = app.Document(base, 'like-user.psd')
    key = next(k for k, l in doc.layers.items() if l.name == 'UV')
    vis = dict(doc.state['visibility'])
    vis[key] = True
    doc.update({'visibility': vis, 'rev': 200})
    stale = dict(vis)
    stale[key] = False
    doc.update({'visibility': stale, 'rev': 100})
    ok(doc.state['visibility'][key] is True, 'older request cannot undo a newer layer toggle')

    random.seed(3)
    keys = [k for k in doc.layers if k not in doc.state['normal_layers']]
    worst = 0
    for step in range(15):
        k = random.choice(keys)
        vis = dict(doc.state['visibility'])
        vis[k] = not vis[k]
        doc.update({'visibility': vis})
        worst = max(worst, diff(doc))
    ok(worst < 3 and doc.fast_failed is None, f'15 random toggles match the exact render (worst mean diff {worst:.2f})')
print('ALL TOGGLE REGRESSION TESTS PASS')
