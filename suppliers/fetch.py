"""Завантаження фіду постачальника. Лише http(s), з таймаутом."""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import requests

from suppliers.constants import FETCH_TIMEOUT, USER_AGENT
from suppliers.exceptions import FeedFetchError

_URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)


def fetch_feed(url: str) -> requests.Response:
    parsed = urlsplit(url or '')
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise FeedFetchError('URL фіду має бути http або https.')
    try:
        response = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': 'application/xml, text/xml, */*',
            },
            stream=True,
        )
        response.raise_for_status()
    except FeedFetchError:
        raise
    except requests.RequestException as exc:
        raise FeedFetchError(_safe_message(exc)) from exc
    return response


@contextmanager
def open_feed(supplier, source=None):
    if source is not None:
        if hasattr(source, 'read'):
            yield source
            return
        path = Path(source)
        if not path.is_file():
            raise FeedFetchError(f'Файл фіду не знайдено: {path}')
        with path.open('rb') as handle:
            yield handle
        return

    response = fetch_feed(supplier.feed_url)
    try:
        response.raw.decode_content = True
        yield response.raw
    finally:
        response.close()


def _safe_message(exc: Exception) -> str:
    text = _URL_RE.sub('[url]', str(exc))
    text = ' '.join(text.split())
    if len(text) > 300:
        text = text[:300] + '…'
    return f'Не вдалося завантажити фід: {text}'
