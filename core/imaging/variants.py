"""WebP-варіанти локальних зображень (Pillow).

Поруч із `products/foo.png` з'являються:
  products/foo.png.w480.webp
  products/foo.png.w800.webp
  products/foo.png.w1280.webp
  products/foo.png.imgmeta.json

Оригінал на диску не змінюється. Сторона довша за MAX_ORIGINAL_SIDE
лише обмежує нові файли, якщо викликати cap_original() окремо.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

WIDTHS = (480, 800, 1280)
WEBP_QUALITY = 80
MAX_ORIGINAL_SIDE = 2000
META_SUFFIX = '.imgmeta.json'
_GENERATED_RE = re.compile(r'\.w\d+\.webp$')


def meta_path(source: Path) -> Path:
    return source.with_name(source.name + META_SUFFIX)


def variant_path(source: Path, width: int) -> Path:
    return source.with_name(f'{source.name}.w{width}.webp')


def is_generated_name(name: str) -> bool:
    return name.endswith(META_SUFFIX) or bool(_GENERATED_RE.search(name))


def target_widths(src_width: int) -> list[int]:
    widths = [width for width in WIDTHS if width < src_width]
    if src_width > 0 and src_width not in widths and src_width <= max(WIDTHS):
        widths.append(src_width)
    return sorted(set(widths))


def _open(path: Path) -> Image.Image:
    with Image.open(path) as raw:
        oriented = ImageOps.exif_transpose(raw)
        image = oriented if oriented is not None else raw
        image.load()
        return image.copy()


def _flatten_mode(image: Image.Image) -> Image.Image:
    if image.mode == 'P':
        return image.convert('RGBA' if 'transparency' in image.info else 'RGB')
    if image.mode == 'LA':
        return image.convert('RGBA')
    if image.mode not in ('RGB', 'RGBA'):
        return image.convert('RGB')
    return image


def _fit_max_side(image: Image.Image, max_side: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _save_webp(image: Image.Image, path: Path) -> None:
    image.save(path, 'WEBP', quality=WEBP_QUALITY, method=4)


def _save_original(image: Image.Image, path: Path) -> None:
    ext = path.suffix.lower()
    if ext in ('.jpg', '.jpeg'):
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel('A'))
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(path, 'JPEG', quality=85, optimize=True)
        return
    if ext == '.webp':
        _save_webp(image, path)
        return
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGBA')
    image.save(path, 'PNG', optimize=True)


def cap_original(path: Path) -> bool:
    """Зменшує оригінал, якщо довша сторона більша за ліміт. Повертає True, якщо файл перезаписано."""
    image = _flatten_mode(_open(path))
    if max(image.size) <= MAX_ORIGINAL_SIDE:
        return False
    _save_original(_fit_max_side(image, MAX_ORIGINAL_SIDE), path)
    return True


def _variants_exist(source: Path, meta: dict) -> bool:
    for item in meta.get('variants') or []:
        width = item.get('width')
        if not width or not variant_path(source, int(width)).is_file():
            return False
    return True


def read_meta(path: Path) -> dict | None:
    meta_file = meta_path(path)
    if not meta_file.is_file():
        return None
    try:
        data = json.loads(meta_file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def build_variants(path: Path) -> dict | None:
    if not path.is_file() or is_generated_name(path.name):
        return None
    existing = read_meta(path)
    try:
        fresh = (
            existing
            and meta_path(path).stat().st_mtime >= path.stat().st_mtime
            and _variants_exist(path, existing)
        )
    except OSError:
        fresh = False
    if fresh:
        return existing

    image = _flatten_mode(_open(path))
    src_width, src_height = image.size
    variants = []
    for width in target_widths(src_width):
        if width == src_width:
            resized = image
            height = src_height
        else:
            height = max(1, round(src_height * (width / src_width)))
            resized = image.resize((width, height), Image.Resampling.LANCZOS)
        destination = variant_path(path, width)
        _save_webp(resized, destination)
        variants.append({
            'width': width,
            'height': resized.size[1],
            'file': destination.name,
        })
    meta = {'width': src_width, 'height': src_height, 'variants': variants}
    meta_file = meta_path(path)
    temporary = meta_file.with_name(meta_file.name + '.tmp')
    temporary.write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    temporary.replace(meta_file)
    return meta


def process_stored_file(path: Path) -> dict | None:
    """Пише лише сусідні WebP і json. Вихідний файл не чіпає."""
    if path is None or not path.is_file() or is_generated_name(path.name):
        return None
    try:
        return build_variants(path)
    except Exception:
        logger.exception('Не вдалося побудувати варіанти для %s', path)
        return None


def field_local_path(field) -> Path | None:
    if not field:
        return None
    try:
        return Path(field.path)
    except Exception:
        return None
