from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.db import connections, router
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from multisite.utils import create_or_sync_alias_from_site


@receiver(pre_save, sender=Site, weak=False, dispatch_uid="site_domain_changed_hook")
def pre_save_site_domain_changed(sender, instance, raw, *args, **kwargs):
    """Updates canonical Alias object if Site.domain has changed."""
    if not raw and instance.pk is not None:
        try:
            original = sender.objects.get(pk=instance.pk)
        except ObjectDoesNotExist:
            pass
        else:
            # Update Alias.domain to match site
            if original.domain != instance.domain:
                create_or_sync_alias_from_site(site=instance)


@receiver(post_save, sender=Site, weak=False, dispatch_uid="site_created_hook")
def post_save_site_created(sender, instance, raw, created, *args, **kwargs):
    """Creates canonical Alias object for a new Site."""
    if not raw and created:
        # When running create_default_site() because of post_syncdb,
        # don't try to sync before the db_table has been created.
        using = router.db_for_write(sender)
        tables = connections[using].introspection.table_names()
        if sender._meta.db_table not in tables:
            pass
        else:
            # Update Alias.domain to match site
            create_or_sync_alias_from_site(site=instance)
