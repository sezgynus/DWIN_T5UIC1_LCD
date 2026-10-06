"""Bounded thumbnail conversion for volatile LCD picture memory."""
from io import BytesIO
import posixpath
import time
import logging
from urllib.parse import quote
from PIL import Image
from preview_metadata import PreviewData, details_from_metadata


def image_jpeg(data):
    """Produce a baseline 128x128 JPEG with a black letterbox background."""
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > 4_000_000:
            raise ValueError('Thumbnail too large')
        source.thumbnail((128, 128), Image.Resampling.LANCZOS)
        rgba = source.convert('RGBA')
        canvas = Image.new('RGB', (128, 128), 'black')
        canvas.paste(rgba, ((128-rgba.width)//2, (128-rgba.height)//2), rgba)
    output = BytesIO()
    canvas.save(output, format='JPEG', quality=70, subsampling=2,
                progressive=False, optimize=False)
    jpeg = output.getvalue()
    if len(jpeg) > 32768:
        raise ValueError('JPEG exceeds LCD SRAM')
    return jpeg


def load_thumbnail(client, filename, metadata=None):
    started = time.monotonic()
    if metadata is None:
        metadata = client.get('/server/files/metadata?filename=' + quote(filename, safe=''))['result']
    thumbs = metadata.get('thumbnails', [])
    candidates = [t for t in thumbs if isinstance(t, dict) and isinstance(t.get('relative_path'), str)
                  and all(isinstance(t.get(k), int) and 0 < t[k] <= 4080 for k in ('width', 'height'))]
    # Prefer a source large enough for the preview, rather than a tiny icon.
    candidates.sort(key=lambda t: (max(t['width'], t['height']) < 128,
                                   abs(max(t['width'], t['height'])-128)))
    for thumb in candidates:
        relative = thumb['relative_path']
        path = posixpath.normpath(posixpath.join(posixpath.dirname(filename), relative))
        if relative.startswith('/') or path.startswith('../') or path == '..':
            continue
        data = client.get_bytes('/server/files/gcodes/' + quote(path, safe='/'), max_bytes=2_000_000)
        downloaded = time.monotonic()
        jpeg = image_jpeg(data)
        logging.info('Thumbnail %s: download %.3fs, conversion %.3fs, %d JPEG bytes',
                     filename, downloaded-started, time.monotonic()-downloaded, len(jpeg))
        return jpeg
    raise ValueError('No thumbnail')


def load_preview(client, filename):
    metadata = client.get('/server/files/metadata?filename=' + quote(filename, safe=''))['result']
    details = details_from_metadata(metadata)
    try:
        jpeg = load_thumbnail(client, filename, metadata=metadata)
    except Exception as error:
        logging.info('Thumbnail unavailable %s: %s', filename, error)
        jpeg = None
    return PreviewData(jpeg, details)
