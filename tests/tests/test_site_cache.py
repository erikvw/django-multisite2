from django.conf import settings
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings

from multisite import SiteID
from multisite.hacks import use_framework_for_site_cache


@override_settings(SITE_ID=SiteID())
class SiteCacheTest(TestCase):
    def _initialize_cache(self):
        # initialize cache again so override key prefix settings are used
        from django.contrib.sites import models

        use_framework_for_site_cache()
        self.cache = models.SITE_CACHE

    def setUp(self):
        from django.contrib.sites import models

        if hasattr(models, "clear_site_cache"):
            # Before Django 1.6, the Site cache is cleared after the Site
            # object has been created. This replicates that behaviour.
            def save(self, *args, **kwargs):
                super(models.Site, self).save(*args, **kwargs)
                models.SITE_CACHE.clear()

            models.Site.save = save

        self._initialize_cache()
        Site.objects.all().delete()
        self.host = "example.com"
        self.site = Site.objects.create(domain=self.host)
        settings.SITE_ID.set(self.site.id)

    def test_get_current(self):
        self.assertRaises(KeyError, self.cache.__getitem__, self.site.id)
        # Populate cache
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(self.cache[self.site.id], self.site)
        self.assertEqual(self.cache.get(key=self.site.id), self.site)
        self.assertEqual(self.cache.get(key=-1), None)  # Site doesn't exist
        self.assertEqual(self.cache.get(-1, "Default"), "Default")  # Site doesn't exist
        self.assertEqual(
            self.cache.get(key=-1, default="Non-existant"), "Non-existant"
        )  # Site doesn't exist
        self.assertEqual(
            "Non-existant",
            self.cache.get(self.site.id, default="Non-existant", version=100),
        )  # Wrong key version 3
        # Clear cache
        self.cache.clear()
        self.assertRaises(KeyError, self.cache.__getitem__, self.site.id)
        self.assertEqual(self.cache.get(key=self.site.id, default="Cleared"), "Cleared")

    def test_create_site(self):
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(Site.objects.get_current().domain, self.site.domain)
        # Create new site
        site = Site.objects.create(domain="example.org")
        settings.SITE_ID.set(site.id)
        self.assertEqual(Site.objects.get_current(), site)
        self.assertEqual(Site.objects.get_current().domain, site.domain)

    def test_change_site(self):
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(Site.objects.get_current().domain, self.site.domain)
        # Change site domain
        self.site.domain = "example.org"
        self.site.save()
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(Site.objects.get_current().domain, self.site.domain)

    def test_delete_site(self):
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(Site.objects.get_current().domain, self.site.domain)
        # Delete site
        self.site.delete()
        self.assertRaises(KeyError, self.cache.__getitem__, self.site.id)

    @override_settings(CACHE_MULTISITE_KEY_PREFIX="__test__")
    def test_multisite_key_prefix(self):
        self._initialize_cache()
        # Populate cache
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(self.cache[self.site.id], self.site)
        self.assertEqual(
            self.cache._cache._get_cache_key(self.site.id),
            "sites.{}.{}".format(settings.CACHE_MULTISITE_KEY_PREFIX, self.site.id),
            self.cache._cache._get_cache_key(self.site.id),
        )

    @override_settings(
        CACHE_MULTISITE_ALIAS="multisite",
        CACHES={
            "multisite": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "KEY_PREFIX": "looselycoupled",
            }
        },
    )
    def test_default_key_prefix(self):
        """
        If CACHE_MULTISITE_KEY_PREFIX is undefined,
        the caching system should use CACHES[current]['KEY_PREFIX'].
        """
        self._initialize_cache()
        # Populate cache
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(self.cache[self.site.id], self.site)
        self.assertEqual(
            self.cache._cache._get_cache_key(self.site.id),
            "sites.looselycoupled.{}".format(self.site.id),
        )

    @override_settings(
        CACHE_MULTISITE_KEY_PREFIX="virtuouslyvirtual",
    )
    def test_multisite_key_prefix_takes_priority_over_default(self):
        self._initialize_cache()
        # Populate cache
        self.assertEqual(Site.objects.get_current(), self.site)
        self.assertEqual(self.cache[self.site.id], self.site)
        self.assertEqual(
            self.cache._cache._get_cache_key(self.site.id),
            "sites.virtuouslyvirtual.{}".format(self.site.id),
        )
