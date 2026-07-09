from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache
from asgiref.sync import sync_to_async

async def health_check(request):
    """Simple health‑check endpoint.
    Returns JSON with DB and cache connectivity status.
    """
    # DB check – run in thread to avoid async DB call
    def _db_check():
        try:
            conn = connections['default']
            conn.ensure_connection()
            return True
        except Exception:
            return False

    db_ok = await sync_to_async(_db_check)()

    # Cache check – also run in thread
    def _cache_check():
        try:
            cache.set('health_check', 'ok', timeout=5)
            return cache.get('health_check') == 'ok'
        except Exception:
            return False

    cache_ok = await sync_to_async(_cache_check)()

    status = {
        'database': db_ok,
        'cache': cache_ok,
    }
    http_status = 200 if db_ok else 500
    return JsonResponse(status, status=http_status)
