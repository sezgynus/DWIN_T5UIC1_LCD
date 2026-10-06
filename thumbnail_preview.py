"""Bounded thumbnail conversion into merged RGB565 rectangles."""
from io import BytesIO
import posixpath
import time
import logging
from urllib.parse import quote
from PIL import Image


def image_runs(data):
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > 4_000_000:
            raise ValueError('Thumbnail too large')
        source.thumbnail((80, 80), Image.Resampling.LANCZOS)
        rgba = source.convert('RGBA')
        canvas = Image.new('RGB', (80, 80), 'black')
        canvas.paste(rgba, ((80-rgba.width)//2, (80-rgba.height)//2), rgba)
    image = canvas.quantize(colors=8, dither=Image.Dither.NONE).convert('RGB')
    runs = []
    for y in range(80):
        start, previous = 0, None
        for x in range(81):
            if x < 80:
                r, g, b = image.getpixel((x, y))
                color = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            else:
                color = None
            if color != previous:
                if previous is not None and previous != 0:
                    runs.append((previous, start, y, x-1, y))
                start, previous = x, color
    return merge_runs(runs)


def merge_runs(runs):
    """Merge identical spans on adjacent rows without altering pixels."""
    rectangles = []
    active = {}
    last_row = -1
    for color, x0, y, x1, _ in runs:
        if y != last_row:
            active = {key: index for key, index in active.items()
                      if rectangles[index][4] == y-1}
            last_row = y
        key = (color, x0, x1)
        index = active.get(key)
        if index is not None and rectangles[index][4] == y-1:
            rectangles[index][4] = y
        else:
            active[key] = len(rectangles)
            rectangles.append([color, x0, y, x1, y])
    return tuple(tuple(rect) for rect in rectangles)


def load_thumbnail(client, filename):
    started = time.monotonic()
    metadata = client.get('/server/files/metadata?filename=' + quote(filename, safe=''))['result']
    thumbs = metadata.get('thumbnails', [])
    candidates = [t for t in thumbs if isinstance(t, dict) and isinstance(t.get('relative_path'), str)
                  and all(isinstance(t.get(k), int) and 0 < t[k] <= 4080 for k in ('width', 'height'))]
    # Prefer a source large enough for the preview, rather than a tiny icon.
    candidates.sort(key=lambda t: (max(t['width'], t['height']) < 80,
                                   abs(max(t['width'], t['height'])-80)))
    for thumb in candidates:
        relative = thumb['relative_path']
        path = posixpath.normpath(posixpath.join(posixpath.dirname(filename), relative))
        if relative.startswith('/') or path.startswith('../') or path == '..':
            continue
        data = client.get_bytes('/server/files/gcodes/' + quote(path, safe='/'), max_bytes=2_000_000)
        downloaded = time.monotonic()
        runs = image_runs(data)
        logging.info('Thumbnail %s: download %.3fs, conversion %.3fs, %d rectangles',
                     filename, downloaded-started, time.monotonic()-downloaded, len(runs))
        return runs
    raise ValueError('No thumbnail')
