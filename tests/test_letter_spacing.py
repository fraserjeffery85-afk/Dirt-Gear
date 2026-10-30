"""Letter spacing tests. Run: python tests/test_letter_spacing.py"""
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
import app  # noqa: E402

def ok(c, m):
    if not c:
        raise SystemExit('FAIL ' + m)
    print('PASS', m)

font = next(k for k in app.installed_fonts() if 'byd-number-font-race' in k.lower())
base = {'value': '76', 'font': font, 'size': 300, 'fill': '#1060ff', 'stroke': 0, 'outline': '#000000'}

def ink_gap(im):
    """Width of the empty column run between the two characters."""
    alpha = np.asarray(im.getchannel('A')) > 20
    cols = alpha.any(axis=0)
    inside = np.flatnonzero(cols)
    run = cols[inside[0]:inside[-1] + 1]
    gaps, current = [], 0
    for filled in run:
        current = 0 if filled else current + 1
        gaps.append(current)
    return max(gaps)

zero = app.render_text_bitmap(dict(base, tracking=0))
legacy = app.render_text_bitmap({k: v for k, v in base.items()})
ok(np.array_equal(np.asarray(zero), np.asarray(legacy)), '0% spacing is pixel-identical to the previous renderer')
tight = app.render_text_bitmap(dict(base, tracking=-15))
wide = app.render_text_bitmap(dict(base, tracking=25))
ok(tight.width < zero.width < wide.width, f'width changes with spacing ({tight.width} < {zero.width} < {wide.width})')
def right_edge(im):
    return int(np.flatnonzero((np.asarray(im.getchannel('A')) > 20).any(axis=0))[-1])
moved_in, moved_out = right_edge(zero) - right_edge(tight), right_edge(wide) - right_edge(zero)
ok(abs(moved_in - 45) <= 2 and abs(moved_out - 75) <= 2, f'the 6 moves by the spacing (-15% of 300px: {moved_in}px in, +25%: {moved_out}px out)')
near_zero = app.render_text_bitmap(dict(base, tracking=1e-9))
ok(np.array_equal(np.asarray(near_zero.getchannel('A')), np.asarray(zero.getchannel('A'))), 'per-letter layout keeps the font kerning (6 tucked under 7)')
name = app.render_text_bitmap(dict(base, value='ONEBLOKE', font=next(k for k in app.installed_fonts() if 'byd-name-font-stock' in k.lower()), tracking=-8))
name0 = app.render_text_bitmap(dict(base, value='ONEBLOKE', font=next(k for k in app.installed_fonts() if 'byd-name-font-stock' in k.lower()), tracking=0))
ok(abs((name0.width - name.width) - round(300 * 0.08 * 7)) <= 3, 'names tighten by spacing x (letters - 1)')
ok(abs(tight.height - zero.height) <= 1, 'height unchanged')
outlined = app.render_text_bitmap(dict(base, tracking=-30, stroke=12))
a = np.asarray(outlined)
fill_px = ((a[..., 2] > 200) & (a[..., 0] < 60) & (a[..., 3] > 250)).sum()
ok(fill_px > 0.5 * ((np.asarray(zero)[..., 3] > 250).sum()), 'tight spacing with outline keeps letter fills on top of outlines')
grad = app.render_text_bitmap(dict(base, tracking=-10, gradient={'start': '#ff0000', 'end': '#0000ff', 'angle': 90}))
g = np.asarray(grad)
ok(g[..., 3].max() == 255 and g[..., 0].max() > 200 and g[..., 2].max() > 200, 'gradient fill works with spacing')
multi = app.render_text_bitmap(dict(base, value='ONE\nBLOKE', tracking=10))
ok(multi.height > zero.height, 'multi-line names work with spacing')
for bad in (-60, 250, 'abc'):
    try:
        app.render_text_bitmap(dict(base, tracking=bad)); ok(False, 'reject %r' % bad)
    except ValueError:
        pass
ok(True, 'out-of-range spacing rejected')
print('ALL LETTER SPACING TESTS PASS')
