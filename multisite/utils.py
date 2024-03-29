from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Callable

from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import (
    ImproperlyConfigured,
    MultipleObjectsReturned,
    ObjectDoesNotExist,
)
from django.http import Http404
from django.urls import get_callable

if TYPE_CHECKING:
    from django.apps import AppConfig
    from django.contrib.sites.models import Site
    from django.db.models import QuerySet

    from multisite.models import Alias


def get_cache_multisite_alias() -> str:
    return getattr(settings, "CACHE_MULTISITE_ALIAS", "default")


def get_cache_multisite_prefix() -> str | None:
    return getattr(settings, "CACHE_MULTISITE_KEY_PREFIX", None)


def get_fallback_view_or_404() -> Callable | Http404:
    fallback = getattr(settings, "MULTISITE_FALLBACK", None)
    if fallback is None:
        raise Http404
    if callable(fallback):
        view = fallback
    else:
        try:
            view = get_callable(fallback)
        except ImportError:
            # newer django forces this to be an error, which is tidier.
            # we rewrite the error to be a bit more helpful to our users.
            raise ImproperlyConfigured(
                "settings.MULTISITE_FALLBACK is not callable: %s" % fallback
            )
    return view


def get_fallback_kwargs() -> dict | None:
    return getattr(settings, "MULTISITE_FALLBACK_KWARGS", {})


def sync_canonical_from_site_domain(apps=None, **options):
    """
    Synchronize canonical Alias objects based on Site.domain.

    You can pass Q-objects or filter arguments to update a subset of
    Alias objects::

        Alias.canonical.sync_many(site__domain='example.com')

    Renamed canonical manager method ``sync_many``.

    """
    apps = apps or django_apps
    model_cls = apps.get_model("multisite.alias")
    options.update(is_canonical=1)
    aliases = model_cls.objects.filter(**options)
    for alias in aliases.select_related("site"):
        domain = alias.site.domain
        if domain and alias.domain != domain:
            alias.domain = domain
            alias.save()


def create_or_sync_missing_canonical_from_site_domain(apps: AppConfig | None = None) -> None:
    """Create missing canonical Alias objects based on Site.domain.

    Renamed canonical manager method ``sync_missing``.
    """
    apps = apps or django_apps
    model_cls = apps.get_model("multisite.alias")
    aliases = model_cls.objects.filter(is_canonical=1)
    try:
        sites = model_cls._meta.get_field("site").remote_field.model
    except AttributeError:
        sites = model_cls._meta.get_field("site").related_model
    for site in sites.objects.exclude(aliases__in=aliases):
        create_or_sync_alias_from_site(site=site, apps=apps)


def create_or_sync_canonical_from_all_sites(
    apps: AppConfig | None = None, verbose: bool | None = None
) -> None:
    """Create or sync canonical Alias objects from all Site objects.

    Renamed canonical manager method ``sync_all``.
    """
    if verbose:
        sys.stdout.write("  * Syncing canonical from site domain ...     \n")
    sync_canonical_from_site_domain(apps=apps)
    if verbose:
        sys.stdout.write("  * Syncing missing canonical from site domain ...     \n")
    create_or_sync_missing_canonical_from_site_domain(apps=apps)


def create_or_sync_alias_from_site(
    site: Site = None, force_insert: bool | None = None, apps: AppConfig | None = None
) -> Alias | None:
    """Create or synchronize Alias object from ``site``.

    If `force_insert`, forces creation of Alias object.

    Renamed model class method ``sync``.
    """
    alias = None
    apps = apps or django_apps
    force_insert = False if force_insert is None else force_insert
    model_cls = apps.get_model("multisite.alias")
    if domain := site.domain:
        if force_insert:
            alias = model_cls.objects.create(site=site, is_canonical=1, domain=domain)
        else:
            alias, created = model_cls.objects.get_or_create(
                site=site, is_canonical=1, defaults={"domain": domain}
            )
            if not created and alias.domain != domain:
                alias.site = site
                alias.domain = domain
                alias.save()
    else:
        sync_blank_domain(site=site)
    return alias


def sync_blank_domain(site: Site = None, apps: AppConfig | None = None) -> None:
    """Delete associated Alias object for ``site``, if domain
    is blank.
    :rtype: object
    """
    apps = apps or django_apps
    model_cls = apps.get_model("multisite.alias")

    if site.domain:
        raise ValueError("%r has a domain" % site)
    # Remove canonical Alias, if no non-canonical aliases exist.
    try:
        alias = model_cls.objects.get(site=site)
    except ObjectDoesNotExist:
        # Nothing to delete
        pass
    else:
        if not alias.is_canonical:
            raise MultipleObjectsReturned(
                "Other %s still exist for %r"
                % (model_cls._meta.verbose_name_plural.capitalize(), site)
            )
        alias.delete()


def get_user_sites(request) -> QuerySet[Site]:
    if request.user.is_superuser:
        sites = Site.objects.all()
    else:
        try:
            user_profile = request.user.userprofile.sites.all()
        except AttributeError:
            sites = Site.objects.all().order_by("domain")
        else:
            sites = user_profile.sites.order_by("domain")
    return sites
