from django.utils import timezone

from ..utils import get_multisite_timezone


class DynamicSiteTimezoneMiddleware:
    """Activates the current site's timezone for the request thread.

    Must be listed AFTER `multisite.middleware.DynamicSiteMiddleware`,
    which resolves `settings.SITE_ID` for this request.

    Outside a request (management commands, signals, workers) nothing
    is activated and Django falls back to `settings.TIME_ZONE`. Use
    `timezone.override(get_multisite_timezone())` there, as you would use
    `settings.SITE_ID.override()`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timezone.activate(get_multisite_timezone())
        try:
            return self.get_response(request)
        finally:
            # threads are reused from the pool, do not leak the timezone
            timezone.deactivate()
