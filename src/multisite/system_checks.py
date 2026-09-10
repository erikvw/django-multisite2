from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning

DYNAMIC_SITE_MIDDLEWARE = "multisite.middleware.DynamicSiteMiddleware"
DYNAMIC_SITE_TIMEZONE_MIDDLEWARE = "multisite.middleware.DynamicSiteTimezoneMiddleware"


def multisite_middleware_check(app_configs, **kwargs) -> list[CheckMessage]:  # noqa: ARG001
    """Checks that `DynamicSiteTimezoneMiddleware`, if used, follows
    `DynamicSiteMiddleware`.

    `DynamicSiteTimezoneMiddleware` reads `settings.SITE_ID`, which is
    not resolved for the request until `DynamicSiteMiddleware` has run.
    Listed first, it silently activates the timezone of the default
    site for every request.
    """
    errors: list[CheckMessage] = []
    middleware = list(getattr(settings, "MIDDLEWARE", None) or [])
    if DYNAMIC_SITE_TIMEZONE_MIDDLEWARE not in middleware:
        return errors
    if DYNAMIC_SITE_MIDDLEWARE not in middleware:
        errors.append(
            Warning(
                f"Missing MIDDLEWARE. `{DYNAMIC_SITE_TIMEZONE_MIDDLEWARE}` has no effect "
                f"without `{DYNAMIC_SITE_MIDDLEWARE}`.",
                hint=(
                    "Without it `settings.SITE_ID` is never resolved for the request, so "
                    "the default site's timezone is activated every time."
                ),
                id="multisite.W001",
            )
        )
    elif middleware.index(DYNAMIC_SITE_TIMEZONE_MIDDLEWARE) < middleware.index(
        DYNAMIC_SITE_MIDDLEWARE
    ):
        errors.append(
            Error(
                f"MIDDLEWARE out of order. `{DYNAMIC_SITE_TIMEZONE_MIDDLEWARE}` must be "
                f"listed after `{DYNAMIC_SITE_MIDDLEWARE}`.",
                hint=(
                    f"`settings.SITE_ID` is not resolved for the request until "
                    f"`{DYNAMIC_SITE_MIDDLEWARE}` has run."
                ),
                id="multisite.E001",
            )
        )
    return errors


def multisite_timezone_setting_check(app_configs, **kwargs) -> list[CheckMessage]:  # noqa: ARG001
    """Checks that `settings.MULTISITE_TIME_ZONES`, if set, is acted on.

    Registered with `deploy=True`, so it runs under `check --deploy`
    and not on every test run.
    """
    errors: list[CheckMessage] = []
    if getattr(settings, "MULTISITE_TIME_ZONES", None) and (
        DYNAMIC_SITE_TIMEZONE_MIDDLEWARE
        not in list(getattr(settings, "MIDDLEWARE", None) or [])
    ):
        errors.append(
            Warning(
                "settings.MULTISITE_TIME_ZONES is set but has no effect.",
                hint=(
                    f"Add `{DYNAMIC_SITE_TIMEZONE_MIDDLEWARE}` to MIDDLEWARE, after "
                    f"`{DYNAMIC_SITE_MIDDLEWARE}`."
                ),
                id="multisite.W002",
            )
        )
    return errors
