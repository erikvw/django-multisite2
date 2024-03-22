from __future__ import annotations

import operator
from functools import reduce
from typing import TYPE_CHECKING

from django.contrib.sites.models import Site
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    ValidationError,
)
from django.core.validators import validate_ipv4_address
from django.db import connections, models, router
from django.db.models import Q, UniqueConstraint
from django.db.models.signals import post_migrate, post_save, pre_save
from django.utils.translation import gettext_lazy as _

from .hacks import use_framework_for_site_cache

if TYPE_CHECKING:
    from django.db.models import QuerySet


_site_domain = Site._meta.get_field("domain")

use_framework_for_site_cache()


class AliasManager(models.Manager):
    """Manager for all Aliases."""

    def get_queryset(self) -> QuerySet[Alias]:
        return super().get_queryset().select_related("site")

    def resolve(self, host: str, port: str | None = None) -> list[str] | None:
        """
        Returns the Alias that best matches ``host`` and ``port``, or None.

        ``host`` is a hostname like ``'example.com'``.
        ``port`` is a port number like 8000, or None.

        Attempts to first match by 'host:port' against
        Alias.domain. If that fails, it will try to match the bare
        'host' with no port number.

        All comparisons are done case-insensitively.
        """
        domains = self._expand_netloc(host=host, port=port)
        q: Q = reduce(operator.or_, (Q(domain__iexact=d) for d in domains))
        aliases = dict((a.domain, a) for a in self.get_queryset().filter(q))
        for domain in domains:
            try:
                return aliases[domain]
            except KeyError:
                pass
        return None

    @classmethod
    def _expand_netloc(cls, host: str, port: str | None = None) -> list[str]:
        """
        Returns a list of possible domain expansions for ``host`` and ``port``.

        ``host`` is a hostname like ``'example.com'``.
        ``port`` is a port number like 8000, or None.

        Expansions are ordered from highest to lowest preference and may
        include wildcards. Examples::

        >>> AliasManager._expand_netloc('www.example.com')
        ['www.example.com', '*.example.com', '*.com', '*']

        >>> AliasManager._expand_netloc('www.example.com', 80)
        ['www.example.com:80', 'www.example.com',
         '*.example.com:80', '*.example.com',
         '*.com:80', '*.com',
         '*:80', '*']
        """
        if not host:
            raise ValueError("Invalid host: %s" % host)

        try:
            validate_ipv4_address(host)
            bits = [host]
        except ValidationError:
            # Not an IP address
            bits = host.split(".")

        result = []
        for i in range(0, (len(bits) + 1)):
            if i == 0:
                host = ".".join(bits[i:])
            else:
                host = ".".join(["*"] + bits[i:])
            if port:
                result.append("%s:%s" % (host, port))
            result.append(host)
        return result


class CanonicalAliasManager(models.Manager):
    """Manager for Alias objects where is_canonical == 1."""

    def get_queryset(self) -> QuerySet[Alias]:
        queryset = super().get_queryset()
        return queryset.filter(is_canonical=1)

    def sync_many(self, *args, **kwargs):
        """
        Synchronize canonical Alias objects based on Site.domain.

        You can pass Q-objects or filter arguments to update a subset of
        Alias objects::

            Alias.canonical.sync_many(site__domain='example.com')
        """
        aliases = self.get_queryset().filter(*args, **kwargs)
        for alias in aliases.select_related("site"):
            domain = alias.site.domain
            if domain and alias.domain != domain:
                alias.domain = domain
                alias.save()

    def sync_missing(self) -> None:
        """Create missing canonical Alias objects based on Site.domain."""
        aliases = self.get_queryset()
        try:
            sites = self.model._meta.get_field("site").remote_field.model
        except AttributeError:
            sites = self.model._meta.get_field("site").related_model
        for site in sites.objects.exclude(aliases__in=aliases):
            Alias.sync(site=site)

    def sync_all(self) -> None:
        """Create or sync canonical Alias objects from all Site objects."""
        self.sync_many()
        self.sync_missing()


class NotCanonicalAliasManager(models.Manager):
    """Manager for Aliases where is_canonical != 1."""

    def get_queryset(self) -> QuerySet[Alias]:
        queryset = super().get_queryset()
        return queryset.exclude(is_canonical=1)


def validate_1_or_none(value: bool) -> None:
    """Raises ValidationError if value is not int(1) or None."""
    if value not in [1, None]:
        raise ValidationError("%r must be 1 or None" % value)


def validate_true_or_none(value: bool) -> None:
    # leave for old migrations
    pass


class Alias(models.Model):
    """
    Model for domain-name aliases for Site objects.

    Domain names must be unique in the format of: 'hostname[:port].'
    Each Site object that has a domain must have an ``is_canonical``
    Alias.
    """

    domain = type(_site_domain)(
        _("domain name"),
        max_length=_site_domain.max_length,
        unique=True,
        help_text=_('Either "domain" or "domain:port"'),
    )
    site = models.ForeignKey(Site, related_name="aliases", on_delete=models.CASCADE)
    is_canonical = models.IntegerField(
        _("is canonical?"),
        default=None,
        null=True,
        editable=False,
        validators=[validate_1_or_none],
        help_text=_("Does this domain name match the one in site?"),
    )
    redirect_to_canonical = models.BooleanField(
        _("redirect to canonical?"),
        default=True,
        help_text=_("Should this domain name redirect to the one in site?"),
    )

    objects = AliasManager()
    canonical = CanonicalAliasManager()
    aliases = NotCanonicalAliasManager()

    class Meta:
        verbose_name = _("Alias")
        verbose_name_plural = _("Aliases")
        # unique_together = [("is_canonical", "site")]
        constraints = [
            UniqueConstraint(
                name="unique_is_canonical_site",
                fields=["is_canonical", "site"],
                # nulls_distinct=False, DJ5
            )
        ]

    def __str__(self):
        return "%s -> %s" % (self.domain, self.site.domain)

    def __repr__(self):
        return "<Alias: %s>" % str(self)

    def save_base(self, *args, **kwargs):
        """For canonical Alias, domains must match Site domains.

        This needs to be validated here so that it is executed *after* the
        Site pre-save signal updates the domain (an AliasInline modelform
        on SiteAdmin will be saved (and it's clean methods run before
        the Site is saved)
        """
        self.full_clean()
        if self.is_canonical and self.domain != self.site.domain:
            raise ValidationError({"domain": ["Does not match %r" % self.site]})
        super().save_base(*args, **kwargs)

    def validate_unique(self, exclude=None) -> None:
        errors = {}
        try:
            super().validate_unique(exclude=exclude)
        except ValidationError as e:
            errors = e.update_error_dict(errors)
        if exclude is not None and "domain" not in exclude:
            errors = self._validate_domain_is_unique(errors)
        if errors:
            raise ValidationError(errors)

    def _validate_domain_is_unique(self, errors: dict) -> dict:
        """Ensure domain is unique, insensitive to case"""
        field_name = "domain"
        field_error = self.unique_error_message(self.__class__, (field_name,))
        if field_name not in errors or str(field_error) not in [
            str(err) for err in errors[field_name]
        ]:
            queryset = self.__class__.objects.filter(
                **{field_name + "__iexact": getattr(self, field_name)}
            )
            if self.pk is not None:
                queryset = queryset.exclude(pk=self.pk)
            if queryset.exists():
                errors.setdefault(field_name, []).append(field_error)
        return errors

    @classmethod
    def _sync_blank_domain(cls, site: Site) -> None:
        """Delete associated Alias object for ``site``, if domain is blank."""
        if site.domain:
            raise ValueError("%r has a domain" % site)
        # Remove canonical Alias, if no non-canonical aliases exist.
        try:
            alias = cls.objects.get(site=site)
        except ObjectDoesNotExist:
            # Nothing to delete
            pass
        else:
            if not alias.is_canonical:
                raise MultipleObjectsReturned(
                    "Other %s still exist for %r"
                    % (cls._meta.verbose_name_plural.capitalize(), site)
                )
            alias.delete()

    @classmethod
    def sync(cls, site: Site, force_insert=False) -> Alias | None:
        """
        Create or synchronize Alias object from ``site``.

        If `force_insert`, forces creation of Alias object.
        """
        alias = None
        if domain := site.domain:
            if force_insert:
                alias = cls.objects.create(site=site, is_canonical=1, domain=domain)
            else:
                alias, created = cls.objects.get_or_create(
                    site=site, is_canonical=1, defaults={"domain": domain}
                )
                if not created and alias.domain != domain:
                    alias.site = site
                    alias.domain = domain
                    alias.save()
        else:
            cls._sync_blank_domain(site)
        return alias

    @classmethod
    def site_domain_changed_hook(cls, sender, instance, raw, *args, **kwargs):
        """Updates canonical Alias object if Site.domain has changed."""
        if not raw and instance.pk is not None:
            try:
                original = sender.objects.get(pk=instance.pk)
            except ObjectDoesNotExist:
                pass
            else:
                # Update Alias.domain to match site
                if original.domain != instance.domain:
                    cls.sync(site=instance)

    @classmethod
    def site_created_hook(cls, sender, instance, raw, created, *args, **kwargs):
        """Creates canonical Alias object for a new Site."""
        if not raw and created:
            # When running create_default_site() because of post_syncdb,
            # don't try to sync before the db_table has been created.
            using = router.db_for_write(cls)
            tables = connections[using].introspection.table_names()
            if cls._meta.db_table not in tables:
                pass
            else:
                # Update Alias.domain to match site
                cls.sync(site=instance)

    @classmethod
    def db_table_created_hook(cls, *args, **kwargs):
        """Syncs canonical Alias objects for all existing Site objects."""
        Alias.canonical.sync_all()


# Hooks to handle Site objects being created or changed
pre_save.connect(Alias.site_domain_changed_hook, sender=Site)
post_save.connect(Alias.site_created_hook, sender=Site)

# Hook to handle syncdb creating the Alias table
post_migrate.connect(Alias.db_table_created_hook)
