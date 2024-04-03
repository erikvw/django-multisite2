from django.conf import settings


class MultisiteError(Exception):
    pass


class MultisiteSiteDoesNotExist(Exception):
    pass


class MultisiteAliasDoesNotExist(Exception):
    pass


class MultisiteCacheError(Exception):
    pass


class MultisiteFallbackError(Exception):
    pass


class MultisiteDisallowedHost(Exception):
    pass


class MultisiteInvalidHostError(Exception):
    pass


class MultisiteServerError(Exception):
    pass


class MultisiteCookieDomainDepthError(Exception):
    pass


def debug_raise_disallowed_host_exception(e):
    if getattr(settings, "MULTISITE_DEBUG", None):
        raise MultisiteDisallowedHost(
            f"DisallowedHost. To silence this exception, set MULTISITE_DEBUG=False. Got {e}."
        )


def debug_raise_cache_missed_exception(netloc, alias):
    if getattr(settings, "MULTISITE_DEBUG", None):
        raise MultisiteCacheError(
            f"Cache missed. Got location {netloc} and Alias {alias}. "
            "To silence this exception, set MULTISITE_DEBUG=False."
        )


def debug_check_status_code(response, **kwargs) -> None:
    if response.status_code == 500 and getattr(settings, "MULTISITE_DEBUG", None):
        raise MultisiteServerError(
            f"HttpResponse 500. {kwargs}. Got {response}."
            "To silence this exception, set MULTISITE_DEBUG=False."
        )
    return None
