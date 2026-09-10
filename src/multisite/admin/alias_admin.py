from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.sites.admin import SiteAdmin
from django.contrib.sites.models import Site
from django.db import models

from ..forms import SiteForm
from ..models import Alias

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.core.handlers.wsgi import WSGIRequest as BaseWSGIRequest
    from django.db.models import QuerySet

    class UserProfile(models.Model):
        user = models.ForeignKey(User, on_delete=models.PROTECT)
        sites = models.ManyToManyField(Site, blank=True)

    class WSGIRequest(BaseWSGIRequest):
        user: User


@admin.register(Alias)
class AliasAdmin(admin.ModelAdmin):
    """Admin for Alias model."""

    list_display = ("domain", "site", "is_canonical", "redirect_to_canonical")
    list_filter = ("is_canonical", "redirect_to_canonical")
    ordering = ("domain",)
    raw_id_fields = ("site",)
    readonly_fields = ("is_canonical",)
    search_fields = ("domain",)


class AliasInline(admin.TabularInline):
    """Inline for Alias model, showing non-canonical aliases."""

    model = Alias
    extra = 1
    ordering = ("domain",)

    def get_queryset(self, request: WSGIRequest) -> QuerySet[Alias]:
        """Returns only non-canonical aliases."""
        qs = self.model.aliases.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


# HACK: Monkeypatch AliasInline into SiteAdmin
SiteAdmin.inlines = type(SiteAdmin.inlines)([AliasInline]) + SiteAdmin.inlines

# HACK: Monkeypatch Alias validation into SiteForm
SiteAdmin.form = SiteForm
