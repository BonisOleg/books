"""Розбір посилань YouTube для відео товару."""

import re
from urllib.parse import parse_qs, urlparse

YOUTUBE_URL_ERROR = (
    'Невірне посилання на YouTube. Підтримуються адреси watch, youtu.be, '
    'Shorts, Live та Embed (www, без www, m.youtube.com, youtube-nocookie.com), '
    'зі стартовим часом t або start.'
)

_ALLOWED_HOSTS = frozenset({
    'youtube.com',
    'm.youtube.com',
    'youtu.be',
    'youtube-nocookie.com',
})
_VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
_TIMESTAMP_RE = re.compile(r'^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$')
_PATH_KINDS = frozenset({'embed', 'shorts', 'live', 'v'})


def parse_youtube_timestamp(value):
    """Секунди з 90, 90s, 1m30s, 1h2m3s. None, якщо формат невідомий."""
    raw = (value or '').strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    match = _TIMESTAMP_RE.fullmatch(raw)
    if not match or not any(match.groups()):
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _normalize_host(hostname):
    host = (hostname or '').lower().rstrip('.')
    if host.startswith('www.'):
        host = host[4:]
    return host


def _start_seconds(query):
    for key in ('start', 't'):
        values = query.get(key) or []
        if not values:
            continue
        parsed = parse_youtube_timestamp(values[0])
        if parsed is not None:
            return parsed
    return 0


def parse_youtube_url(url):
    """Повертає (video_id, start_seconds). ValueError — якщо це не YouTube."""
    text = (url or '').strip()
    if not text:
        raise ValueError(YOUTUBE_URL_ERROR)
    if '://' not in text:
        text = 'https://' + text
    parsed = urlparse(text)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(YOUTUBE_URL_ERROR)
    host = _normalize_host(parsed.hostname)
    if host not in _ALLOWED_HOSTS:
        raise ValueError(YOUTUBE_URL_ERROR)

    query = parse_qs(parsed.query, keep_blank_values=False)
    parts = [part for part in (parsed.path or '').split('/') if part]
    video_id = ''
    if host == 'youtu.be':
        video_id = parts[0] if parts else ''
    elif parts and parts[0] in _PATH_KINDS and len(parts) >= 2:
        video_id = parts[1]
    else:
        video_ids = query.get('v') or []
        video_id = video_ids[0] if video_ids else ''

    video_id = (video_id or '').strip()
    if not _VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError(YOUTUBE_URL_ERROR)
    return video_id, _start_seconds(query)


def youtube_embed_url(url):
    """Канонічний embed. Стартовий час — query-параметр start."""
    video_id, start = parse_youtube_url(url)
    embed = f'https://www.youtube.com/embed/{video_id}'
    if start:
        return f'{embed}?start={start}'
    return embed
