from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache

def health_check(request):
    """Synchronous health‑check endpoint.
    Returns JSON indicating database and cache connectivity.
    """
    # DB check – ensure a connection can be obtained
    try:
        conn = connections['default']
        conn.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    # Cache check – simple set/get if a cache backend is configured
    try:
        cache.set('health_check', 'ok', timeout=5)
        cache_ok = cache.get('health_check') == 'ok'
    except Exception:
        cache_ok = False

    status = {'database': db_ok, 'cache': cache_ok}
    http_status = 200 if db_ok else 500
    return JsonResponse(status, status=http_status)
