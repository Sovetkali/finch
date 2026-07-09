import time

import logging


logger = logging.getLogger("finch.request")


class RequestLoggingMiddleware:
    """Log basic request timing information in a machine-friendly format."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f user=%s",
            request.method,
            request.path,
            getattr(response, "status_code", 500),
            duration_ms,
            getattr(request.user, "id", None),
        )
        return response
