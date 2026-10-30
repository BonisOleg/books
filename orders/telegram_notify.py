"""Сповіщення в Telegram про імпорт конверсій. Без токена — тихо пропускає."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_URL = 'https://api.telegram.org/bot{token}/sendMessage'
TIMEOUT = 8


def send_message(text: str) -> bool:
    token = str(getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '').strip()
    chat_id = str(getattr(settings, 'TELEGRAM_CHAT_ID', '') or '').strip()
    if not token or not chat_id:
        return False
    message = (text or '').strip()
    if not message:
        return False
    try:
        response = requests.post(
            API_URL.format(token=token),
            json={
                'chat_id': chat_id,
                'text': message[:4000],
                'disable_web_page_preview': True,
            },
            timeout=TIMEOUT,
        )
        if response.status_code >= 400:
            logger.warning(
                'Telegram HTTP %s: %s',
                response.status_code,
                (response.text or '')[:200],
            )
            return False
        return True
    except requests.RequestException:
        logger.exception('Telegram: не вдалося надіслати повідомлення')
        return False


def notify_import_failure(summary: dict | None = None, error: str = '') -> bool:
    parts = ['Ofion: збій імпорту KeyCRM → Google Ads.']
    if summary:
        parts.append(
            'fetched={fetched} uploaded={uploaded} skipped={skipped} '
            'failed={failed} invalid={invalid}'.format(
                fetched=summary.get('fetched', 0),
                uploaded=summary.get('uploaded', 0),
                skipped=summary.get('skipped', 0),
                failed=summary.get('failed', 0),
                invalid=summary.get('invalid', 0),
            )
        )
    if error:
        parts.append(str(error)[:500])
    return send_message('\n'.join(parts))


def notify_daily_summary(summary: dict) -> bool:
    if summary.get('not_configured'):
        text = (
            'Ofion: щоденний підсумок конверсій.\n'
            f"не налаштовано: {', '.join(summary.get('missing') or [])}"
        )
    else:
        text = (
            'Ofion: щоденний підсумок конверсій.\n'
            'fetched={fetched} uploaded={uploaded} skipped={skipped} '
            'failed={failed} invalid={invalid}'.format(
                fetched=summary.get('fetched', 0),
                uploaded=summary.get('uploaded', 0),
                skipped=summary.get('skipped', 0),
                failed=summary.get('failed', 0),
                invalid=summary.get('invalid', 0),
            )
        )
    return send_message(text)
