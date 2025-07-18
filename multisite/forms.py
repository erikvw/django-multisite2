from __future__ import absolute_import, unicode_literals

from django.contrib.sites.admin import SiteAdmin
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from .models import Alias


class SiteForm(SiteAdmin.form):
    def clean_domain(self):
        domain = self.cleaned_data["domain"]

        try:
            alias = Alias.objects.get(domain=domain)
        except ObjectDoesNotExist:
            # New Site that doesn't clobber an Alias
            return domain

        if alias.site_id == self.instance.pk and alias.is_canonical:
            return domain

        raise ValidationError(
            'Cannot overwrite non-canonical Alias: "%s"' % alias.domain
        )
