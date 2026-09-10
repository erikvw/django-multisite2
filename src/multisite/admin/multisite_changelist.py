from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.admin.views.main import ChangeList
from django.contrib.sites.models import Site
from django.db import models

from ..utils import get_user_sites

__all__ = ["MultisiteChangeList"]

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.core.handlers.wsgi import WSGIRequest as BaseWSGIRequest

    class UserProfile(models.Model):
        user = models.ForeignKey(User, on_delete=models.PROTECT)
        sites = models.ManyToManyField(Site, blank=True)

    class WSGIRequest(BaseWSGIRequest):
        user: User


class MultisiteChangeList(ChangeList):
    """
    A ChangeList like the built-in admin one, but it excludes site filters for
    sites you're not associated with, unless you're a super-user.

    At this point, it's probably fragile, given its reliance on Django
    internals.
    """

    def get_filters(self, request: WSGIRequest, *args, **kwargs) -> tuple[list, bool]:
        """
        This might be considered a fragile function, since it relies on a
        fair bit of Django's internals.
        """
        get_filters = super().get_filters
        filter_specs, has_filter_specs = get_filters(request)
        if request.user.is_superuser or not has_filter_specs:
            return filter_specs, has_filter_specs
        new_filter_specs = []
        user_sites = frozenset(get_user_sites(request).values_list("pk", "domain"))
        for filter_spec in filter_specs:
            try:
                try:
                    remote_model = filter_spec.field.remote_field.model
                except AttributeError:
                    remote_model = filter_spec.field.related_model
            except AttributeError:
                new_filter_specs.append(filter_spec)
                continue
            if remote_model is not Site:
                new_filter_specs.append(filter_spec)
                continue
            lookup_choices = frozenset(filter_spec.lookup_choices) & user_sites
            if len(lookup_choices) > 1:
                # put the choices back into the form they came in
                filter_spec.lookup_choices = list(lookup_choices)
                filter_spec.lookup_choices.sort()
                new_filter_specs.append(filter_spec)

        return new_filter_specs, bool(new_filter_specs)
