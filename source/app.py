from collections import OrderedDict
import argparse
import configparser
import base64
import io
import json
import logging
import math
import re
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
import zipfile

from flask import Flask, request, jsonify, send_file, abort
from PIL import Image, ImageGrab, ImageFont, ImageDraw, ImageColor
import numpy as np
from scipy.ndimage import binary_propagation
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from packing import tga_bytes, pack_pnt, read_pnt, field
import fastpreview
import updater

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
app = Flask(__name__, static_folder=str(ROOT/'static'))
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024
TOKEN = secrets.token_urlsafe(32)
TEMP = tempfile.TemporaryDirectory(prefix='dirt-gear-')
WORK = Path(TEMP.name)
LOCK = threading.RLock()
DOC = None
PORT = 0
LAST_HEARTBEAT = time.monotonic()
FONTS = {}
NATIVE_WINDOW = None
PREVIEW_SIZE = 1400      # long side of the interactive preview
ZOOM_PREVIEW_SIZE = 2048 # long side when zoomed in
THUMB_LOCK = threading.Lock()
RENDER_IDLE = threading.Event()   # thumbnails yield to renders
RENDER_IDLE.set()
RENDERS_ACTIVE = [0]


def installed_fonts():
    if FONTS:
        return FONTS
    roots = [Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts',
             Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData/Local')))/'Microsoft/Windows/Fonts',
             ROOT/'fonts']
    for root in roots:
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.suffix.lower() not in ('.ttf','.otf','.ttc'):
                continue
            try:
                font = ImageFont.truetype(str(path), 32)
                family, style = font.getname()
                key = path.name
                font_name = (path.name+' '+family).lower()
                FONTS[key] = {'id':key,'label':family+(' · '+style if style not in ('Regular','Normal') else ''),
                              'path':str(path),'byd':'byd' in font_name,
                              'mx':font_name.startswith('mx') or ' mx' in font_name}
            except Exception:
                continue
    return FONTS


@app.before_request
def protect():
    if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
        abort(403)
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin')
        if origin and origin != f'http://{request.host}':
            abort(403)
        candidate = (request.headers.get('X-Dirt-Token') or request.headers.get('X-Moto-Token')) or request.args.get('token', '')
        if not secrets.compare_digest(candidate, TOKEN):
            abort(403)


@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
    return response


@app.errorhandler(Exception)
def error(exc):
    from werkzeug.exceptions import HTTPException
    code = exc.code if isinstance(exc, HTTPException) else 400
    logging.exception('Dirt Gear request failed')
    return jsonify(error=str(exc)), code


def png(image, size=None):
    image = image.copy()
    if size:
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, 'PNG', compress_level=2)
    return out.getvalue()


def artwork_overlay(art):
    """The colour overlay for an added logo, or None.

    New style: art['overlay'] = {'mode': 'solid', 'color', 'strength'} or
    {'mode': 'gradient', 'start', 'end', 'angle', 'strength'}. Older projects
    store a single tint in art['color'], which is a full-strength solid overlay."""
    overlay = art.get('overlay')
    if overlay:
        return overlay
    if art.get('color'):
        return {'mode': 'solid', 'color': art['color'], 'strength': 1}
    return None


def validate_overlay(overlay):
    if overlay is None:
        return
    if not isinstance(overlay, dict) or overlay.get('mode') not in ('solid', 'gradient'):
        raise ValueError('Colour overlay must be a solid colour or a gradient.')
    keys = ('color',) if overlay['mode'] == 'solid' else ('start', 'end')
    for key in keys:
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(overlay.get(key, ''))):
            raise ValueError('Overlay colours must be six-digit hex codes.')
    strength = overlay.get('strength', 1)
    angle = overlay.get('angle', 90)
    if not isinstance(strength, (int, float)) or not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError('Overlay strength must be between 0 and 100%.')
    if not isinstance(angle, (int, float)) or not math.isfinite(angle):
        raise ValueError('Choose a valid gradient direction.')


def apply_overlay(image, overlay):
    """Recolour an RGBA image with a solid or gradient overlay, keeping its alpha.

    Strength blends from the original colours (0) to the overlay (1). Gradients
    run across the artwork's own box, so they turn with the logo."""
    if not overlay:
        return image
    image = image.convert('RGBA')
    width, height = image.size
    pixels = np.asarray(image, dtype=np.float32)
    if overlay['mode'] == 'solid':
        colour = np.broadcast_to(np.array(ImageColor.getrgb(overlay['color']), dtype=np.float32), (height, width, 3))
    else:
        start = np.array(ImageColor.getrgb(overlay['start']), dtype=np.float32)
        end = np.array(ImageColor.getrgb(overlay['end']), dtype=np.float32)
        angle = math.radians(float(overlay.get('angle', 90)))
        dx, dy = math.cos(angle), math.sin(angle)
        extent = max(1, abs(dx)*(width-1) + abs(dy)*(height-1))
        yy, xx = np.ogrid[:height, :width]
        t = np.clip(((xx-(width-1)/2)*dx + (yy-(height-1)/2)*dy)/extent + .5, 0, 1)
        colour = start + t[..., None]*(end-start)
    strength = float(overlay.get('strength', 1))
    rgb = pixels[..., :3]*(1-strength) + colour*strength
    out = np.dstack([np.clip(np.rint(rgb), 0, 255), pixels[..., 3:4]]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


class Document:
    def __init__(self, path, name):
        self.path, self.name = Path(path), name
        self.psd = PSDImage.open(path)
        if self.psd.color_mode.name != 'RGB' or self.psd.depth != 8:
            raise ValueError('V1 supports 8-bit RGB PSDs. In Photoshop, convert to RGB / 8 Bits per Channel first.')
        if max(self.psd.size) > 8192:
            raise ValueError('V1 supports PSDs up to 8192 pixels per side.')
        self.layers = {}
        self.rows = []
        self.assets = {}
        self.previews = {}
        self.preview_key = None
        self.base_preview_image = None
        self.base_render_key = None
        self.render_key = None
        self.rendered = None
        self.text_raster_cache = {}
        self.maps = None
        self.thumb_cache = {}
        self.fast_cache = fastpreview.LayerCache()
        self.fast_failed = None      # reason the fast path is unavailable for this PSD
        self.fast_images = {}        # (kind, size) -> (state key, PIL image)
        self.fast_prefix = {}        # cached compositor state below the artwork
        self.state = {'name': Path(name).stem[:99], 'artworks': [], 'visibility': {}, 'shading': '', 'placement': '', 'normal': '', 'normal_layers': [], 'spec': '', 'palette': []}
        self.walk(self.psd)
        self.pixel_cache = OrderedDict()
        self.pixel_cache_bytes = 0
        # PSD source pixels never change; only visibility and inserted art do.
        for key, layer in self.layers.items():
            original = layer.numpy
            def cached_numpy(channel=None, real_mask=True, _key=key, _read=original):
                cache_key = (_key, channel, real_mask)
                if cache_key in self.pixel_cache:
                    self.pixel_cache.move_to_end(cache_key)
                    cached = self.pixel_cache[cache_key]
                    return cached.copy() if cached is not None else None
                value = _read(channel, real_mask)
                size = value.nbytes if value is not None else 0
                budget = 192 * 1024 * 1024
                if size <= 64 * 1024 * 1024:
                    while self.pixel_cache and self.pixel_cache_bytes + size > budget:
                        _, old = self.pixel_cache.popitem(last=False)
                        self.pixel_cache_bytes -= old.nbytes if old is not None else 0
                    self.pixel_cache[cache_key] = value.copy() if value is not None else None
                    self.pixel_cache_bytes += size
                return value
            layer.numpy = cached_numpy
        normal_name = re.compile(r'\b(?:norm(?:al)?s?|normal[ _-]?map)\b', re.I)
        spec_name = re.compile(r'\b(?:spec(?:ular)?s?|reflection(?:s)?|reflect(?:ive|ivity)?)\b', re.I)
        shade_name = re.compile(r'\b(?:shading|shade|shadow(?:s)?)\b', re.I)
        normal_groups = [r for r in self.rows if r['group'] and normal_name.search(r['name']) and not spec_name.search(r['name']) and not shade_name.search(r['name'])]
        if normal_groups:
            group = sorted(normal_groups, key=lambda r:r['depth'])[0]
            self.state['normal_layers'] = [r['id'] for r in self.rows
                if r['id'].startswith(group['id']+'.') and not r['group']
                and not any((spec_name.search(a['name']) or shade_name.search(a['name']))
                            for a in self.rows if a['id'] == r['id'] or
                            (a['id'].startswith(group['id']+'.') and r['id'].startswith(a['id']+'.'))) ]
        else:
            self.state['normal_layers'] = [r['id'] for r in self.rows if not r['group'] and normal_name.search(r['name']) and not spec_name.search(r['name'])]
        self.state['normal'] = self.state['normal_layers'][0] if self.state['normal_layers'] else ''
        spec_candidates = [r for r in self.rows if r['group'] and spec_name.search(r['name']) and not normal_name.search(r['name']) and not shade_name.search(r['name'])] or [r for r in self.rows if not r['group'] and spec_name.search(r['name'])]
        if spec_candidates:
            self.state['spec'] = sorted(spec_candidates, key=lambda r:r['depth'])[0]['id']
        maps = set(self.state['normal_layers']) | ({self.state['spec']} if self.state['spec'] else set())
        def inside_map(row):
            return any(row['id'] == m or row['id'].startswith(m+'.') for m in maps)
        shade_candidates = [r for r in self.rows if shade_name.search(r['name']) and not normal_name.search(r['name']) and not spec_name.search(r['name']) and not inside_map(r)]
        if not shade_candidates:
            # Combined containers such as "4 SHADING/NORM": place artwork below
            # the whole container, which puts it under the shading inside it.
            shade_candidates = [r for r in self.rows if r['group'] and shade_name.search(r['name']) and not inside_map(r)]
        if not shade_candidates:
            extra_name = re.compile(r'\b(?:wrinkles?|folds?|creases?|ambient[ _-]?occlusion|ao|lighting|highlights?)\b', re.I)
            shade_candidates = [r for r in self.rows if extra_name.search(r['name']) and not inside_map(r)]
        if shade_candidates:
            self.state['shading'] = sorted(shade_candidates, key=lambda r:(r['depth'],not r['group']))[0]['id']
        self.state['placement'] = self.state['shading']
        self.warnings = []
        if not self.state['shading']:
            self.warnings.append('No shading layer was found by name. Drag "Your added layers" onto your shading layer so logos and text sit underneath it.')
        if any(l.kind in ('smartobject', 'type') or l.has_effects() for l in self.layers.values()):
            self.warnings.append('This PSD contains text, smart objects or effects. Existing artwork is rendered; check the preview against Photoshop before your first export.')

    def walk(self, parent, depth=0, prefix=''):
        for i, layer in enumerate(parent):
            key = prefix+str(i)
            self.layers[key] = layer
            self.rows.append({'id': key, 'name': layer.name, 'group': layer.is_group(), 'kind': layer.kind, 'depth': depth,
                              'visible': layer.visible, 'blend': layer.blend_mode.value.decode('ascii').strip()})
            self.state['visibility'][key] = layer.visible
            if layer.is_group():
                self.walk(layer, depth+1, key+'.')

    def info(self):
        def display(parent, prefix=''):
            result = []
            for i in reversed(range(len(parent))):
                key = prefix+str(i)
                result.append(next(r for r in self.rows if r['id']==key))
                if parent[i].is_group():
                    result.extend(display(parent[i], key+'.'))
            return result
        return {'filename': self.name, 'width': self.psd.width, 'height': self.psd.height,
                'layers': display(self.psd), 'state': self.state, 'warnings': self.warnings,
                'normal_candidates': self.state['normal_layers'],
                'assets': [{'id': k, 'name': v['name'], 'width': v['image'].width, 'height': v['image'].height} for k,v in self.assets.items()]}

    def thumbnail(self, key):
        if key not in self.thumb_cache:
            layer = self.layers[key]
            if layer.is_group():
                # Rendering a whole 4K group for a 36px icon can stall the editor.
                def kids(group):
                    return [item for item in list(group) if item.name != 'Dirt Gear artwork']
                items = kids(layer)
                child = next((item for item in reversed(items) if item.visible), items[-1] if items else None)
                while child is not None and child.is_group():
                    items = kids(child)
                    child = next((item for item in reversed(items) if item.visible), items[-1] if items else None)
                image = self.preview_pixels(child) if child is not None else None
            else:
                image = self.preview_pixels(layer)
            tile = Image.new('RGBA', (36, 36), (35, 39, 42, 255))
            if image is not None:
                image = image.convert('RGBA')
                image.thumbnail((34, 34), Image.Resampling.BOX, reducing_gap=2.0)
                tile.alpha_composite(image, ((36-image.width)//2, (36-image.height)//2))
            self.thumb_cache[key] = png(tile)
        return self.thumb_cache[key]

    def preview_pixels(self, layer):
        """A layer's pixels at preview scale, shared with the preview cache."""
        key = next((k for k, l in self.layers.items() if l is layer), None)
        if key is None or self.fast_failed is not None or not fastpreview.SUPPORTED:
            return layer.topil()
        scale = min(1.0, PREVIEW_SIZE / max(self.psd.size))
        try:
            data = self.fast_cache.get((key, scale), lambda: fastpreview.layer_data(layer, scale))
        except Exception:
            return layer.topil()
        if 'rgba' in data:
            return Image.fromarray(data['rgba'][0], 'RGBA')
        if 'rgb' in data:
            return Image.fromarray(data['rgb'][0], 'RGB')
        return None

    def update(self, data):
        # Requests can reach the server out of order (threads waiting on the
        # lock aren't served first-come-first-served). The editor stamps each
        # request with an increasing number; an older one must never put back
        # visibility or artwork the user has already changed.
        rev = data.get('rev')
        if isinstance(rev, (int, float)) and math.isfinite(rev):
            if rev < getattr(self, 'last_rev', 0):
                return
            self.last_rev = rev
        for key in ('shading', 'normal', 'spec'):
            val = data.get(key, self.state[key])
            if val and val not in self.layers:
                raise ValueError('Choose an existing layer for '+key)
            self.state[key] = val
        placement = data.get('placement', self.state['placement'])
        if placement and placement not in self.layers:
            raise ValueError('Choose an existing PSD layer for your artwork.')
        if placement and any(placement == key or placement.startswith(key+'.') for key in
                             self.state['normal_layers'] + ([self.state['spec']] if self.state['spec'] else [])):
            raise ValueError('Artwork cannot be placed inside a Norm or Spec map.')
        self.state['placement'] = placement
        normal_layers = data.get('normal_layers')
        if normal_layers is None:
            normal_layers = [data['normal']] if 'normal' in data and data['normal'] else self.state['normal_layers']
        if not isinstance(normal_layers, list) or len(normal_layers) > len(self.layers) or any(k not in self.layers or self.layers[k].is_group() for k in normal_layers):
            raise ValueError('Choose valid Normal map layers.')
        self.state['normal_layers'] = list(dict.fromkeys(normal_layers))
        self.state['normal'] = self.state['normal_layers'][0] if self.state['normal_layers'] else ''
        palette = data.get('palette', self.state['palette'])
        if not isinstance(palette, list) or len(palette) > 32 or any(not isinstance(c,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',c) for c in palette):
            raise ValueError('Palette colours must use exact six-digit hex codes.')
        self.state['palette'] = list(dict.fromkeys(c.upper() for c in palette))
        for key,val in data.get('visibility', {}).items():
            if key in self.layers:
                self.state['visibility'][key] = bool(val)
        self.state['name'] = str(data.get('name', self.state['name']))[:99]
        artworks = data.get('artworks', self.state['artworks'])
        if len(artworks) > 100:
            raise ValueError('V1 supports up to 100 artwork layers.')
        for art in artworks:
            if art.get('asset') not in self.assets:
                raise ValueError('Missing artwork image. Add it again.')
            for key in ('x','y','width','height','rotation','opacity'):
                if not isinstance(art.get(key), (int, float)) or not math.isfinite(art[key]):
                    raise ValueError('Invalid artwork position')
            if not (1 <= art['width'] <= 16384 and 1 <= art['height'] <= 16384 and 0 <= art['opacity'] <= 1):
                raise ValueError('Artwork dimensions or opacity are out of range')
            if art.get('color') and not re.fullmatch(r'#[0-9a-fA-F]{6}', art['color']):
                raise ValueError('Artwork colour must be a six-digit hex code.')
            validate_overlay(art.get('overlay'))
        self.state['artworks'] = artworks

    def set_visibility(self):
        for key, layer in self.layers.items():
            layer.visible = self.state['visibility'][key]
        for key in self.state['normal_layers'] + ([self.state['spec']] if self.state['spec'] else []):
            self.layers[key].visible = False

    def composite_default(self, artwork=True, exclude_shading=False):
        cache_key = json.dumps({k:self.state[k] for k in ('visibility','shading','placement','normal_layers','spec','artworks')},sort_keys=True)
        if artwork and not exclude_shading and cache_key == self.render_key:
            return self.rendered.copy()
        base_key = json.dumps({k:self.state[k] for k in ('visibility','shading','normal_layers','spec')}, sort_keys=True)
        self.set_visibility()
        if exclude_shading and self.state['shading']:
            self.layers[self.state['shading']].visible = False
        added = None
        try:
            if artwork and self.state['artworks']:
                target = self.layers.get(self.state['placement'])
                parent = target.parent if target is not None else self.psd
                art_image = self.art_image()
                added = PixelLayer.frompil(art_image, parent, name='Dirt Gear artwork')
                parent.remove(added)
                parent.insert(parent.index(target) if target is not None else len(parent), added)
            # Re-composite only the affected rectangle when the PSD has no
            # clipping/adjustment/effect dependencies outside that rectangle.
            local_layers = all(l.kind in ('pixel','group','smartobject','type') and
                               not l.clipping and not l.has_effects() for l in self.layers.values())
            region = art_image.getbbox() if added is not None else None
            if (region and local_layers and not exclude_shading and
                    self.base_preview_image is not None and self.base_render_key == base_key):
                result = self.base_preview_image.copy()
                patch = self.psd.composite(viewport=region, ignore_preview=True, apply_icc=False).convert('RGB')
                result.paste(patch, region[:2])
            else:
                result = self.psd.composite(ignore_preview=True, apply_icc=False).convert('RGB')
            if artwork and not exclude_shading:
                self.render_key, self.rendered = cache_key, result.copy()
            return result
        finally:
            if added is not None:
                added.parent.remove(added)

    def art_image(self):
        result = Image.new('RGBA', self.psd.size)
        for art in self.state['artworks']:
            if not art.get('visible', True):
                continue
            source = self.assets[art['asset']]['image'].copy().convert('RGBA')
            text_settings = art.get('text')
            if text_settings and text_settings.get('font') in installed_fonts():
                base_width = max(1,text_settings.get('base_width',source.width))
                base_height = max(1,text_settings.get('base_height',source.height))
                scale = max(1,art['width']/base_width,art['height']/base_height)
                scale = min(scale,8192/max(base_width,base_height),
                            (32*1024*1024/(base_width*base_height))**.5)
                if scale > 1.05 and (source.width < art['width'] or source.height < art['height']):
                    cache_key=(art['asset'],round(art['width']),round(art['height']))
                    if cache_key not in self.text_raster_cache:
                        if len(self.text_raster_cache)>=8:
                            self.text_raster_cache.clear()
                        self.text_raster_cache[cache_key]=render_text_bitmap(text_settings,scale)
                    source=self.text_raster_cache[cache_key].copy()
            source = apply_overlay(source, artwork_overlay(art))
            source = source.resize((round(art['width']), round(art['height'])), Image.Resampling.LANCZOS)
            if art['opacity'] < 1:
                source.putalpha(source.getchannel('A').point(lambda v: round(v*art['opacity'])))
            source = source.rotate(-art['rotation'], Image.Resampling.BICUBIC, expand=True)
            result.alpha_composite(source, (round(art['x']-source.width/2), round(art['y']-source.height/2)))
        return result

    def isolated(self, key):
        if key == 'spec' and not self.state['spec']:
            return Image.new('RGBA', self.psd.size, (0, 0, 0, 0))
        if key == 'normal' and len(self.state['normal_layers']) > 1:
            return self.composite_normals()
        layer = self.layers.get(self.state[key])
        if layer is None:
            raise ValueError('Choose the '+key+' layer in Template setup.')
        old = layer.visible
        layer.visible = True
        try:
            return layer.composite(viewport=(0,0,*self.psd.size), force=False, apply_icc=False).convert('RGBA')
        finally:
            layer.visible = old

    def composite_normals(self):
        selected = {self.layers[key] for key in self.state['normal_layers']}
        needed = set(selected)
        for layer in selected:
            parent = layer.parent
            while parent is not self.psd:
                needed.add(parent)
                parent = parent.parent
        previous = {layer: layer.visible for layer in self.layers.values()}
        try:
            for layer in self.layers.values():
                layer.visible = layer in needed
            return self.psd.composite(ignore_preview=True, apply_icc=False).convert('RGBA')
        finally:
            for layer, visible in previous.items():
                layer.visible = visible

    def prepare_preview(self):
        key = json.dumps({k:self.state[k] for k in ('visibility','shading','normal_layers','spec')}, sort_keys=True)
        if key == self.preview_key:
            return
        image = self.fast_composite(False, PREVIEW_SIZE)
        self.previews = {'default': png(image, PREVIEW_SIZE)}
        self.preview_key = key

    # -- fast interactive preview ------------------------------------------
    def _fast_source(self, scale, art=None, placeholder=None):
        ids = {id(layer): key for key, layer in self.layers.items()}
        def source(layer, kind):
            if placeholder is not None and layer is placeholder:
                return (art[kind] if art and art.get(kind) is not None else (None, None))
            key = ids.get(id(layer))
            if key is None:
                raise fastpreview.Unsupported('unknown layer')
            if isinstance(kind, tuple):   # a layer effect, drawn once and cached
                return self.fast_cache.get((key, scale) + kind,
                                           lambda: fastpreview.effect_data(layer, kind[0], kind[1], kind[2], scale))
            data = self.fast_cache.get((key, scale), lambda: fastpreview.layer_data(layer, scale))
            return fastpreview.as_float(data, kind)
        return source

    def _prefetch(self, scale):
        """Decode visible layers in parallel before compositing (first open)."""
        from concurrent.futures import ThreadPoolExecutor
        todo = [(k, l) for k, l in self.layers.items()
                if not l.is_group() and l.is_visible() and (k, scale) not in self.fast_cache.data]
        if len(todo) < 2:
            return
        def work(item):
            key, layer = item
            self.fast_cache.get((key, scale), lambda: fastpreview.layer_data(layer, scale))
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as pool:
            list(pool.map(work, todo))

    def fast_composite(self, artwork=True, size=PREVIEW_SIZE):
        RENDERS_ACTIVE[0] += 1
        RENDER_IDLE.clear()
        try:
            return self._fast_composite_cached(artwork, size)
        finally:
            RENDERS_ACTIVE[0] -= 1
            if RENDERS_ACTIVE[0] <= 0:
                RENDERS_ACTIVE[0] = 0
                RENDER_IDLE.set()

    def _fast_composite_cached(self, artwork, size):
        """Preview-resolution composite (long side `size`), artwork under the chosen layer.

        Uses psd-tools' blend maths on cached downscaled layers; falls back to
        the exact full-resolution composite if the PSD needs something the
        fast path cannot reproduce."""
        scale = min(1.0, size / max(self.psd.size))
        key = json.dumps({k:self.state[k] for k in ('visibility','shading','placement','normal_layers','spec')
                          } | {'artworks': self.state['artworks'] if artwork else []}, sort_keys=True)
        cached = self.fast_images.get((artwork, size))
        if cached and cached[0] == key:
            return cached[1].copy()
        if self.fast_failed is None:
            try:
                image = self._fast_composite(artwork, scale)
            except fastpreview.Unsupported as exc:
                self.fast_failed = str(exc)
                logging.warning('Fast preview unavailable (%s); using full rendering', exc)
            except Exception:
                self.fast_failed = 'error'
                logging.exception('Fast preview failed; using full rendering')
        if self.fast_failed is not None:
            image = self.composite_default(artwork)
            image = image.copy()
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
        if len(self.fast_images) > 6:
            self.fast_images.clear()
        self.fast_images[(artwork, size)] = (key, image.copy())
        return image

    def _fast_composite(self, artwork, scale):
        self.set_visibility()
        self._prefetch(scale)
        placeholder = None
        art = None
        try:
            if artwork and self.state['artworks']:
                target = self.layers.get(self.state['placement'])
                parent = target.parent if target is not None else self.psd
                art = fastpreview.art_data(self.art_image_scaled(scale))
                placeholder = PixelLayer.frompil(Image.new('RGBA', (1, 1)), parent, name='Dirt Gear artwork')
                parent.remove(placeholder)
                parent.insert(parent.index(target) if target is not None else len(parent), placeholder)
            prefix_key = json.dumps([scale, self.state['visibility'], self.state['normal_layers'],
                                     self.state['spec'], self.state['placement']], sort_keys=True)
            return fastpreview.composite(self.psd, scale, self._fast_source(scale, art, placeholder),
                                         placeholder=placeholder, prefix_store=self.fast_prefix,
                                         prefix_key=prefix_key)
        finally:
            if placeholder is not None:
                placeholder.parent.remove(placeholder)

    def art_image_scaled(self, scale):
        """The artwork layer rendered directly at preview scale."""
        width = max(1, round(self.psd.width * scale))
        height = max(1, round(self.psd.height * scale))
        result = Image.new('RGBA', (width, height))
        for art in self.state['artworks']:
            if not art.get('visible', True):
                continue
            source = self.assets[art['asset']]['image'].convert('RGBA')
            text_settings = art.get('text')
            w, h = max(1, round(art['width'] * scale)), max(1, round(art['height'] * scale))
            if text_settings and text_settings.get('font') in installed_fonts():
                base_width = max(1, text_settings.get('base_width', source.width))
                base_height = max(1, text_settings.get('base_height', source.height))
                need = max(w / base_width, h / base_height)
                if need > 1.05 and (source.width < w or source.height < h):
                    cache_key = (art['asset'], w, h)
                    if cache_key not in self.text_raster_cache:
                        if len(self.text_raster_cache) >= 8:
                            self.text_raster_cache.clear()
                        self.text_raster_cache[cache_key] = render_text_bitmap(text_settings, min(need, 8))
                    source = self.text_raster_cache[cache_key]
            source = apply_overlay(source, artwork_overlay(art))
            source = source.resize((w, h), Image.Resampling.LANCZOS)
            if art['opacity'] < 1:
                source.putalpha(source.getchannel('A').point(lambda v: round(v*art['opacity'])))
            source = source.rotate(-art['rotation'], Image.Resampling.BICUBIC, expand=True)
            result.alpha_composite(source, (round(art['x']*scale-source.width/2), round(art['y']*scale-source.height/2)))
        return result

    def textures(self):
        if not self.state['normal_layers']:
            raise ValueError('Dirt Gear could not find a Normal map group or layer in this PSD.')
        return {'rider': tga_bytes(self.composite_default()),
                'rider_n': tga_bytes(self.isolated('normal'), True),
                'rider_r': tga_bytes(self.isolated('spec'), True)}


def require_doc():
    if DOC is None:
        raise ValueError('Open a PSD first.')
    return DOC


@app.get('/')
def home():
    return send_file(ROOT/'static/index.html')


@app.get('/api/document')
def info():
    with LOCK:
        return jsonify(DOC.info() if DOC else None)


@app.get('/api/platform')
def platform_info():
    return jsonify(desktop=NATIVE_WINDOW is not None, version=updater.app_version(),
                   updates=bool(updater.update_repo()))


# -- updates --------------------------------------------------------------
def settings_path():
    return local_app_data()/APP_DATA_NAME/'settings.json'


def load_settings():
    try:
        data = json.loads(settings_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(changes):
    data = load_settings() | changes
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(data, indent=1), encoding='utf-8')
    temporary.replace(path)
    return data


def updates_folder():
    return local_app_data()/APP_DATA_NAME/'updates'


@app.get('/api/update/check')
def update_check():
    settings = load_settings()
    manual = request.args.get('manual') == '1'
    if not manual and not settings.get('check_on_start', True):
        return jsonify(enabled=bool(updater.update_repo()), current=updater.app_version(),
                       available=False, check_on_start=False)
    result = updater.check()
    result['check_on_start'] = settings.get('check_on_start', True)
    result['skipped'] = bool(result.get('available') and not manual and
                             settings.get('skip_version') == result.get('latest'))
    result['can_install'] = bool(result.get('signed') and getattr(sys, 'frozen', False) and os.name == 'nt')
    result.pop('installer', None)
    return jsonify(result)


@app.post('/api/update/settings')
def update_settings():
    data = request.get_json() or {}
    changes = {}
    if 'check_on_start' in data:
        changes['check_on_start'] = bool(data['check_on_start'])
    if 'skip_version' in data:
        changes['skip_version'] = str(data['skip_version'] or '')[:20]
    return jsonify(save_settings(changes))


@app.post('/api/update/open-page')
def update_open_page():
    result = updater.check()
    page = result.get('page') or (f"https://github.com/{updater.update_repo()}/releases/latest" if updater.update_repo() else '')
    if not page.startswith('https://github.com/'):
        raise ValueError('No download page is available.')
    webbrowser.open(page)
    return jsonify(ok=True, page=page)


@app.post('/api/update/install')
def update_install():
    if not (getattr(sys, 'frozen', False) and os.name == 'nt'):
        raise ValueError('Updates install from the installed Windows app.')
    result = updater.check()
    info = result.get('installer')
    if not (result.get('available') and result.get('signed') and info):
        raise ValueError('This update is not signed, so it can only be downloaded from the release page.')
    installer = updater.download(info, updates_folder())
    target = Path(sys.executable).resolve().parent
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(installer), '--update', '--target', str(target), '--wait-pid', str(os.getpid())],
                     creationflags=flags, close_fds=True, cwd=str(installer.parent))

    def close_for_update():
        try:
            if NATIVE_WINDOW is not None:
                NATIVE_WINDOW.destroy()
                return
        except Exception:
            logging.exception('Could not close the window for the update')
        os._exit(0)
    threading.Timer(1.5, close_for_update).start()
    return jsonify(ok=True, version=result.get('latest'))


@app.post('/api/heartbeat')
def heartbeat():
    global LAST_HEARTBEAT
    LAST_HEARTBEAT = time.monotonic()
    return jsonify(ok=True)


@app.post('/api/open')
def open_psd():
    global DOC
    file = request.files['file']
    with LOCK:
        path = WORK/(uuid.uuid4().hex+'.psd')
        file.save(path)
        doc = Document(path, Path(file.filename).name)
        DOC = doc
        return jsonify(doc.info())


@app.post('/api/setup')
def setup():
    with LOCK:
        doc = require_doc()
        doc.update(request.get_json())
        doc.prepare_preview()
        return jsonify(doc.info())


@app.get('/api/preview/<kind>')
def preview(kind):
    with LOCK:
        doc = require_doc()
        if request.args.get('full') == '1' and kind in ('default','proof'):
            if kind == 'proof' and request.args.get('exact') == '1':
                if doc.rendered is None:
                    abort(404)
                return send_file(io.BytesIO(png(doc.rendered, min(4096, max(doc.psd.size)))), mimetype='image/png')
            image = doc.fast_composite(kind == 'proof', ZOOM_PREVIEW_SIZE)
            return send_file(io.BytesIO(png(image)), mimetype='image/png')
        if kind in ('normal', 'spec') and kind not in doc.previews and (doc.state[kind] or kind == 'spec'):
            doc.previews[kind] = png(doc.isolated(kind).convert('RGB'), 1400)
        if kind not in doc.previews:
            abort(404)
        return send_file(io.BytesIO(doc.previews[kind]), mimetype='image/png')


def add_asset(data, name):
    doc = require_doc()
    image = Image.open(io.BytesIO(data))
    if image.width*image.height > 64*1024*1024:
        raise ValueError('Artwork must be smaller than 64 megapixels.')
    image = image.convert('RGBA')
    key = uuid.uuid4().hex
    doc.assets[key] = {'name': name, 'image': image}
    return {'id': key, 'name': name, 'width': image.width, 'height': image.height}


@app.post('/api/artwork')
def artwork():
    with LOCK:
        file = request.files['file']
        return jsonify(add_asset(file.read(), Path(file.filename).name))


@app.get('/api/fonts')
def fonts():
    return jsonify(sorted([{k:v for k,v in f.items() if k!='path'} for f in installed_fonts().values()],
                          key=lambda f:(not f['byd'],f['label'].lower())))


def text_tracking(settings):
    """Letter spacing as a percentage of the font size (-50 to 200; 0 = font default)."""
    try:
        value = float(settings.get('tracking', 0) or 0)
    except (TypeError, ValueError):
        raise ValueError('Letter spacing must be a number.')
    if not math.isfinite(value) or not -50 <= value <= 200:
        raise ValueError('Letter spacing must be between -50% and 200%.')
    return value


def _tracked_layout(value, font, stroke, spacing, tracking_px):
    """Character positions for centred multi-line text with extra spacing.

    Each character sits where the font itself places it in the line (so pair
    kerning like a 6 tucked under a 7 is kept) plus the extra spacing."""
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    line_height = probe.textbbox((0, 0), 'A', font=font, stroke_width=stroke)[3] + stroke + spacing
    lines = value.split('\n')
    widths = [font.getlength(line) + tracking_px * max(0, len(line) - 1) for line in lines]
    widest = max(widths) if widths else 0
    glyphs = []
    for row, line in enumerate(lines):
        x0 = (widest - widths[row]) / 2
        for i, ch in enumerate(line):
            if ch.strip():
                # Position inside the full line, kerning with the previous
                # character included, then the extra spacing on top.
                x = font.getlength(line[:i + 1]) - font.getlength(ch)
                glyphs.append((x0 + x + tracking_px * i, row * line_height, ch))
    if not glyphs:
        raise ValueError('Enter a name or number.')
    boxes = [probe.textbbox((x, y), ch, font=font, stroke_width=stroke) for x, y, ch in glyphs]
    bounds = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return glyphs, bounds


def render_text_bitmap(settings, scale=1):
    fontinfo = installed_fonts().get(settings.get('font'))
    if fontinfo is None:
        raise ValueError('Choose a font installed on this PC.')
    size = max(1, round(int(settings['size'])*scale))
    stroke = max(0, round(int(settings.get('stroke',0))*scale))
    font = ImageFont.truetype(fontinfo['path'], size)
    value = settings['value']
    spacing = round(size*.12)
    tracking = text_tracking(settings)
    tracking_px = size * tracking / 100
    fill_colour = ImageColor.getrgb(settings.get('fill','#ffffff'))
    outline_colour = ImageColor.getrgb(settings.get('outline','#000000'))
    gradient = settings.get('gradient')
    margin = max(4,round(4*scale))
    if tracking == 0:
        bounds = ImageDraw.Draw(Image.new('RGBA',(1,1))).multiline_textbbox((0,0),value,font=font,stroke_width=stroke,spacing=spacing,align='center')
    else:
        glyphs, bounds = _tracked_layout(value, font, stroke, spacing, tracking_px)
    # Round away float noise first so a near-zero spacing can't add a pixel.
    width,height=math.ceil(round(bounds[2]-bounds[0],3))+2*margin,math.ceil(round(bounds[3]-bounds[1],3))+2*margin
    if width*height>64*1024*1024 or max(width,height)>16384:
        raise ValueError('Text is too large. Reduce its size or length.')
    im=Image.new('RGBA',(width,height))
    ox, oy = margin-bounds[0], margin-bounds[1]

    def draw_text(target, fill, with_stroke):
        draw = ImageDraw.Draw(target)
        if tracking == 0:
            draw.multiline_text((ox, oy), value, font=font, fill=fill,
                                stroke_width=stroke if with_stroke else 0, stroke_fill=outline_colour,
                                spacing=spacing, align='center')
            return
        for x, y, ch in glyphs:
            draw.text((ox + x, oy + y), ch, font=font, fill=fill,
                      stroke_width=stroke if with_stroke else 0, stroke_fill=outline_colour)

    if tracking == 0:
        draw_text(im, (0,0,0,0) if gradient else fill_colour, True)
    else:
        # Outlines first, then fills, so tight spacing never lets one letter's
        # outline cover the next letter's fill.
        if stroke:
            draw_text(im, outline_colour, True)
        if not gradient:
            draw_text(im, fill_colour, False)
    if gradient:
        start = np.array(ImageColor.getrgb(gradient['start']), dtype=np.float32)
        end = np.array(ImageColor.getrgb(gradient['end']), dtype=np.float32)
        angle = math.radians(float(gradient.get('angle', 90)))
        if not math.isfinite(angle):
            raise ValueError('Choose a finite gradient angle.')
        dx, dy = math.cos(angle), math.sin(angle)
        extent = max(1, abs(dx)*(width-1) + abs(dy)*(height-1))
        yy, xx = np.ogrid[:height, :width]
        t = np.clip(((xx-(width-1)/2)*dx + (yy-(height-1)/2)*dy)/extent + .5, 0, 1)
        colours = np.rint(start + t[..., None]*(end-start)).astype(np.uint8)
        fill = Image.fromarray(colours, 'RGB').convert('RGBA')
        mask = Image.new('L', im.size)
        draw_text(mask, 255, False)
        fill.putalpha(mask)
        im.alpha_composite(fill)
    return im


@app.post('/api/text/preview')
def text_preview():
    settings = dict(request.get_json())
    value = str(settings.get('value', '')).strip()
    if not value or len(value) > 200 or value.count('\n') > 5:
        raise ValueError('Enter up to 200 characters and six lines.')
    size, stroke = int(settings.get('size', 240)), int(settings.get('stroke', 0))
    if not 8 <= size <= 1600 or not 0 <= stroke <= 80:
        raise ValueError('Text size must be 8–1600, outline 0–80.')
    settings.update(value=value, size=size, stroke=stroke, tracking=text_tracking(settings))
    # Bound raster work independently of the eventual full-resolution artwork.
    preview = render_text_bitmap(settings, min(1, 96 / size))
    preview.thumbnail((960, 280), Image.Resampling.LANCZOS)
    return send_file(io.BytesIO(png(preview)), mimetype='image/png', max_age=0)


@app.post('/api/text')
def text_art():
    with LOCK:
        require_doc()
        settings = request.get_json()
        value = str(settings.get('value','')).strip()
        if not value or len(value)>200 or value.count('\n')>5:
            raise ValueError('Enter a name or number (up to 200 characters and six lines).')
        size = int(settings.get('size',240))
        stroke = int(settings.get('stroke',0))
        if not 8<=size<=1600 or not 0<=stroke<=80:
            raise ValueError('Text size must be 8–1600, outline 0–80.')
        settings['size'],settings['stroke'],settings['value']=size,stroke,value
        settings['tracking'] = text_tracking(settings)
        logical = render_text_bitmap(settings)
        max_side=max(logical.size)
        scale=min(4, max(require_doc().psd.size)/max_side, (32*1024*1024/(logical.width*logical.height))**.5)
        high_res=render_text_bitmap(settings,max(1,scale)) if scale>1.1 else logical
        key=uuid.uuid4().hex
        name=value.replace('\n',' ')
        require_doc().assets[key]={'name':name,'image':high_res}
        result={'id':key,'name':name,'width':logical.width,'height':logical.height}
        result['text']={'value':value,'font':settings['font'],'size':size,'stroke':stroke,
                        'fill':settings.get('fill','#ffffff'),'outline':settings.get('outline','#000000'),
                        'base_width':logical.width,'base_height':logical.height, 'gradient':settings.get('gradient'),
                        'tracking':settings['tracking']}
        return jsonify(result)


@app.get('/api/artwork/<key>')
def asset(key):
    with LOCK:
        item = require_doc().assets.get(key)
        if not item:
            abort(404)
        return send_file(io.BytesIO(png(item['image'])), mimetype='image/png')


@app.get('/api/layer/thumbnail/<key>')
def layer_thumbnail(key):
    # Thumbnails only read layer pixels, so they don't wait behind a render.
    doc = require_doc()
    if key not in doc.layers:
        abort(404)
    if key not in doc.thumb_cache:
        RENDER_IDLE.wait(timeout=120)   # let the preview render finish first
    with THUMB_LOCK:
        data = doc.thumbnail(key)
    response = send_file(io.BytesIO(data), mimetype='image/png')
    response.headers['Cache-Control'] = 'private, max-age=86400, immutable'
    return response


@app.post('/api/clipboard')
def clipboard():
    with LOCK:
        require_doc()
        # Windows often supplies several formats for one copy. Prefer vector or
        # alpha-preserving PNG before the flattened bitmap returned by ImageGrab.
        import ctypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
        user32.RegisterClipboardFormatW.restype = ctypes.c_uint
        user32.GetClipboardData.restype = ctypes.c_void_p
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
        kernel32.GlobalSize.restype = ctypes.c_size_t
        if user32.OpenClipboard(None):
            try:
                for fmt in ('image/svg+xml','image/svg','SVG','PNG','image/png'):
                    handle = user32.GetClipboardData(user32.RegisterClipboardFormatW(fmt))
                    if handle:
                        size = kernel32.GlobalSize(handle)
                        if size > 64*1024*1024:
                            raise ValueError('Clipboard artwork is too large.')
                        ptr = kernel32.GlobalLock(handle)
                        if ptr:
                            try:
                                data = ctypes.string_at(ptr, size)
                            finally:
                                kernel32.GlobalUnlock(handle)
                            if 'svg' in fmt.lower():
                                encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-16-le' if b'\0' in data[:80] else 'utf-8-sig'
                                return jsonify(svg=data.decode(encoding).rstrip('\0'))
                            if data.startswith(b'\x89PNG\r\n\x1a\n'):
                                return jsonify(add_asset(data, 'Pasted artwork'))
            finally:
                user32.CloseClipboard()
        image = ImageGrab.grabclipboard()
        if isinstance(image, Image.Image):
            return jsonify(add_asset(png(image), 'Pasted artwork'))
        raise ValueError('No supported image on the clipboard. In Illustrator enable SVG or bitmap copying, or export an SVG/PNG and add it here.')


def remove_white_background(image):
    pixels = np.array(image.convert('RGBA'))
    near_white = np.min(pixels[:, :, :3], axis=2) >= 240
    near_white &= pixels[:, :, 3] >= 250
    seeds = np.zeros(near_white.shape, dtype=bool)
    seeds[0, :] = near_white[0, :]
    seeds[-1, :] = near_white[-1, :]
    seeds[:, 0] = near_white[:, 0]
    seeds[:, -1] = near_white[:, -1]
    if not seeds.any():
        raise ValueError('No white background touches the image edges. This artwork may already be transparent.')
    background = binary_propagation(seeds, mask=near_white)
    pixels[background, 3] = 0
    return Image.fromarray(pixels, 'RGBA')


@app.post('/api/artwork/remove-white')
def remove_white_artwork():
    with LOCK:
        doc = require_doc()
        source = doc.assets.get(request.get_json().get('asset'))
        if source is None:
            raise ValueError('Select the pasted artwork first.')
        cleaned = remove_white_background(source['image'])
        key = uuid.uuid4().hex
        doc.assets[key] = {'name': source['name']+' (transparent)', 'image': cleaned}
        return jsonify({'id':key, 'name':doc.assets[key]['name'], 'width':cleaned.width, 'height':cleaned.height})


@app.post('/api/sample-colour')
def sample_colour():
    with LOCK:
        doc = require_doc()
        data = request.get_json()
        x, y = int(data['x']), int(data['y'])
        if not (0 <= x < doc.psd.width and 0 <= y < doc.psd.height):
            raise ValueError('Click inside the gear texture.')
        image = doc.fast_composite(False, ZOOM_PREVIEW_SIZE)
        sx = min(image.width-1, int(x * image.width / doc.psd.width))
        sy = min(image.height-1, int(y * image.height / doc.psd.height))
        rgb = image.getpixel((sx, sy))[:3]
        return jsonify(colour='#' + ''.join(f'{v:02x}' for v in rgb))


def library_root():
    root = project_library().parent / 'Logos'
    root.mkdir(parents=True, exist_ok=True)
    return root


def library_item(key):
    if not re.fullmatch(r'[0-9a-f]{32}', key):
        abort(404)
    path = library_root() / (key + '.png')
    if not path.is_file():
        abort(404)
    return path


def layouts_root():
    root = project_library().parent / 'Layouts'
    root.mkdir(parents=True, exist_ok=True)
    return root


def layout_path(key):
    if not re.fullmatch(r'[0-9a-f]{32}', key):
        abort(404)
    path = layouts_root() / (key + '.zip')
    if not path.is_file():
        abort(404)
    return path


@app.get('/api/layouts')
def list_layouts():
    items = []
    for path in layouts_root().glob('*.zip'):
        try:
            with zipfile.ZipFile(path) as z:
                data = json.loads(z.read('layout.json'))
            items.append({'id':path.stem, 'name':data['name'], 'count':len(data['artworks'])})
        except (ValueError, OSError, KeyError, zipfile.BadZipFile):
            continue
    return jsonify(items)


@app.post('/api/layouts')
def save_layout():
    with LOCK:
        doc = require_doc()
        data = request.get_json()
        doc.update(data['state'])
        if not doc.state['artworks']:
            raise ValueError('Add logos, a name or a number before saving a layout.')
        name = str(data.get('name') or doc.state['name']).strip()[:100]
        if not name:
            raise ValueError('Enter a layout name.')
        key = uuid.uuid4().hex
        target = layouts_root() / (key + '.zip')
        temporary = target.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('layout.json', json.dumps({'version':1, 'name':name, 'size':doc.psd.size,
                    'artworks':doc.state['artworks'], 'palette':doc.state['palette']}))
                for asset in {a['asset'] for a in doc.state['artworks']}:
                    z.writestr('assets/'+asset+'.png', png(doc.assets[asset]['image']))
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return jsonify(id=key, name=name)


@app.post('/api/layouts/<key>/add')
def add_layout(key):
    with LOCK:
        doc = require_doc()
        with zipfile.ZipFile(layout_path(key)) as z:
            data = json.loads(z.read('layout.json'))
            if data.get('version') != 1 or not 0 < len(data['artworks']) <= 100:
                raise ValueError('Unsupported layout.')
            sx, sy = doc.psd.width/data['size'][0], doc.psd.height/data['size'][1]
            assets, mapping, artworks = [], {}, []
            # Stage all images first; a failed import cannot partially add artwork.
            for art in data['artworks']:
                old = art['asset']
                if old not in mapping:
                    image = Image.open(io.BytesIO(z.read('assets/'+old+'.png')))
                    if image.width*image.height > 64*1024*1024:
                        raise ValueError('Layout image is too large.')
                    image = image.convert('RGBA')
                    new = uuid.uuid4().hex
                    mapping[old] = new
                    assets.append((new, {'name':art['name'], 'image':image}))
                item = dict(art, id=uuid.uuid4().hex, asset=mapping[old])
                for prop, factor in [('x',sx),('width',sx),('y',sy),('height',sy)]:
                    item[prop] *= factor
                if not (1 <= item['width'] <= 16384 and 1 <= item['height'] <= 16384):
                    raise ValueError('This layout is too large or too small for this template.')
                artworks.append(item)
        doc.assets.update(assets)
        return jsonify(artworks=artworks, palette=data.get('palette', []), assets=[
            {'id':k, 'name':v['name'], 'width':v['image'].width, 'height':v['image'].height} for k,v in assets])


@app.delete('/api/layouts/<key>')
def delete_layout(key):
    with LOCK:
        layout_path(key).unlink()
        return jsonify(deleted=key)


@app.get('/api/logos')
def logos():
    items = []
    for path in library_root().glob('*.json'):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
            if (path.with_suffix('.png')).is_file():
                items.append(item)
        except (ValueError, OSError):
            continue
    return jsonify(items)


@app.post('/api/logos')
def save_logo():
    with LOCK:
        doc = require_doc()
        data = request.get_json()
        source = doc.assets.get(data.get('asset'))
        if source is None:
            raise ValueError('Select artwork to save to your library.')
        image = source['image'].convert('RGBA')
        overlay = data.get('overlay') or ({'mode': 'solid', 'color': data['color'], 'strength': 1} if data.get('color') else None)
        validate_overlay(overlay)
        image = apply_overlay(image, overlay)
        key = uuid.uuid4().hex
        item = {'id':key, 'name':str(data.get('name') or source['name'])[:200]}
        root = library_root()
        image.save(root/(key+'.png'))
        (root/(key+'.json')).write_text(json.dumps(item), encoding='utf-8')
        return jsonify(item)


@app.get('/api/logos/<key>/image')
def logo_image(key):
    return send_file(library_item(key), mimetype='image/png')


@app.delete('/api/logos/<key>')
def delete_logo(key):
    with LOCK:
        path = library_item(key)
        # Imported artwork is copied into each project, not linked to this file.
        path.with_suffix('.json').unlink(missing_ok=True)
        path.unlink()
        return jsonify(deleted=key)


@app.get('/api/viewer/map/<kind>')
def viewer_map(kind):
    if kind not in ('normal', 'spec'):
        abort(404)
    with LOCK:
        doc = require_doc()
        key = json.dumps([kind, doc.state['normal_layers'], doc.state['spec'], doc.state['visibility']], sort_keys=True)
        cache = getattr(doc, 'viewer_map_cache', {})
        if key not in cache:
            if kind == 'normal' and not doc.state['normal_layers']:
                image = Image.new('RGB', (1, 1), (128, 128, 255))
            else:
                # Preview RGB independently of the export's deliberately black alpha.
                image = doc.isolated(kind).convert('RGB')
            if len(cache) >= 2:
                cache.clear()
            cache[key] = png(image, 4096)
            doc.viewer_map_cache = cache
        return send_file(io.BytesIO(cache[key]), mimetype='image/png')


@app.post('/api/logos/<key>/add')
def logo_add(key):
    with LOCK:
        path = library_item(key)
        meta = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        return jsonify(add_asset(path.read_bytes(), meta['name']))


@app.post('/api/viewer/diffuse')
def viewer_diffuse():
    with LOCK:
        doc = require_doc()
        doc.update(request.get_json())
        return send_file(io.BytesIO(png(doc.fast_composite(True, ZOOM_PREVIEW_SIZE))), mimetype='image/png')


@app.post('/api/render')
def render():
    with LOCK:
        doc = require_doc()
        doc.update(request.get_json())
        doc.previews['proof'] = png(doc.composite_default(), 1400)
        doc.previews.pop('proof_full', None)
        return jsonify(ok=True)


@app.post('/api/render/live')
def render_live():
    # Return this request's image directly, so another render cannot replace
    # a shared proof between the render request and the image download.
    with LOCK:
        doc = require_doc()
        doc.update(request.get_json())
        result = png(doc.fast_composite(True, PREVIEW_SIZE))
        return send_file(io.BytesIO(result), mimetype='image/png')


def download(data, filename, mime='application/octet-stream'):
    if NATIVE_WINDOW is not None and (request.headers.get('X-Dirt-Desktop') or request.headers.get('X-Moto-Desktop')) == '1':
        import webview
        extension = Path(filename).suffix
        chosen = NATIVE_WINDOW.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename,
                                                  file_types=(f'Dirt Gear output (*{extension})',))
        if not chosen:
            return jsonify(cancelled=True)
        destination = Path(chosen if isinstance(chosen,str) else chosen[0])
        if destination.suffix.lower() != extension.lower():
            destination = destination.with_name(destination.name+extension)
        if extension.lower() == '.pnt':
            # PaintEd writes the chosen paint name into the PNT header as well
            # as the filename. Keep both names aligned when Save As renames it.
            data = data[:4] + field(destination.stem) + data[104:]
        destination.write_bytes(data)
        return jsonify(saved=str(destination), filename=destination.name)
    return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=filename)


def safe_name(name):
    return ''.join(c for c in name if c not in '<>:"/\\|?*' and ord(c)>=32).strip('. ')[:99] or 'Dirt Gear'


PROJECT_EXT = '.dirtgear'
APP_DATA_NAME = 'Dirt Gear'
LEGACY_DATA_NAME = 'Moto Gear'
_MIGRATED = False


def local_app_data():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData/Local')))


def migrate_moto_gear_library():
    """Copy (never move) a Moto Gear library into Dirt Gear on first run.

    Saved projects, logos and layouts carry across. The Moto Gear folder is
    left untouched so the old app keeps working side by side."""
    global _MIGRATED
    if _MIGRATED:
        return
    _MIGRATED = True
    new_root = local_app_data()/APP_DATA_NAME
    old_root = local_app_data()/LEGACY_DATA_NAME
    if new_root.exists() or not old_root.is_dir():
        return
    try:
        for part in ('Projects', 'Logos', 'Layouts'):
            source = old_root/part
            if source.is_dir():
                shutil.copytree(source, new_root/part, dirs_exist_ok=True)
        new_root.mkdir(parents=True, exist_ok=True)
        (new_root/'imported-from-moto-gear.txt').write_text(
            'Projects, logos and layouts were copied from Moto Gear on first launch.\n'
            'The original Moto Gear folder was not changed.\n', encoding='utf-8')
    except OSError:
        logging.exception('Could not copy the Moto Gear library')


def project_library():
    migrate_moto_gear_library()
    return local_app_data()/APP_DATA_NAME/'Projects'


def project_bytes(doc):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(doc.path, 'template.psd')
        z.writestr('project.json', json.dumps({'version':1,'filename':doc.name,'state':doc.state,
            'assets':{k:v['name'] for k,v in doc.assets.items()}}))
        for key,val in doc.assets.items():
            z.writestr('artwork/'+key+'.png', png(val['image']))
    return out.getvalue()


def load_project(stream, saved_path=None):
    with zipfile.ZipFile(stream) as z:
        if sum(i.file_size for i in z.infolist()) > 2*1024**3:
            raise ValueError('Project is too large.')
        config = json.loads(z.read('project.json'))
        if config.get('version') != 1:
            raise ValueError('Unsupported project version')
        path = WORK/(uuid.uuid4().hex+'.psd')
        path.write_bytes(z.read('template.psd'))
        doc = Document(path, config['filename'])
        for key,name in config['assets'].items():
            image = Image.open(io.BytesIO(z.read('artwork/'+key+'.png'))).convert('RGBA')
            doc.assets[key] = {'name': name, 'image': image}
        doc.update(config['state'])
        doc.quick_save_path = saved_path
        return doc


def rider_paint_folders():
    """Find the rider paint folders in MX Bikes' configured mods directory."""
    documents = [Path.home()/'Documents',
                 Path(os.environ.get('OneDrive', str(Path.home()/'OneDrive')))/'Documents']
    for directory in documents:
        settings = directory/'PiBoSo/MX Bikes/global.ini'
        if not settings.is_file():
            continue
        config = configparser.ConfigParser(interpolation=None)
        config.read(settings, encoding='utf-8-sig')
        mods = config.get('mods', 'folder', fallback='').strip()
        if not mods:
            mods = str(settings.parent/'mods')
        riders = Path(mods)/'rider/riders'
        if riders.is_dir():
            return {model.name: model/'paints' for model in riders.iterdir()
                    if model.is_dir() and (model/'paints').is_dir()}
    return {}


@app.get('/api/game/paint-folders')
def game_paint_folders():
    return jsonify(models=sorted(rider_paint_folders(), key=str.casefold))


@app.post('/api/game/install-pnt')
def install_game_pnt():
    with LOCK:
        doc = require_doc()
        request_data = request.get_json()
        model = request_data.get('model', '')
        folders = rider_paint_folders()
        if model not in folders:
            raise ValueError('Choose an available MX Bikes rider model.')
        doc.update(request_data['state'])
        textures = doc.textures()
        packed = pack_pnt(doc.state['name'], textures)
        if set(read_pnt(packed)) != set(textures):
            raise ValueError('PNT verification failed')
        destination = folders[model]/(safe_name(doc.state['name'])+'.pnt')
        if destination.exists() and not request_data.get('replace'):
            return jsonify(exists=True, filename=destination.name)
        temporary = destination.with_name(destination.name+'.dirt-gear-tmp')
        try:
            temporary.write_bytes(packed)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return jsonify(saved=str(destination), filename=destination.name, model=model)


@app.post('/api/export/<kind>')
def export(kind):
    with LOCK:
        doc = require_doc()
        doc.update(request.get_json())
        textures = doc.textures()
        name = safe_name(doc.state['name'])
        if kind == 'pnt':
            packed = pack_pnt(doc.state['name'], textures)
            checked = read_pnt(packed)
            if set(checked) != set(textures):
                raise ValueError('PNT verification failed')
            return download(packed, name+'.pnt')
        if kind == 'tga':
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
                for stem,data in textures.items():
                    z.writestr(stem+'.tga', data)
            return download(out.getvalue(), name+' - TGAs.zip', 'application/zip')
        raise ValueError('Unknown export type')


@app.post('/api/project/save')
def save_project():
    with LOCK:
        doc = require_doc()
        doc.update(request.get_json())
        return download(project_bytes(doc), safe_name(doc.state['name'])+PROJECT_EXT)


@app.post('/api/project/quick-save')
def quick_save_project():
    with LOCK:
        doc = require_doc()
        doc.update(request.get_json())
        library = project_library()
        library.mkdir(parents=True, exist_ok=True)
        destination = getattr(doc, 'quick_save_path', None)
        if destination is None:
            destination = library/(safe_name(doc.state['name'])[:70]+'-'+uuid.uuid4().hex[:8]+PROJECT_EXT)
            doc.quick_save_path = destination
        temporary = destination.with_name(destination.name+'.tmp')
        try:
            temporary.write_bytes(project_bytes(doc))
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return jsonify(saved=str(destination), name=doc.state['name'])


@app.get('/api/project/recent')
def recent_projects():
    library = project_library()
    if not library.is_dir():
        return jsonify(projects=[])
    projects = []
    for path in sorted([*library.glob('*'+PROJECT_EXT), *library.glob('*.motogear')], key=lambda p:p.stat().st_mtime, reverse=True)[:10]:
        try:
            with zipfile.ZipFile(path) as z:
                state = json.loads(z.read('project.json'))['state']
            projects.append({'id':path.name,'name':state['name']})
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            continue
    return jsonify(projects=projects)


@app.post('/api/project/reopen')
def reopen_project():
    global DOC
    with LOCK:
        selected = request.get_json().get('id', '')
        if Path(selected).name != selected or not selected.lower().endswith((PROJECT_EXT, '.motogear')):
            raise ValueError('Choose a saved Dirt Gear project.')
        path = project_library()/selected
        if not path.is_file():
            raise ValueError('That saved project is no longer available.')
        doc = load_project(path, saved_path=path)
        DOC = doc
        return jsonify(doc.info())


@app.post('/api/project/open')
def open_project():
    global DOC
    with LOCK:
        upload = request.files['file']
        doc = load_project(upload.stream)
        DOC = doc
        return jsonify(doc.info())


def main():
    global PORT, TOKEN, DOC, NATIVE_WINDOW
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--open')
    parser.add_argument('--session-file')
    parser.add_argument('--state-file')
    args = parser.parse_args()
    shutil.rmtree(updates_folder(), ignore_errors=True)
    if args.open:
        DOC = Document(args.open, Path(args.open).name)
        if args.state_file:
            DOC.update(json.loads(Path(args.state_file).read_text(encoding='utf-8-sig')))
    from werkzeug.serving import make_server
    server = make_server('127.0.0.1', args.port, app, threaded=True)
    PORT = server.server_port
    url = f'http://127.0.0.1:{PORT}/?token={TOKEN}'
    if args.session_file:
        Path(args.session_file).write_text(json.dumps({'url':url,'token':TOKEN,'port':PORT}))
    if args.no_browser:
        print('Dirt Gear is running at', url, flush=True)
        server.serve_forever()
        return
    import webview
    NATIVE_WINDOW = webview.create_window('Dirt Gear', url, width=1500, height=960,
                                         min_size=(1100,760), background_color='#0E0F11')
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        webview.start(gui='edgechromium', icon=str(ROOT/'icon.ico'))
    finally:
        server.shutdown()
        TEMP.cleanup()
    # Edge WebView2 can leave helper threads alive after its window has closed.
    # At this point the local server and temporary files are already released.
    if getattr(sys, '_MEIPASS', None):
        os._exit(0)


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    try:
        main()
    except Exception as exc:
        logging.exception('Dirt Gear could not start')
        if getattr(sys, 'frozen', False):
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'Dirt Gear could not start.\n\n'+str(exc)+'\n\nMicrosoft Edge WebView2 Runtime is required.', 'Dirt Gear', 16)
        else:
            raise
