from django.core.cache import cache


def is_rate_limited(key: str, *, limit: int, window_seconds: int) -> bool:
    """Return True when the caller has exceeded the allowed attempts."""
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, timeout=window_seconds)
    return False
