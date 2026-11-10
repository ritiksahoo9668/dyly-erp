import logging

from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


logger = logging.getLogger("erp.api")


def _check_database() -> str:
    try:
        connection.ensure_connection()
    except Exception:
        logger.exception("Database health check failed")
        return "unavailable"
    return "ok"


def _check_redis() -> str:
    try:
        cache.set("erp-health", "ok", timeout=5)
        if cache.get("erp-health") != "ok":
            return "unavailable"
    except Exception:
        logger.exception("Redis health check failed")
        return "unavailable"
    return "ok"


@api_view(["GET"])
@permission_classes([AllowAny])
def health(_request):
    checks = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    status = "ok" if all(value == "ok" for value in checks.values()) else "degraded"
    return Response({"status": status, **checks}, status=200 if status == "ok" else 503)
