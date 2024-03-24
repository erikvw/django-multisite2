from __future__ import annotations

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint
from django.utils.translation import gettext_lazy as _

from .managers import AliasManager, CanonicalAliasManager, NotCanonicalAliasManager
from .validators import validate_1_or_none

_site_domain = Site._meta.get_field("domain")


__all__ = ["Alias"]


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

    def __str__(self):
        return f"{self.domain} -> {self.site.domain}"

    def __repr__(self):
        return f"<Alias: {self}>"

    objects = AliasManager()
    canonical = CanonicalAliasManager()
    aliases = NotCanonicalAliasManager()

    class Meta:
        verbose_name = _("Alias")
        verbose_name_plural = _("Aliases")
        constraints = [
            UniqueConstraint(
                name="unique_is_canonical_site",
                fields=["is_canonical", "site"],
                # nulls_distinct=False, DJ5
            )
        ]

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
