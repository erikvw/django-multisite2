from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, HttpResponse
from django.test import TestCase, override_settings, tag

from multisite import SiteID
from multisite.exceptions import MultisiteCacheError, MultisiteError
from multisite.middleware import DynamicSiteMiddleware
from multisite.models import Alias

from ..get_allowed_hosts import get_allowed_hosts
from ..get_test_http_response import get_test_http_response
from .request_factory import RequestFactory


@override_settings(
    ROOT_URLCONF="multisite_app.urls",
    SITE_ID=SiteID(default=0),
    CACHE_MULTISITE_ALIAS="multisite",
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
        "multisite": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    },
    MULTISITE_FALLBACK=None,
    ALLOWED_HOSTS=get_allowed_hosts("example.com", "anothersite.example", replace=True),
)
class DynamicSiteMiddlewareTest(TestCase):
    def setUp(self):
        self.host = "example.com"
        self.factory = RequestFactory(host=self.host)

        Site.objects.all().delete()
        self.site = Site.objects.create(pk=1, domain=self.host)
        self.site2 = Site.objects.create(pk=2, domain="anothersite.example")

    def test_valid_domain(self):
        # Make the request
        request = self.factory.get("/")
        self.assertEqual(DynamicSiteMiddleware(HttpResponse)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site.pk)
        # Request again
        self.assertEqual(DynamicSiteMiddleware(HttpResponse)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site.pk)

    def test_valid_domain_port(self):
        # Make the request with a specific port
        request = self.factory.get("/", host=self.host + ":8000")
        self.assertEqual(DynamicSiteMiddleware(HttpResponse)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site.pk)
        # Request again
        self.assertEqual(DynamicSiteMiddleware(HttpResponse)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site.pk)

    def test_case_sensitivity(self):
        # Make the request in all uppercase
        request = self.factory.get("/", host=self.host.upper())
        self.assertEqual(DynamicSiteMiddleware(HttpResponse)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site.pk)

    def test_change_domain(self):
        # Make the request
        request = self.factory.get("/")
        self.assertEqual(DynamicSiteMiddleware(HttpResponse)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site.pk)
        # Another request with a different site
        request = self.factory.get("/", host=self.site2.domain)
        self.assertEqual(DynamicSiteMiddleware(HttpResponse)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site2.pk)

    def test_unknown_host(self):
        # Unknown host
        request = self.factory.get("/", host="unknown")
        with self.assertRaises(Http404):
            DynamicSiteMiddleware(HttpResponse)(request)
        # The middleware resets SiteID to its default value, as given above, on error.
        self.assertEqual(settings.SITE_ID, 0)

    def test_unknown_hostport(self):
        # Unknown host:port
        request = self.factory.get("/", host="unknown:8000")
        with self.assertRaises(Http404):
            DynamicSiteMiddleware(HttpResponse)(request)
        # The middleware resets SiteID to its default value, as given above, on error.
        self.assertEqual(settings.SITE_ID, 0)

    def test_invalid_host(self):
        # Invalid host
        request = self.factory.get("/", host="")
        with self.assertRaises(Http404):
            DynamicSiteMiddleware(HttpResponse)(request)

    def test_invalid_hostport(self):
        # Invalid host:port
        request = self.factory.get("/", host=":8000")
        with self.assertRaises(Http404):
            DynamicSiteMiddleware(HttpResponse)(request)

    def test_no_sites(self):
        # FIXME: this needs to go into its own TestCase since
        #  it requires modifying the fixture to work properly
        # Remove all Sites
        Site.objects.all().delete()
        # Make the request
        request = self.factory.get("/")
        self.assertRaises(Http404, DynamicSiteMiddleware(HttpResponse), request)
        # The middleware resets SiteID to its default value, as given above, on error.
        self.assertEqual(settings.SITE_ID, 0)

    @override_settings(MULTISITE_DEBUG=True)
    def test_debug_no_sites_raises(self):
        Site.objects.all().delete()
        request = self.factory.get("/")
        self.assertRaises(MultisiteCacheError, DynamicSiteMiddleware(HttpResponse), request)

    @override_settings(MULTISITE_DEBUG=False)
    def test_no_sites_raises(self):
        Site.objects.all().delete()
        request = self.factory.get("/")
        self.assertRaises(Http404, DynamicSiteMiddleware(HttpResponse), request)

    @override_settings(ALLOWED_HOSTS=["example.org"])
    def test_redirect(self):
        host = "example.org"
        alias = Alias.objects.create(site=self.site, domain=host)
        self.assertTrue(alias.redirect_to_canonical)
        # Make the request
        http_response = get_test_http_response()
        request = self.factory.get("/path", host=host)
        response = DynamicSiteMiddleware(http_response)(request)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "http://%s/path" % self.host)

    @override_settings(ALLOWED_HOSTS=["example.org"])
    def test_no_redirect(self):
        host = "example.org"
        Alias.objects.create(site=self.site, domain=host, redirect_to_canonical=False)
        # Make the request
        http_response = get_test_http_response()
        request = self.factory.get("/path", host=host)
        self.assertEqual(DynamicSiteMiddleware(http_response)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, self.site.pk)

    @tag("9")
    def test_integration(self):
        """Test that the middleware loads and runs properly
        under settings.MIDDLEWARE.
        """
        self.assertTrue(Site.objects.get(domain="example.com"))
        self.assertTrue(Site.objects.get(domain="anothersite.example"))

        response = self.client.get("/domain/", HTTP_HOST=self.host)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.site.domain)
        self.assertEqual(settings.SITE_ID, self.site.pk)

        response = self.client.get("/domain/", HTTP_HOST=self.site2.domain)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.site2.domain)
        self.assertEqual(settings.SITE_ID, self.site2.pk)


@override_settings(
    SITE_ID=SiteID(default=0),
    CACHE_MULTISITE_ALIAS="multisite",
    CACHES={"multisite": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}},
    MULTISITE_FALLBACK=None,
    MULTISITE_FALLBACK_KWARGS={},
)
class DynamicSiteMiddlewareFallbackTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory(host="unknown")

        Site.objects.all().delete()

    def test_404(self):
        http_response = get_test_http_response()
        request = self.factory.get("/")
        self.assertRaises(Http404, DynamicSiteMiddleware(http_response), request)
        self.assertEqual(settings.SITE_ID, 0)

    def test_testserver(self):
        host = "testserver"
        site = Site.objects.create(domain=host)
        http_response = get_test_http_response()
        request = self.factory.get("/", host=host)
        self.assertEqual(DynamicSiteMiddleware(http_response)(request).status_code, 200)
        self.assertEqual(settings.SITE_ID, site.pk)

    def test_string_class(self):
        # Class based
        settings.MULTISITE_FALLBACK = "django.views.generic.base.RedirectView"
        settings.MULTISITE_FALLBACK_KWARGS = {
            "url": "http://example.com/",
            "permanent": False,
        }
        request = self.factory.get("/")
        http_response = get_test_http_response()
        response = DynamicSiteMiddleware(http_response)(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.MULTISITE_FALLBACK_KWARGS["url"])

    def test_class_view(self):
        from django.views.generic.base import RedirectView

        settings.MULTISITE_FALLBACK = RedirectView.as_view(
            url="http://example.com/", permanent=False
        )
        http_response = get_test_http_response()
        request = self.factory.get("/")
        response = DynamicSiteMiddleware(http_response)(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://example.com/")

    def test_invalid(self):
        settings.MULTISITE_FALLBACK = ""
        http_response = get_test_http_response()
        request = self.factory.get("/")
        self.assertRaises(ImproperlyConfigured, DynamicSiteMiddleware(http_response), request)


@override_settings(SITE_ID=0)
class DynamicSiteMiddlewareSettingsTest(TestCase):

    def test_invalid_settings(self):
        http_response = get_test_http_response()
        self.assertRaises(MultisiteError, DynamicSiteMiddleware, http_response)


@override_settings(
    SITE_ID=SiteID(default=0),
    CACHE_MULTISITE_ALIAS="multisite",
    CACHES={"multisite": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    MULTISITE_FALLBACK=None,
    ALLOWED_HOSTS=get_allowed_hosts("example.com", replace=True),
)
class CacheTest(TestCase):
    def setUp(self):
        self.host = "example.com"
        self.factory = RequestFactory(host=self.host)

        Site.objects.all().delete()
        self.site = Site.objects.create(domain=self.host)

    def test_site_domain_changed(self):
        # Test to ensure that the cache is cleared properly
        http_response = get_test_http_response()
        middleware = DynamicSiteMiddleware(http_response)
        cache_key = middleware.get_cache_key(self.host)
        self.assertEqual(middleware.cache.get(cache_key), None)
        # Make the request
        request = self.factory.get("/")
        self.assertEqual(middleware(request).status_code, 200)
        self.assertEqual(middleware.cache.get(cache_key).site_id, self.site.pk)
        # Change the domain name
        self.site.domain = "example.org"
        self.site.save()
        self.assertEqual(middleware.cache.get(cache_key), None)
        # Make the request again, which will now be invalid
        request = self.factory.get("/")
        self.assertRaises(Http404, middleware, request)
        self.assertEqual(settings.SITE_ID, 0)
