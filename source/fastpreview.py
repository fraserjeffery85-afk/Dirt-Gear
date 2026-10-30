"""Fast on-screen preview compositing for Dirt Gear.

psd-tools composites at full resolution in float arrays, which takes tens of
seconds for a 4K gear PSD with many layers. The on-screen preview never needs
4K, so this module runs *psd-tools' own compositor* (same blend maths, masks,
clipping, pass-through/isolated groups, adjustments) over cached, downscaled
copies of each layer's pixels.

Exports and "Check final rendering" keep using the full-resolution psd-tools
composite; nothing here touches export output.

Anything this path cannot reproduce at a smaller scale (layer strokes, pattern
or gradient overlays, vector-drawn masks/fills, knockout) raises Unsupported,
and the caller falls back to the exact full-resolution composite.

Written against psd-tools 1.19 (the version Dirt Gear ships with).
"""
from __future__ import annotations

import math
import threading
from typing import cast

import numpy as np
from PIL import Image

import psd_tools
from psd_tools.api.layers import GroupMixin, Layer
import importlib
ptc = importlib.import_module("psd_tools.composite.composite")
from psd_tools.composite import utils
from psd_tools.composite.widen import make_widen
from psd_tools.constants import BlendMode, Knockout

SUPPORTED = psd_tools.__version__.startswith('1.19.')


class Unsupported(Exception):
    pass


def _scaled_box(bbox, s):
    l, t, r, b = bbox
    return (int(math.floor(l * s)), int(math.floor(t * s)),
            max(int(math.floor(l * s)) + 1, int(math.ceil(r * s))),
            max(int(math.floor(t * s)) + 1, int(math.ceil(b * s))))


def _resize(array, size):
    """Area-average resize of a float32 (h, w, c) array to size=(w, h)."""
    h, w, c = array.shape
    if (w, h) == size:
        return array.astype(np.float32, copy=False)
    planes = [np.asarray(Image.fromarray(np.ascontiguousarray(array[:, :, i]), 'F')
                         .resize(size, Image.Resampling.BOX), dtype=np.float32)
              for i in range(c)]
    return np.stack(planes, axis=2)


class LayerCache:
    """Downscaled per-layer pixel data, keyed by (layer id, scale)."""

    def __init__(self, budget=1024 * 1024 * 1024):
        self.data = {}
        self.bytes = 0
        self.budget = budget
        self.lock = threading.RLock()
        self.pending = {}

    def get(self, key, make):
        """Return cached data for key, computing it once even if several
        threads ask at the same time (prefetch, thumbnails, renders)."""
        with self.lock:
            if key in self.data:
                return self.data[key]
            pending = self.pending.get(key)
            if pending is None:
                pending = self.pending[key] = threading.Event()
                owner = True
            else:
                owner = False
        if not owner:
            pending.wait()
            with self.lock:
                if key in self.data:
                    return self.data[key]
            return make()
        try:
            value = make()
            size = sum(v[0].nbytes for v in value.values()) if isinstance(value, dict) else 0
            with self.lock:
                while self.data and self.bytes + size > self.budget:
                    old = self.data.pop(next(iter(self.data)))
                    self.bytes -= sum(v[0].nbytes for v in old.values()) if isinstance(old, dict) else 0
                self.data[key] = value
                self.bytes += size
            return value
        finally:
            with self.lock:
                self.pending.pop(key, None)
            pending.set()

    def clear(self):
        with self.lock:
            self.data.clear()
            self.bytes = 0


class ScaledCompositor(ptc.Compositor):
    """psd-tools Compositor working in a scaled coordinate space."""

    def __init__(self, viewport, color, alpha, *, scale, source, placeholder=None, full_box=None, **kwargs):
        super().__init__(viewport, color, alpha, **kwargs)
        self._placeholder = placeholder
        self._full_box = full_box
        self._scale = scale
        self._source = source   # callable(layer, kind) -> (array, scaled bbox) or (None, None)

    # -- helpers -------------------------------------------------------------
    def _sbbox(self, layer):
        if self._placeholder is not None and layer is self._placeholder:
            return self._full_box   # artwork covers the whole canvas
        return _scaled_box(layer.bbox, self._scale) if layer.bbox != (0, 0, 0, 0) else (0, 0, 0, 0)

    def _child(self, viewport, color, alpha, **kwargs):
        return ScaledCompositor(viewport, color, alpha, scale=self._scale, source=self._source,
                                placeholder=self._placeholder, full_box=self._full_box,
                                widen=self._widen, color_mode=self._color_mode, **kwargs)

    # -- overrides (same logic as psd-tools 1.19, scaled geometry) -----------
    def _accepts(self, layer, clip_compositing):
        if self._layer_filter is not None and not self._layer_filter(layer):
            return False
        from psd_tools.api.layers import AdjustmentLayer
        if (utils.intersect(self._viewport, self._sbbox(layer)) == (0, 0, 0, 0)) and not (
                isinstance(layer, AdjustmentLayer) or isinstance(layer, GroupMixin)):
            return False
        if not clip_compositing and layer.clipping:
            return False
        return True

    def _resolve_source(self, layer):
        if ptc._read_knockout(layer):
            raise Unsupported('knockout')
        return super()._resolve_source(layer)

    def _get_group(self, layer, knockout):
        is_passthrough = layer.blend_mode == BlendMode.PASS_THROUGH
        viewport = self._viewport if is_passthrough else utils.intersect(self._viewport, self._sbbox(layer))
        if viewport == (0, 0, 0, 0):   # group lies entirely outside this band
            empty = np.zeros((self.height, self.width, 1), dtype=np.float32)
            return np.ones((self.height, self.width, self.channels), dtype=np.float32), empty, empty.copy(), False
        color_b, alpha_b = self._color, self._alpha
        shape_const, _ = self._get_const(layer)
        isolate_adjustments = shape_const < 1.0 or layer.has_clip_layers()
        group_alpha = (ptc.paste(viewport, self._viewport, alpha_b) if is_passthrough
                       else np.zeros((viewport[3] - viewport[1], viewport[2] - viewport[0], 1), dtype=np.float32))
        group = self._child(viewport, ptc.paste(viewport, self._viewport, color_b, 1.0), group_alpha,
                            layer_filter=self._layer_filter,
                            adjustment_isolated=self._adjustment_isolated or isolate_adjustments)
        for sublayer in cast(GroupMixin, layer):
            group.apply(sublayer)
        color = group.result_isolated() if isolate_adjustments else group.result_over_backdrop()
        return (ptc.paste(self._viewport, viewport, color, 1.0),
                ptc.paste(self._viewport, viewport, group.shape),
                ptc.paste(self._viewport, viewport, group.alpha), isolate_adjustments)

    def _get_object(self, layer):
        if not layer.has_pixels() and utils.has_fill(layer):
            raise Unsupported('vector fill without pixels')
        if layer.has_vector_mask() and layer.stroke is not None and layer.stroke.enabled:
            raise Unsupported('vector stroke')
        color, cbox = self._source(layer, 'color')
        shape, sbox = self._source(layer, 'shape')
        if color is None and shape is None:
            # No pixel data at all: psd-tools composites this as fully
            # transparent (colour 1, shape 0) -- it must not cover the canvas.
            empty = np.zeros((self.height, self.width, 1), dtype=np.float32)
            return np.ones((self.height, self.width, 1), dtype=np.float32), empty, empty * 1.0
        if color is None:
            color = np.ones((self.height, self.width, 1), dtype=np.float32)
        else:
            color = ptc.paste(self._viewport, cbox, color, 1.0)
        if shape is None:
            shape = np.ones((self.height, self.width, 1), dtype=np.float32)
        else:
            shape = ptc.paste(self._viewport, sbox, shape)
        return color, shape, shape * 1.0

    def _apply_clip_layers(self, layer, color, alpha):
        clip = self._child(self._viewport, self._widen(color, self.channels), alpha,
                           layer_filter=self._layer_filter)
        for clip_layer in layer.clip_layers:
            clip.apply(clip_layer, clip_compositing=True)
        return clip.result_over_backdrop()

    def _get_mask(self, layer):
        shape = 1.0
        if layer.mask is not None and not layer.mask.disabled:
            mask, mbox = self._source(layer, 'mask')
            if mask is not None:
                shape = ptc.paste(self._viewport, mbox, mask, layer.mask.background_color / 255.0)
            if layer.mask.parameters:
                density = layer.mask.parameters.user_mask_density
                if density is None:
                    density = layer.mask.parameters.vector_mask_density
                if density is None:
                    density = 255
                density = float(density) / 255.0
                shape = density * shape + (1 - density)
        if (layer.vector_mask is not None and not layer.vector_mask.disabled and
                (not layer.has_pixels() or (not utils.has_fill(layer) and layer.mask is not None
                                            and not layer.mask.has_real()))):
            raise Unsupported('vector mask')
        return shape

    def _blend(self, color, shape, alpha, blend_mode):
        """psd-tools 1.19 _apply_source (no knockout) with fewer temporaries.

        Algebraically the same numerator: (1-shape)*a_prev*Cb + color_t
        = a_prev*Cb*(1-alpha) + alpha*((1-a_prev)*Cs + a_prev*B(Cb,Cs))."""
        color = self._fit_source(color)
        sg, ag, a0 = self._shape_g, self._alpha_g, self._alpha_0
        shape_g = sg + shape
        shape_g -= sg * shape
        alpha_g = ag + alpha
        alpha_g -= ag * alpha
        new_alpha = a0 + alpha_g
        new_alpha -= a0 * alpha_g
        a_prev, cb = self._alpha, self._color
        num = np.asarray(ptc.get_blend_func(blend_mode, self._color_mode)(cb, color), dtype=np.float32)
        if num is cb or num is color:
            num = num.copy()
        num *= a_prev
        num += color * (1.0 - a_prev)
        num *= alpha
        num += cb * (a_prev * (1.0 - alpha))
        positive = new_alpha > 0
        np.divide(num, new_alpha, out=num, where=positive)
        if not positive.all():
            np.copyto(num, 1.0, where=np.broadcast_to(~positive, num.shape))
        np.clip(num, 0.0, 1.0, out=num)
        self._shape_g, self._alpha_g, self._alpha, self._color = shape_g, alpha_g, new_alpha, num

    def _apply_source(self, color, shape, alpha, blend_mode, knockout=Knockout.NONE):
        """Blend only inside the source's coverage box.

        Outside it shape and alpha are 0, so psd-tools' formula leaves colour
        and alpha unchanged there; skipping those pixels gives identical
        results for a fraction of the work."""
        full_size = (self.height, self.width)
        if knockout or not isinstance(shape, np.ndarray) or shape.shape[:2] != full_size:
            return super()._apply_source(color, shape, alpha, blend_mode, knockout)
        if not isinstance(alpha, np.ndarray) or alpha.shape[:2] != full_size or color.shape[:2] != full_size:
            return super()._apply_source(color, shape, alpha, blend_mode, knockout)
        rows = np.flatnonzero(shape.any(axis=(1, 2)))
        if rows.size == 0:
            return
        cols = np.flatnonzero(shape[rows[0]:rows[-1] + 1].any(axis=(0, 2)))
        y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
        if (y1 - y0) * (x1 - x0) > 0.85 * self.height * self.width:
            return self._blend(color, shape, alpha, blend_mode)
        region = (slice(y0, y1), slice(x0, x1))
        sub = ScaledCompositor.__new__(ScaledCompositor)
        sub.__dict__.update(self.__dict__)
        sub._viewport = (0, 0, x1 - x0, y1 - y0)
        sub._color, sub._alpha = self._color[region], self._alpha[region]
        sub._color_0, sub._alpha_0 = self._color_0[region], self._alpha_0[region]
        sub._shape_g, sub._alpha_g = self._shape_g[region], self._alpha_g[region]
        sub._blend(color[region], shape[region], alpha[region], blend_mode)
        for name in ('_color', '_alpha', '_shape_g', '_alpha_g'):
            full = getattr(self, name)
            if full is self._color_0 or full is self._alpha_0:
                full = full.copy()   # never write into the shared backdrop
                setattr(self, name, full)
            full[region] = getattr(sub, name)

    def _apply_effects(self, layer, source):
        """psd-tools 1.19 _apply_effects, with each effect drawn once at full
        resolution (cached, downscaled) instead of per preview."""
        effects = layer.effects
        if not effects:
            return
        for name in ('coloroverlay', 'patternoverlay', 'gradientoverlay'):
            for index, effect in enumerate(ptc._styled(effects.find(name))):
                data = self._source(layer, ('overlay', name, index))
                if data is None:
                    continue
                (fill, box), shape_data = data
                color = ptc.paste(self._viewport, box, fill, 1.0)
                if shape_data is None:
                    shape_e = np.ones((self.height, self.width, 1), dtype=np.float32)
                else:
                    shape_e = ptc.paste(self._viewport, shape_data[1], shape_data[0])
                opacity = effect.opacity / 100.0
                self._apply_source(color, source.shape * shape_e, source.alpha * shape_e * opacity,
                                   effect.blend_mode)
        strokes = list(ptc._styled(effects.find('stroke')))
        if strokes:
            traces_mask = not layer.has_pixels() and utils.has_fill(layer)
            if traces_mask:
                raise Unsupported('stroke on a vector shape')
            for index, effect in enumerate(strokes):
                data = self._source(layer, ('stroke', 'stroke', index))
                if data is None:
                    continue
                (fill, box), (shape_s, sbox) = data
                color = ptc.paste(self._viewport, box, fill)
                shape = ptc.paste(self._viewport, sbox, shape_s)
                opacity = effect.opacity / 100.0
                self._apply_source(color, shape, shape * opacity, effect.blend_mode)


def effect_data(layer, kind, name, index, scale):
    """Draw one layer effect at full resolution with psd-tools and downscale it.

    Overlays depend only on the layer's box and the effect settings; a stroke
    depends on the layer's own coverage. Neither depends on other layers'
    visibility, so the result is cached per layer."""
    effect = list(ptc._styled(layer.effects.find(name)))[index]
    bbox = layer.bbox
    if kind == 'overlay':
        fill, shape_e = ptc._OVERLAY_DRAWS[name](layer, effect.value, 3)
        if fill is None:
            return None
    else:
        shape = layer.numpy('shape')
        if shape is None:
            shape = np.ones((bbox[3] - bbox[1], bbox[2] - bbox[0], 1), dtype=np.float32)
        if layer.mask is not None and not layer.mask.disabled:
            mask = layer.numpy('mask', real_mask=True)
            if mask is not None:
                shape = shape * ptc.paste(bbox, layer.mask.bbox, mask, layer.mask.background_color / 255.0)
        fill, shape_e = ptc.draw_stroke_effect(bbox, shape.astype(np.float32), effect.value, layer._psd)
    fill = np.asarray(fill, dtype=np.float32)
    if fill.ndim == 2:
        fill = fill[:, :, None]
    if fill.shape[:2] != (bbox[3] - bbox[1], bbox[2] - bbox[0]):
        # A solid colour fill comes back as a single pixel; spread it over the box.
        fill = np.broadcast_to(fill.reshape(1, 1, -1), (bbox[3] - bbox[1], bbox[2] - bbox[0], fill.shape[-1]))
    padded, box = _grid(bbox, scale, np.ascontiguousarray(fill), 1.0 if kind == 'overlay' else 0.0)
    out_fill = (_resize(padded, (box[2] - box[0], box[3] - box[1])), box)
    out_shape = None
    if shape_e is not None:
        shape_e = np.asarray(shape_e, dtype=np.float32)
        if shape_e.ndim == 2:
            shape_e = shape_e[:, :, None]
        padded, sbox = _grid(bbox, scale, np.ascontiguousarray(shape_e), 0.0)
        out_shape = (_resize(padded, (sbox[2] - sbox[0], sbox[3] - sbox[1])), sbox)
    elif kind == 'stroke':
        raise Unsupported('stroke without coverage')
    return out_fill, out_shape


import os
from concurrent.futures import ThreadPoolExecutor

_POOL = None


def _pool():
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=max(1, min(8, os.cpu_count() or 2)))
    return _POOL


def _composite_band(psd, scale, source, viewport, layer_filter, placeholder, prefix_store, prefix_key):
    widen = make_widen(psd)
    height, width = viewport[3] - viewport[1], viewport[2] - viewport[0]
    color0, alpha0 = ptc._normalize_backdrop(1.0, 0.0, height, width, 3, widen=widen)
    full_box = (0, 0, max(1, round(psd.width * scale)), max(1, round(psd.height * scale)))
    comp = ScaledCompositor(viewport, color0, alpha0, scale=scale, source=source,
                            placeholder=placeholder, full_box=full_box,
                            layer_filter=layer_filter or Layer.is_visible, widen=widen,
                            color_mode=psd.color_mode)
    items = list(psd)
    start = 0
    split = None
    if placeholder is not None and prefix_store is not None:
        top = placeholder
        while top.parent is not None and top.parent is not psd:
            top = top.parent
        split = next((i for i, item in enumerate(items) if item is top), None)
        saved = prefix_store.get((prefix_key, viewport)) if split is not None else None
        if saved is not None and saved[0] == split:
            comp._color, comp._alpha, comp._shape_g, comp._alpha_g = (a.copy() for a in saved[1])
            start = split
    for i in range(start, len(items)):
        if split is not None and i == split and start != split:
            prefix_store[(prefix_key, viewport)] = (split, tuple(a.copy() for a in
                                                    (comp._color, comp._alpha, comp._shape_g, comp._alpha_g)))
        comp.apply(items[i])
    color, _, alpha = comp.finish()
    return np.concatenate((color, alpha), 2)


def composite(psd, scale, source, layer_filter=None, placeholder=None, prefix_store=None, prefix_key=None):
    """Composite `psd` at `scale`; returns an RGB PIL image.

    Compositing is per pixel, so the canvas is split into horizontal bands
    blended in parallel. With `placeholder` (the inserted artwork layer) and a
    `prefix_store` dict, the state just before the top-level item holding the
    artwork is cached under `prefix_key`, so moving artwork only re-blends
    the layers from there up (usually just the shading)."""
    if not SUPPORTED:
        raise Unsupported('psd-tools version')
    width = max(1, round(psd.width * scale))
    height = max(1, round(psd.height * scale))
    if prefix_store is not None and any(k[0] != prefix_key for k in prefix_store):
        prefix_store.clear()
    bands = max(1, min(_pool()._max_workers, height // 64))
    edges = [round(height * i / bands) for i in range(bands + 1)]
    viewports = [(0, edges[i], width, edges[i + 1]) for i in range(bands)]
    if bands == 1:
        parts = [_composite_band(psd, scale, source, viewports[0], layer_filter, placeholder, prefix_store, prefix_key)]
    else:
        parts = list(_pool().map(lambda vp: _composite_band(psd, scale, source, vp, layer_filter,
                                                            placeholder, prefix_store, prefix_key), viewports))
    rgba = np.concatenate(parts, 0)
    # Same final step as composite_pil for an RGB document with a transparent
    # backdrop: keep alpha, then flatten as psd.composite(...).convert('RGB') does.
    pixels = np.clip(255 * rgba, 0, 255).astype(np.uint8)
    return Image.fromarray(pixels, 'RGBA').convert('RGB')


def _grid(bbox, scale, array, fill):
    """Pad `array` (in bbox coords) out to the scaled pixel grid; return it with the scaled box."""
    sbox = _scaled_box(bbox, scale)
    l, t = sbox[0] / scale, sbox[1] / scale
    r, b = sbox[2] / scale, sbox[3] / scale
    pad = (max(0, int(round(bbox[1] - t))), max(0, int(round(b - bbox[3]))),
           max(0, int(round(bbox[0] - l))), max(0, int(round(r - bbox[2]))))
    if any(pad):
        array = np.pad(array, ((pad[0], pad[1]), (pad[2], pad[3]), (0, 0)), constant_values=fill)
    return array, sbox


def _pil_grid(image, bbox, scale, fill):
    """Place a PIL image (in bbox coords) on the scaled grid and box-resize it."""
    sbox = _scaled_box(bbox, scale)
    size = (sbox[2] - sbox[0], sbox[3] - sbox[1])
    l, t = sbox[0] / scale, sbox[1] / scale
    r, b = sbox[2] / scale, sbox[3] / scale
    ox, oy = int(math.floor(bbox[0] - l)), int(math.floor(bbox[1] - t))
    cw = max(int(math.ceil(r - l)), ox + image.width)
    ch = max(int(math.ceil(b - t)), oy + image.height)
    if (ox, oy, cw, ch) != (0, 0, image.width, image.height):
        canvas = Image.new(image.mode, (cw, ch), fill)
        canvas.paste(image, (ox, oy))
        image = canvas
    box = (bbox[0] - l - ox, bbox[1] - t - oy, 0, 0)
    box = (max(0.0, box[0]), max(0.0, box[1]), min(image.width, r - l), min(image.height, b - t))
    return image.resize(size, Image.Resampling.BOX, box=box), sbox


def layer_data(layer, scale):
    """Downscaled channels for one layer: {'color': (arr, box), 'shape': ..., 'mask': ...}.

    Uses Pillow's premultiplied box filter so colour is weighted by coverage
    (transparent pixels don't bleed into edges) and the heavy lifting runs in C."""
    out = {}
    image = layer.topil(apply_icc=False) if layer.has_pixels() else None
    if image is not None:
        if image.mode not in ('RGBA', 'RGB'):
            image = image.convert('RGBA')
        if image.mode == 'RGBA':
            small, sbox = _pil_grid(image.convert('RGBa'), layer.bbox, scale, (0, 0, 0, 0))
            out['rgba'] = (np.asarray(small.convert('RGBA')), sbox)
        else:
            small, sbox = _pil_grid(image, layer.bbox, scale, (255, 255, 255))
            out['rgb'] = (np.asarray(small), sbox)
    if layer.mask is not None:
        mask = layer.numpy('mask', real_mask=True)
        if mask is not None:
            mimg = Image.fromarray(np.clip(mask[:, :, 0] * 255 + 0.5, 0, 255).astype(np.uint8), 'L')
            small, mbox = _pil_grid(mimg, layer.mask.bbox, scale, int(layer.mask.background_color))
            out['mask'] = (np.asarray(small)[:, :, None], mbox)
    return out


def as_float(data, kind):
    """(float32 array, box) for 'color' / 'shape' / 'mask' from cached uint8 data."""
    if kind == 'mask':
        if 'mask' not in data:
            return None, None
        array, box = data['mask']
        return array.astype(np.float32) / 255.0, box
    if 'rgba' in data:
        array, box = data['rgba']
        if kind == 'color':
            return array[:, :, :3].astype(np.float32) / 255.0, box
        return array[:, :, 3:4].astype(np.float32) / 255.0, box
    if 'rgb' in data:
        array, box = data['rgb']
        if kind == 'color':
            return array.astype(np.float32) / 255.0, box
        return np.ones(array.shape[:2] + (1,), dtype=np.float32), box
    return None, None


def art_data(image):
    """Source data for the inserted artwork layer (already at preview scale)."""
    array = np.asarray(image.convert('RGBA'), dtype=np.float32) / 255.0
    box = (0, 0, image.width, image.height)
    return {'color': (np.ascontiguousarray(array[:, :, :3]), box),
            'shape': (np.ascontiguousarray(array[:, :, 3:4]), box)}
