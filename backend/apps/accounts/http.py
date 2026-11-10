import ipaddress


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def audit_ip(request) -> str | None:
    """Client IP suitable for audit storage, or None when it is not a valid address."""
    value = client_ip(request)
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None
