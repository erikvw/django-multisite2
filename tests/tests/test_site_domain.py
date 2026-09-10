from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase

from multisite import SiteDomain


class TestSiteDomain(TestCase):
    def setUp(self):
        Site.objects.all().delete()
        self.domain = "example.com"
        self.site = Site.objects.create(domain=self.domain)

    def test_init(self):
        self.assertEqual(int(SiteDomain(default=self.domain)), self.site.id)
        self.assertRaises(ObjectDoesNotExist, int, SiteDomain(default="invalid"))
        self.assertRaises(TypeError, SiteDomain, default=None)
        self.assertRaises(TypeError, SiteDomain, default=1)

    def test_deferred_site(self):
        domain = "example.org"
        self.assertRaises(ObjectDoesNotExist, int, SiteDomain(default=domain))
        site = Site.objects.create(domain=domain)
        self.assertEqual(int(SiteDomain(default=domain)), site.id)
