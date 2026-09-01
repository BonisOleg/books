import ipaddress


def get_client_ip(request):
    """Client IP behind nginx and optional Cloudflare.

    Prefer CF-Connecting-IP when Cloudflare proxies traffic.
    """
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
    if _is_valid_ip(cf_ip):
        return cf_ip

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        for part in forwarded.split(','):
            candidate = part.strip()
            if _is_valid_ip(candidate):
                return candidate

    remote = request.META.get('REMOTE_ADDR', '') or '0.0.0.0'
    return remote if _is_valid_ip(remote) else '0.0.0.0'


def _is_valid_ip(value):
    if not value or len(value) > 45:
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True
