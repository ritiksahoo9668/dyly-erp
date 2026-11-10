import logging

from rest_framework.views import exception_handler

logger = logging.getLogger("erp.api")


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
        return None

    response.data = {
        "error": {
            "status_code": response.status_code,
            "detail": response.data,
        }
    }
    return response
