from pathlib import Path

from django.conf import settings
from django.http import HttpResponse


def deployment_admin_guard(get_response):
    """Keep editorial writes paused while production is checking a new release."""
    if not settings.DEPLOYMENT_BACKUP:
        return get_response

    backup = Path(settings.DEPLOYMENT_BACKUP)

    def middleware(request):
        if request.path_info.startswith("/admin/") and backup.exists():
            return HttpResponse(
                "Administration is temporarily unavailable during deployment.",
                status=503,
                headers={"Retry-After": "60", "Cache-Control": "no-store"},
            )
        return get_response(request)

    return middleware
