import logging

from django.core.cache import cache

from core.client_ip import get_client_ip

logger = logging.getLogger('security.abuse')


def log_abuse(request, reason, extra=''):
    ip = '-'
    path = '-'
    session_prefix = '-'
    if request is not None:
        ip = get_client_ip(request)
        path = getattr(request, 'path', '-') or '-'
        session = getattr(request, 'session', None)
        raw_key = getattr(session, 'session_key', None) or ''
        session_prefix = raw_key[:8] or '-'
    logger.warning(
        'abuse reason=%s path=%s ip=%s session=%s %s',
        reason,
        path,
        ip,
        session_prefix,
        extra,
    )


def _hit_limit(cache_key, limit, period):
    try:
        added = cache.add(cache_key, 1, period)
        if added:
            count = 1
        else:
            count = cache.incr(cache_key)
    except Exception:
        logger.exception('rate-limit cache failed key=%s', cache_key)
        return False
    return count > limit


def is_rate_limited(
    request,
    action,
    *,
    ip_limit=None,
    ip_period=60,
    session_limit=None,
    session_period=60,
):
    blocked = False
    ip = get_client_ip(request)

    if ip_limit:
        if _hit_limit(f'rl:{action}:ip:{ip}', ip_limit, ip_period):
            blocked = True

    session_key = ''
    session = getattr(request, 'session', None)
    if session is not None:
        session_key = session.session_key or ''

    if session_limit and session_key:
        if _hit_limit(f'rl:{action}:sess:{session_key}', session_limit, session_period):
            blocked = True

    if blocked:
        log_abuse(request, 'rate', extra=f'action={action}')
    return blocked
