from django.apps import AppConfig as DjangoAppConfig
from django.conf import settings
from django.core.checks import register
from django.db.models.signals import post_migrate

from .hacks import use_framework_for_site_cache
from .system_checks import (
    multisite_middleware_check,
    multisite_timezone_setting_check,
)
from .utils import create_or_sync_canonical_from_all_sites


def post_migrate_sync_alias(apps=None, **kwargs):
    """Syncs canonical Alias objects for all existing Site objects."""
    create_or_sync_canonical_from_all_sites(apps)


class AppConfig(DjangoAppConfig):
    name = "multisite"
    verbose_name = "Multisite"
    default_auto_field = "django.db.models.BigAutoField"

    def import_models(self):
        use_framework_for_site_cache()
        super().import_models()

    def ready(self):
        register(multisite_middleware_check)
        register(multisite_timezone_setting_check, deploy=True)
        if not getattr(settings, "MULTISITE_REGISTER_POST_MIGRATE_SYNC_ALIAS", True):
            post_migrate.connect(
                post_migrate_sync_alias,
                sender=self,
                dispatch_uid="multisite.post_migrate_sync_alias",
            )
