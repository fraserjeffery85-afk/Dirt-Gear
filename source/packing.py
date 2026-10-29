"""Dirt Gear's independent PiBoSo PNT writer. No PaintHub/PaintEd dependency."""
import hashlib
import io
import struct
import zlib
from PIL import Image


def tga_bytes(image, alpha=False):
    image = image.convert('RGBA' if alpha else 'RGB')
    if alpha:
        image.putalpha(0)
    stream = io.BytesIO()
    image.save(stream, format='TGA', compression=None)
    data = stream.getvalue()
    if data[16] != (32 if alpha else 24):
        raise ValueError('Incorrect TGA depth')
    return data


def field(text):
    try:
        value = text.encode('cp1252')
    except UnicodeEncodeError as exc:
        raise ValueError('Use Latin characters for the MX Bikes paint name.') from exc
    if not value or len(value) > 99 or b'\0' in value:
        raise ValueError('Paint name must contain 1–99 characters.')
    return value.ljust(100, b'\0')


def pack_pnt(name, textures):
    """Pack mapping {texture_stem: complete TGA bytes} into a PNT container.

    Validated against supplied existing PNT: 100-byte CP1252 fields,
    source-TGA MD5, bottom-up RGBA, eight reserved bytes + raw DEFLATE.
    """
    result = io.BytesIO()
    result.write(b'PNT\0' + field(name) + struct.pack('<I', len(textures)))
    for stem, tga in textures.items():
        image = Image.open(io.BytesIO(tga)).convert('RGBA')
        pixels = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
        compressor = zlib.compressobj(6, zlib.DEFLATED, -15)
        compressed = b'\0' * 8 + compressor.compress(pixels) + compressor.flush()
        result.write(field(stem))
        result.write(struct.pack('<II', *image.size))
        result.write(hashlib.md5(tga).digest())
        result.write(struct.pack('<I', len(compressed)))
        result.write(compressed)
    return result.getvalue()


def read_pnt(data):
    """Strict reader used for export verification; returns decompressed textures."""
    if data[:4] != b'PNT\0' or len(data) < 108:
        raise ValueError('Not a PNT file')
    count = struct.unpack_from('<I', data, 104)[0]
    if not 1 <= count <= 100:
        raise ValueError('Invalid texture count')
    pos, entries = 108, {}
    for _ in range(count):
        stem = data[pos:pos+100].split(b'\0')[0].decode('cp1252')
        width, height = struct.unpack_from('<II', data, pos+100)
        digest = data[pos+108:pos+124]
        size = struct.unpack_from('<I', data, pos+124)[0]
        if not (0 < width <= 16384 and 0 < height <= 16384) or pos+128+size > len(data):
            raise ValueError('Invalid PNT entry')
        blob = data[pos+128:pos+128+size]
        decoder = zlib.decompressobj(-15)
        raw = decoder.decompress(blob[8:], width*height*4+1)
        if len(raw) != width*height*4 or not decoder.eof or decoder.unused_data:
            raise ValueError('Invalid PNT texture data')
        entries[stem] = {'size': (width, height), 'md5': digest, 'rgba': raw}
        pos += 128+size
    if pos != len(data):
        raise ValueError('Unexpected trailing PNT data')
    return entries
