from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error

from .constants import DYNAMIC_SITE_MIDDLEWARE, DYNAMIC_SITE_TIMEZONE_MIDDLEWARE


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
            Error(
                f"Missing MIDDLEWARE. `{DYNAMIC_SITE_TIMEZONE_MIDDLEWARE}` "
                f"requires `{DYNAMIC_SITE_MIDDLEWARE}`.",
                hint=(
                    f"Add `{DYNAMIC_SITE_MIDDLEWARE}` to settings "
                    f"before `{DYNAMIC_SITE_TIMEZONE_MIDDLEWARE}`."
                ),
                id="multisite.E003",
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
    """Checks that `settings.MULTISITE_TIME_ZONES`, if set, is acted on."""
    errors: list[CheckMessage] = []
    if not getattr(settings, "MULTISITE_TIME_ZONES", None) and (
        DYNAMIC_SITE_TIMEZONE_MIDDLEWARE in (list(getattr(settings, "MIDDLEWARE", None) or []))
    ):
        errors.append(
            Error(
                "settings.MULTISITE_TIME_ZONES is missing or not set. "
                f"MULTISITE_TIME_ZONES is required if {DYNAMIC_SITE_TIMEZONE_MIDDLEWARE} "
                "is active in middleware.",
                hint="Add `MULTISITE_TIME_ZONES` to settings.",
                id="multisite.E002",
            )
        )
    return errors
