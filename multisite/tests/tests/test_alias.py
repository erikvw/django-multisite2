from django.contrib.sites.models import Site
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.test import TestCase

from multisite.exceptions import MultisiteInvalidHostError
from multisite.models import Alias
from multisite.utils import (
    create_or_sync_alias_from_site,
    create_or_sync_canonical_from_all_sites,
    create_or_sync_missing_canonical_from_site_domain,
    sync_blank_domain,
    sync_canonical_from_site_domain,
)


class AliasTest(TestCase):
    def setUp(self):
        Alias.objects.all().delete()
        Site.objects.all().delete()

    def test_create(self):
        Site.objects.create()  # site0
        site1 = Site.objects.create(domain="1.example")
        site2 = Site.objects.create(domain="2.example")
        # Missing site
        self.assertRaises(ValidationError, Alias.objects.create)
        self.assertRaises(ValidationError, Alias.objects.create, domain="0.example")
        # Valid
        self.assertTrue(Alias.objects.create(domain="1a.example", site=site1))
        # Duplicate domain
        self.assertRaises(
            ValidationError, Alias.objects.create, domain=site1.domain, site=site1
        )
        self.assertRaises(
            ValidationError, Alias.objects.create, domain=site2.domain, site=site1
        )
        self.assertRaises(
            ValidationError, Alias.objects.create, domain="1a.example", site=site1
        )
        # Duplicate domains, case-sensitivity
        self.assertRaises(
            ValidationError, Alias.objects.create, domain="1A.EXAMPLE", site=site2
        )
        self.assertRaises(
            ValidationError, Alias.objects.create, domain="2.EXAMPLE", site=site2
        )
        # Duplicate is_canonical
        site1.domain = "1b.example"
        self.assertRaises(
            ValidationError,
            Alias.objects.create,
            domain=site1.domain,
            site=site1,
            is_canonical=1,
        )
        # Invalid is_canonical
        self.assertRaises(
            ValidationError,
            Alias.objects.create,
            domain=site1.domain,
            site=site1,
            is_canonical=0,
        )

    def test_repr(self):
        site = Site.objects.create(domain="example.com")
        self.assertEqual(
            repr(Alias.objects.get(site=site)),
            "<Alias: %(domain)s -> %(domain)s>" % site.__dict__,
        )

    def test_managers(self):
        site = Site.objects.create(domain="example.com")
        Alias.objects.create(site=site, domain="example.org")
        self.assertEqual(
            set(Alias.objects.values_list("domain", flat=True)),
            set(["example.com", "example.org"]),
        )
        self.assertEqual(
            set(Alias.canonical.values_list("domain", flat=True)), set(["example.com"])
        )
        self.assertEqual(
            set(Alias.aliases.values_list("domain", flat=True)), set(["example.org"])
        )

    def test_sync_canonical_from_site_domain(self):
        # Create Sites with Aliases
        Site.objects.create()
        site1 = Site.objects.create(domain="1.example.com")
        site2 = Site.objects.create(domain="2.example.com")
        # Create Site without triggering signals
        site3 = Site(domain="3.example.com")
        site3.save_base(raw=True)
        self.assertEqual(
            set(Alias.objects.values_list("domain", flat=True)),
            set([site1.domain, site2.domain]),
        )
        # Sync existing
        site1.domain = "1.example.org"
        site1.save_base(raw=True)
        site2.domain = "2.example.org"
        site2.save_base(raw=True)
        sync_canonical_from_site_domain()
        self.assertEqual(
            set(Alias.objects.values_list("domain", flat=True)),
            set([site1.domain, site2.domain]),
        )
        # Sync with filter
        site1.domain = "1.example.net"
        site1.save_base(raw=True)
        site2.domain = "2.example.net"
        site2.save_base(raw=True)
        sync_canonical_from_site_domain(site__domain=site1.domain)
        self.assertEqual(
            set(Alias.objects.values_list("domain", flat=True)),
            set([site1.domain, "2.example.org"]),
        )

    def test_sync_missing(self):
        Site.objects.create()
        site1 = Site.objects.create(domain="1.example.com")
        # Update site1 without triggering signals
        site1.domain = "1.example.org"
        site1.save_base(raw=True)
        # Create site2 without triggering signals
        site2 = Site(domain="2.example.org")
        site2.save_base(raw=True)
        # Only site2 should be updated
        create_or_sync_missing_canonical_from_site_domain()
        self.assertEqual(
            set(Alias.objects.values_list("domain", flat=True)),
            set(["1.example.com", site2.domain]),
        )

    def test_sync_all(self):
        Site.objects.create()
        site1 = Site.objects.create(domain="1.example.com")
        # Update site1 without triggering signals
        site1.domain = "1.example.org"
        site1.save_base(raw=True)
        # Create site2 without triggering signals
        site2 = Site(domain="2.example.org")
        site2.save_base(raw=True)
        # Sync all
        create_or_sync_canonical_from_all_sites()
        self.assertEqual(
            set(Alias.objects.values_list("domain", flat=True)),
            set([site1.domain, site2.domain]),
        )

    def test_sync(self):
        # Create Site without triggering signals
        site = Site(domain="example.com")
        site.save_base(raw=True)
        # Insert Alias
        self.assertFalse(Alias.objects.filter(site=site).exists())
        create_or_sync_alias_from_site(site=site)
        self.assertEqual(Alias.objects.get(site=site).domain, site.domain)
        # Idempotent sync_alias
        create_or_sync_alias_from_site(site=site)
        self.assertEqual(Alias.objects.get(site=site).domain, site.domain)
        # Duplicate force_insert
        self.assertRaises(
            ValidationError,
            create_or_sync_alias_from_site,
            site=site,
            force_insert=True,
        )
        # Update Alias
        site.domain = "example.org"
        create_or_sync_alias_from_site(site=site)
        self.assertEqual(Alias.objects.get(site=site).domain, site.domain)
        # Clear domain
        site.domain = ""
        create_or_sync_alias_from_site(site=site)
        self.assertFalse(Alias.objects.filter(site=site).exists())

    def test_sync_blank_domain(self):
        # Create Site
        site = Site.objects.create(domain="example.com")
        # Without clearing domain
        self.assertRaises(ValueError, sync_blank_domain, site=site)
        # With an extra Alias
        site.domain = ""
        alias = Alias.objects.create(site=site, domain="example.org")
        self.assertRaises(MultipleObjectsReturned, sync_blank_domain, site=site)
        # With a blank site
        alias.delete()
        sync_blank_domain(site=site)
        self.assertFalse(Alias.objects.filter(site=site).exists())

    def test_hooks(self):
        # Create empty Site
        Site.objects.create()
        self.assertFalse(Alias.objects.filter(domain="").exists())
        # Create Site
        site = Site.objects.create(domain="example.com")
        alias = Alias.objects.get(site=site)
        self.assertEqual(alias.domain, site.domain)
        self.assertTrue(alias.is_canonical)
        # Create a non-canonical alias
        Alias.objects.create(site=site, domain="example.info")
        # Change Site to another domain name
        site.domain = "example.org"
        site.save()
        self.assertEqual(Alias.canonical.get(site=site).domain, site.domain)
        self.assertEqual(Alias.aliases.get(site=site).domain, "example.info")
        # Change Site to an empty domain name
        site.domain = ""
        self.assertRaises(MultipleObjectsReturned, site.save)

        Alias.aliases.all().delete()
        Site.objects.get(domain="").delete()  # domain is unique in Django1.9
        site.save()
        self.assertFalse(Alias.objects.filter(site=site).exists())

        # Change Site from an empty domain name
        site.domain = "example.net"
        site.save()
        site.refresh_from_db()
        self.assertEqual(Alias.canonical.get(site=site).domain, site.domain)

        # Delete Site, which deletes Alias
        site.delete()
        self.assertFalse(Alias.objects.filter(site__domain="example.net").exists())

    def test_expand_netloc(self):
        _expand_netloc = Alias.objects._expand_netloc
        self.assertRaises(MultisiteInvalidHostError, _expand_netloc, "")
        self.assertRaises(MultisiteInvalidHostError, _expand_netloc, "", 8000)
        self.assertEqual(
            _expand_netloc("testserver", 8000),
            ["testserver:8000", "testserver", "*:8000", "*"],
        )
        self.assertEqual(_expand_netloc("testserver"), ["testserver", "*"])
        self.assertEqual(
            _expand_netloc("example.com", 8000),
            ["example.com:8000", "example.com", "*.com:8000", "*.com", "*:8000", "*"],
        )
        self.assertEqual(_expand_netloc("example.com"), ["example.com", "*.com", "*"])
        self.assertEqual(
            _expand_netloc("www.example.com", 8000),
            [
                "www.example.com:8000",
                "www.example.com",
                "*.example.com:8000",
                "*.example.com",
                "*.com:8000",
                "*.com",
                "*:8000",
                "*",
            ],
        )
        self.assertEqual(
            _expand_netloc("www.example.com"),
            ["www.example.com", "*.example.com", "*.com", "*"],
        )

    def test_resolve(self):
        site = Site.objects.create(domain="example.com")
        alias = Alias.objects.get(domain="example.com")
        # *.example.com
        self.assertEqual(Alias.objects.resolve("www.example.com"), None)
        self.assertEqual(Alias.objects.resolve("www.dev.example.com"), None)

        alias = Alias.objects.create(site=site, domain="*.example.com")
        self.assertEqual(Alias.objects.resolve("www.example.com"), alias)
        self.assertEqual(Alias.objects.resolve("www.dev.example.com"), alias)
        # *
        self.assertEqual(Alias.objects.resolve("example.net"), None)

        alias = Alias.objects.create(site=site, domain="*")
        self.assertEqual(Alias.objects.resolve("example.net"), alias)
        self.assertEqual(Alias.objects.resolve("blah"), alias)
