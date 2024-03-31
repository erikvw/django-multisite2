from __future__ import annotations

from hashlib import md5 as md5_constructor
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.contrib.sites.models import SITE_CACHE, Site
from django.core import mail
from django.core.cache import caches
from django.core.exceptions import DisallowedHost
from django.db.models.signals import post_delete, post_init, pre_save
from django.http import HttpResponse, HttpResponsePermanentRedirect

from ..exceptions import (
    MultisiteError,
    MultisiteInvalidHostError,
    debug_check_status_code,
    debug_raise_cache_missed_exception,
    debug_raise_disallowed_host_exception,
)
from ..models import Alias

__all__ = ["DynamicSiteMiddleware"]

from ..utils import (
    get_cache_multisite_alias,
    get_cache_multisite_prefix,
    get_fallback_kwargs,
    get_fallback_view_or_404,
)


class DynamicSiteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        if not hasattr(settings.SITE_ID, "set"):
            raise MultisiteError(
                "Invalid type for settings.SITE_ID: %s" % type(settings.SITE_ID).__name__
            )

        self.cache_alias = get_cache_multisite_alias()
        self.key_prefix = get_cache_multisite_prefix() or settings.CACHES[
            self.cache_alias
        ].get("KEY_PREFIX", "")

        self.cache = caches[self.cache_alias]
        post_init.connect(
            self.site_domain_cache_hook, sender=Site, dispatch_uid="multisite_post_init"
        )
        pre_save.connect(self.site_domain_changed_hook, sender=Site)
        post_delete.connect(self.site_deleted_hook, sender=Site)

    def __call__(self, request):
        # if 500 here -> Site ObjectDoesNotExist was raised by get_current_site()
        # debug_check_status_code(response, request=request)
        try:
            netloc = request.get_host().lower()
        except DisallowedHost as e:
            debug_raise_disallowed_host_exception(e)
            settings.SITE_ID.reset()
            response = self.fallback_view(request)
        else:
            cache_key = self.get_cache_key(netloc)
            if (alias := self.cache.get(cache_key)) is not None:
                # found Alias
                self.cache.set(cache_key, alias)
                settings.SITE_ID.set(alias.site_id)
                response = self.redirect_to_canonical(request, alias)
            elif (alias := self.get_alias(netloc)) is None:
                # Cache missed, fallback using settings.MULTISITE_FALLBACK
                debug_raise_cache_missed_exception(netloc, alias)
                settings.SITE_ID.reset()
                response = self.fallback_view(request)
            else:
                # found Site
                self.cache.set(cache_key, alias)
                settings.SITE_ID.set(alias.site_id)
                SITE_CACHE[settings.SITE_ID] = alias.site  # Pre-populate SITE_CACHE
                response = self.redirect_to_canonical(request, alias)
                # debug_check_status_code(response, netloc=netloc, alias=alias, site=alias.site)
        return response or self.get_response(request)

    @staticmethod
    def redirect_to_canonical(request, alias: Alias) -> HttpResponse | None:
        if not alias.redirect_to_canonical or alias.is_canonical:
            response = None
        else:
            url = urlsplit(request.build_absolute_uri(request.get_full_path()))
            url = urlunsplit(
                (url.scheme, alias.site.domain, url.path, url.query, url.fragment)
            )
            response = HttpResponsePermanentRedirect(url)
        return response

    def get_cache_key(self, netloc):
        """Returns a cache key based on ``netloc``."""
        netloc = md5_constructor(netloc.encode("utf-8"), usedforsecurity=False)
        return "multisite.alias.%s.%s" % (self.key_prefix, netloc.hexdigest())

    @staticmethod
    def netloc_parse(netloc):
        """Returns ``(host, port)`` for ``netloc`` of the form
        ``'host:port'``.

        If netloc does not have a port number, ``port`` will be None.
        """
        if ":" in netloc:
            return netloc.rsplit(":", 1)
        else:
            return netloc, None

    def get_alias(self, netloc) -> Alias | None:
        """Returns Alias matching ``netloc``. Otherwise,
        returns None.
        """
        host, port = self.netloc_parse(netloc)
        try:
            alias = Alias.objects.resolve(host=host, port=port)
        except MultisiteInvalidHostError:
            alias = None
        if alias is None:
            # Running under TestCase or runserver?
            alias = self.get_development_alias(netloc)
        return alias

    @staticmethod
    def fallback_view(request) -> HttpResponse:
        """Runs the fallback view function in
        ``settings.MULTISITE_FALLBACK``.

        If ``MULTISITE_FALLBACK`` is None, raises an Http404 error.

        If ``MULTISITE_FALLBACK`` is callable, will treat that
        callable as a view that returns an HttpResponse.

        If ``MULTISITE_FALLBACK`` is a string, will resolve it to a
        view that returns an HttpResponse.

        In order to use a generic view that takes additional
        parameters, ``settings.MULTISITE_FALLBACK_KWARGS`` may be a
        dictionary of additional keyword arguments.
        """
        view = get_fallback_view_or_404()
        kwargs = get_fallback_kwargs()
        if hasattr(view, "as_view"):
            return view.as_view(**kwargs)(request)
        return view(request, **kwargs)

    @staticmethod
    def get_development_alias(netloc) -> Alias:
        """Returns valid Alias when in development mode. Otherwise,
        returns None.

        Development mode is either:
        - Running tests, i.e. manage.py test
        - Running locally in `settings.DEBUG` = True, where the
          hostname is a top-level name, i.e. localhost
        """
        alias = None
        # When running tests, django.core.mail.outbox exists and
        # netloc == 'testserver'
        is_testserver = hasattr(mail, "outbox") and netloc in (
            "testserver",
            "adminsite.com",
        )
        # When using runserver, assume that host will only have one path
        # component. This covers 'localhost' and your machine name.
        is_local_debug = settings.DEBUG and len(netloc.split(".")) == 1
        if is_testserver or is_local_debug:
            try:
                # Prefer the default SITE_ID
                site_id = settings.SITE_ID.get_default()
            except ValueError:
                # Fallback to the first Site object
                alias = Alias.canonical.order_by("site")[0]
            else:
                alias = Alias.canonical.get(site=site_id)
        return alias

    @classmethod
    def site_domain_cache_hook(cls, sender, instance, *args, **kwargs):
        """Caches `Site.domain` in the object for
        site_domain_changed_hook.
        """
        instance._domain_cache = instance.domain

    def site_domain_changed_hook(self, sender, instance, raw, *args, **kwargs):
        """Clears the cache if `Site.domain` has changed."""
        if raw or instance.pk is None:
            return

        original = getattr(instance, "_domain_cache", None)
        if original != instance.domain:
            self.cache.clear()

    def site_deleted_hook(self, *args, **kwargs):
        """Clears the cache if Site was deleted."""
        self.cache.clear()
