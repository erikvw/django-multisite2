from __future__ import annotations

import operator
from functools import reduce
from typing import TYPE_CHECKING

from django.contrib.sites import managers
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.validators import validate_ipv4_address
from django.db import models
from django.db.models import Q
from django.db.models.constants import LOOKUP_SEP

from ..exceptions import MultisiteInvalidHostError

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from .alias import Alias

__all__ = [
    "AliasManager",
    "CanonicalAliasManager",
    "NotCanonicalAliasManager",
    "SpanningCurrentSiteManager",
]


class AliasManager(models.Manager):
    """Manager for all Aliases."""

    use_in_migrations = True

    def get_queryset(self) -> QuerySet[Alias]:
        return super().get_queryset().select_related("site")

    def resolve(self, host: str, port: str | None = None) -> list[str] | None:
        """Returns the Alias that best matches ``host`` and
        ``port``, or None.

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
        """Returns a list of possible domain expansions for ``host``
        and ``port``.

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
            raise MultisiteInvalidHostError("Invalid host: %s" % host)
        try:
            validate_ipv4_address(host)
        except ValidationError:
            # Not an IP address
            bits = host.split(".")
        else:
            bits = [host]
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

    use_in_migrations = True

    def get_queryset(self) -> QuerySet[Alias]:
        queryset = super().get_queryset()
        return queryset.filter(is_canonical=1)


class NotCanonicalAliasManager(models.Manager):
    """Manager for Aliases where is_canonical != 1."""

    use_in_migrations = True

    def get_queryset(self) -> QuerySet[Alias]:
        queryset = super().get_queryset()
        return queryset.exclude(is_canonical=1)


class SpanningCurrentSiteManager(managers.CurrentSiteManager):
    """Unlike ``django.contrib.sites.managers.CurrentSiteManager``,
    this CurrentSiteManager can span multiple related models by using
    the django filtering syntax, namely foo__bar__baz__site.

    For example, let's say you have a model called Layer, which has
    a field called family, which points to a model called LayerFamily,
    which in turn has a field called site pointing to a
    django.contrib.sites Site model. On Layer, add the following
    manager:

        on_site = SpanningCurrentSiteManager("family__site")

    and it will do the proper thing.
    """

    def _validate_field_name(self):
        """Given the field identifier, goes down the chain to check that
        each specified field
            a) exists,
            b) is of type ForeignKey or ManyToManyField

        If no field name is specified when instantiating
        SpanningCurrentSiteManager, it tries to find either 'site' or
        'sites' as the site link, much like CurrentSiteManager does.
        """
        if self._CurrentSiteManager__field_name is None:
            # Guess at field name
            field_names = self.model._meta.get_all_field_names()
            for potential_name in ["site", "sites"]:
                if potential_name in field_names:
                    self._CurrentSiteManager__field_name = potential_name
                    break
            else:
                raise ValueError(
                    f"{self.__class__.__name__} couldn't find a field named either 'site' or 'sites' "
                    f"in {self.model._meta.object_name}."
                )

        field_name_chain = self._CurrentSiteManager__field_name.split(LOOKUP_SEP)
        model = self.model

        for field_name in field_name_chain:
            # Throws an exception if anything goes bad
            self.validate_single_field_name(model, field_name)
            model = self.get_related_model(model, field_name)

        # If we get this far without an exception, everything is good
        self._CurrentSiteManager__is_validated = True

    @staticmethod
    def validate_single_field_name(model, field_name) -> None:
        """Checks if the given field_name can be used to make a link
        between a model and a site.

        If anything is wrong, will raise an appropriate exception,
        because that is what CurrentSiteManager expects.
        """
        try:
            field = model._meta.get_field(field_name)
            if not isinstance(field, (models.ForeignKey, models.ManyToManyField)):
                raise TypeError(f"Field {field_name} must be a ForeignKey or ManyToManyField.")
        except FieldDoesNotExist:
            raise ValueError(
                f"Couldn't find a field named {field_name} in {model._meta.object_name}."
            )

    @staticmethod
    def get_related_model(model, field_name) -> models.Model:
        """Given a model and the name of a ForeignKey or ManyToManyField column
        as a string, returns the associated model.
        """
        try:
            return model._meta.get_field(field_name).remote_field.model
        except AttributeError:
            return model._meta.get_field(field_name).related_model
