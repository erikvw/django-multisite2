from django.contrib.sites.models import Site
from django.test import TestCase

from multisite import SiteID


class TestSiteID(TestCase):
    def setUp(self):
        Site.objects.all().delete()
        self.site = Site.objects.create(domain="example.com")
        self.site_id = SiteID()

    def test_invalid_default(self):
        self.assertRaises(ValueError, SiteID, default="a")
        self.assertRaises(ValueError, SiteID, default=self.site_id)

    def test_compare_default_site_id(self):
        self.site_id = SiteID(default=self.site.id)
        self.assertEqual(self.site_id, self.site.id)
        self.assertFalse(self.site_id != self.site.id)
        self.assertFalse(self.site_id < self.site.id)
        self.assertTrue(self.site_id <= self.site.id)
        self.assertFalse(self.site_id > self.site.id)
        self.assertTrue(self.site_id >= self.site.id)

    def test_compare_site_ids(self):
        self.site_id.set(1)
        self.assertEqual(self.site_id, self.site_id)
        self.assertFalse(self.site_id != self.site_id)
        self.assertFalse(self.site_id < self.site_id)
        self.assertTrue(self.site_id <= self.site_id)
        self.assertFalse(self.site_id > self.site_id)
        self.assertTrue(self.site_id >= self.site_id)

    def test_compare_differing_types(self):
        self.site_id.set(1)
        self.assertNotEqual(self.site_id, "1")
        self.assertFalse(self.site_id == "1")
        self.assertTrue(self.site_id < "1")
        self.assertTrue(self.site_id <= "1")
        self.assertFalse(self.site_id > "1")
        self.assertFalse(self.site_id >= "1")
        self.assertNotEqual("1", self.site_id)
        self.assertFalse("1" == self.site_id)
        self.assertFalse("1" < self.site_id)
        self.assertFalse("1" <= self.site_id)
        self.assertTrue("1" > self.site_id)
        self.assertTrue("1" >= self.site_id)

    def test_set(self):
        self.site_id.set(10)
        self.assertEqual(int(self.site_id), 10)
        self.site_id.set(20)
        self.assertEqual(int(self.site_id), 20)
        self.site_id.set(self.site)
        self.assertEqual(int(self.site_id), self.site.id)

    def test_hash(self):
        self.site_id.set(10)
        self.assertEqual(hash(self.site_id), 10)
        self.site_id.set(20)
        self.assertEqual(hash(self.site_id), 20)

    def test_str_repr(self):
        self.site_id.set(10)
        self.assertEqual(str(self.site_id), "10")
        self.assertEqual(repr(self.site_id), "10")

    def test_context_manager(self):
        self.assertEqual(self.site_id.site_id, None)
        with self.site_id.override(1):
            self.assertEqual(self.site_id.site_id, 1)
            with self.site_id.override(2):
                self.assertEqual(self.site_id.site_id, 2)
            self.assertEqual(self.site_id.site_id, 1)
        self.assertEqual(self.site_id.site_id, None)
