from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.sites.models import Site
from django.db import models

from ..utils import get_user_sites
from .multisite_changelist import MultisiteChangeList

__all__ = ["MultisiteModelAdmin"]

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.core.handlers.wsgi import WSGIRequest as BaseWSGIRequest
    from django.db.models import QuerySet

    class UserProfile(models.Model):
        user = models.ForeignKey(User, on_delete=models.PROTECT)
        sites = models.ManyToManyField(Site, blank=True)

    class WSGIRequest(BaseWSGIRequest):
        user: User


class MultisiteModelAdmin(admin.ModelAdmin):
    """
    A very helpful ModelAdmin class for handling multi-site django
    applications.
    """

    filter_sites_by_current_object = False

    def __init__(self, model, admin_site):
        self.object_sites: tuple | None = None
        super().__init__(model, admin_site)

    def get_queryset(self, request: WSGIRequest) -> QuerySet:
        """
        Filters lists of items to items belonging to sites assigned to the
        current member.

        Additionally, for cases where the field containing a reference
        to 'site' or 'sites' isn't immediate -- one can supply the
        ModelAdmin class with a list of fields to check the site of:

         - multisite_filter_fields
            A list of paths to a 'site' or 'sites' field on a related model to
            filter the queryset on.

        (As long as you're not a superuser)
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_sites = get_user_sites(request)
        if hasattr(qs.model, "site"):
            qs = qs.filter(site__in=user_sites)
        elif hasattr(qs.model, "sites"):
            qs = qs.filter(sites__in=user_sites)

        if hasattr(self, "multisite_filter_fields"):
            for field in self.multisite_filter_fields:
                qkwargs = {"{field}__in".format(field=field): user_sites}
                qs = qs.filter(**qkwargs)

        return qs

    def add_view(
        self, request: WSGIRequest, form_url: str = "", extra_context: dict = None
    ):
        if self.filter_sites_by_current_object:
            if hasattr(self.model, "site") or hasattr(self.model, "sites"):
                self.object_sites = tuple()
        return super().add_view(request, form_url, extra_context)

    def change_view(
        self,
        request: WSGIRequest,
        object_id,
        form_url: str = "",
        extra_context: dict = None,
    ):
        if self.filter_sites_by_current_object:
            object_instance = self.get_object(request, object_id)
            try:
                self.object_sites = object_instance.sites.values_list("pk", flat=True)
            except AttributeError:
                try:
                    self.object_sites = (object_instance.site.pk,)
                except AttributeError:
                    pass  # assume the object doesn't belong to a site
        return super().change_view(request, object_id, form_url, extra_context)

    def handle_multisite_foreign_keys(self, db_field, request, **kwargs):
        """
        Filters the foreignkey queryset for fields referencing other models
        to those models assigned to a site belonging to the current member
        (if they aren't a superuser), and (optionally) belonging to the same
        site as the current object.

        Also prevents (non-super) users from assigning objects to sites that
        they are not members of.

        If the foreign key does not have a site/sites field directly, you can
        specify a path to a site/sites field to filter on by setting the key:

            - multisite_foreign_key_site_path

        to a dictionary pointing specific foreign key field instances
        from their model to the site field to filter on something
        like:

            multisite_indirect_foreign_key_path = {
                    'plan_instance': 'plan__site'
                }

        for a field named 'plan_instance' referencing a model with a
        foreign key named 'plan' having a foreign key to 'site'.

        To filter the FK queryset to the same sites the current object belongs
        to, simply set `filter_sites_by_current_object` to `True`.

        Caveats:

        1) If you're adding an object that belongs to a site (or sites),
        and you've set `self.limit_sites_by_current_object = True`,
        then the FK fields to objects that also belong to a site won't show
        any objects. This is due to filtering on an empty queryset.
        """
        user_sites = get_user_sites(request)
        try:
            remote_model = db_field.remote_field.model
        except AttributeError:
            remote_model = db_field.related_model
        if hasattr(remote_model, "site"):
            kwargs["queryset"] = remote_model._default_manager.filter(
                site__in=user_sites
            )
        if hasattr(remote_model, "sites"):
            kwargs["queryset"] = remote_model._default_manager.filter(
                sites__in=user_sites
            )
        if db_field.name == "site" or db_field.name == "sites":
            kwargs["queryset"] = user_sites
        if (
            hasattr(self, "multisite_indirect_foreign_key_path")
            and db_field.name in self.multisite_indirect_foreign_key_path.keys()
        ):
            fkey = self.multisite_indirect_foreign_key_path[db_field.name]
            kwargs["queryset"] = remote_model._default_manager.filter(
                **{fkey: user_sites}
            )

        return kwargs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        kwargs = self.handle_multisite_foreign_keys(db_field, request, **kwargs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        kwargs = self.handle_multisite_foreign_keys(db_field, request, **kwargs)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_changelist(self, request, **kwargs):
        """
        Restrict the site filter (if there is one) to sites you are
        associated with, or remove it entirely if you're just
        associated with one site. Unless you're a super-user, of
        course.
        """
        return MultisiteChangeList
