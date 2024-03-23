import tempfile

from django.contrib.sites.models import Site
from django.http import HttpResponse, SimpleCookie
from django.test import TestCase, override_settings

from multisite.exceptions import MultisiteCookieDomainDepthError
from multisite.middleware import CookieDomainMiddleware

from ..get_allowed_hosts import get_allowed_hosts
from ..get_test_http_response import get_test_http_response
from .request_factory import RequestFactory


@override_settings(
    MULTISITE_COOKIE_DOMAIN_DEPTH=0,
    MULTISITE_PUBLIC_SUFFIX_LIST_CACHE_DIR=None,
    ALLOWED_HOSTS=get_allowed_hosts(".com"),
    MULTISITE_EXTRA_HOSTS=[".extrahost.com"],
)
class TestCookieDomainMiddleware(TestCase):

    def setUp(self):
        self.factory = RequestFactory(host="example.com")
        Site.objects.all().delete()
        # create sites so we populate ALLOWED_HOSTS
        Site.objects.create(domain="app.test1.example.com")
        Site.objects.create(domain="app.test2.example.com")
        Site.objects.create(domain="example.com")
        Site.objects.create(domain="new.app.test3.example.com")
        Site.objects.create(domain="test.example.com")

    def test_init(self):
        self.assertEqual(CookieDomainMiddleware(HttpResponse).depth, 0)
        self.assertEqual(
            CookieDomainMiddleware(HttpResponse).psl_cache_dir, tempfile.gettempdir()
        )

    @override_settings(
        MULTISITE_COOKIE_DOMAIN_DEPTH=1, MULTISITE_PUBLIC_SUFFIX_LIST_CACHE_DIR="/var/psl"
    )
    def test_init2(self):
        middleware = CookieDomainMiddleware(HttpResponse)
        self.assertEqual(middleware.depth, 1)
        self.assertEqual(middleware.psl_cache_dir, "/var/psl")

    @override_settings(
        MULTISITE_COOKIE_DOMAIN_DEPTH=-1, MULTISITE_PUBLIC_SUFFIX_LIST_CACHE_DIR=None
    )
    def test_init3(self):
        self.assertRaises(
            MultisiteCookieDomainDepthError, CookieDomainMiddleware, HttpResponse
        )

    @override_settings(
        MULTISITE_COOKIE_DOMAIN_DEPTH="invalid", MULTISITE_PUBLIC_SUFFIX_LIST_CACHE_DIR=None
    )
    def test_init4(self):
        self.assertRaises(
            MultisiteCookieDomainDepthError, CookieDomainMiddleware, HttpResponse
        )

    def test_no_matched_cookies(self):
        # No cookies
        http_response = get_test_http_response()
        request = self.factory.get("/")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies, SimpleCookie())
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(list(response.cookies.values()), [])

        # Add some cookies with their domains already set
        http_response = get_test_http_response(
            dict(key="a", value="a", domain=".example.org"),
            dict(key="b", value="b", domain=".example.co.uk"),
        )
        response = CookieDomainMiddleware(http_response)(request)
        self.assertCountEqual(
            list(response.cookies.values()), [response.cookies["a"], response.cookies["b"]]
        )
        self.assertEqual(response.cookies["a"]["domain"], ".example.org")
        self.assertEqual(response.cookies["b"]["domain"], ".example.co.uk")

    def test_matched_cookies(self):
        """Assert no new cookies introduced with multiple responses."""
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        request = self.factory.get("/")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(list(response.cookies.values()), [response.cookies["a"]])
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(list(response.cookies.values()), [response.cookies["a"]])

    @override_settings(ALLOWED_HOSTS=get_allowed_hosts("192.0.43.10"))
    def test_ip_address(self):
        """Assert IP addresses not be mutated."""
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        request = self.factory.get("/", host="192.0.43.10")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies["a"]["domain"], "")

    @override_settings(ALLOWED_HOSTS=get_allowed_hosts("localhost", "localhost.localdomain"))
    def test_localpath(self):
        """Assert local domains not mutated."""
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        request = self.factory.get("/", host="localhost")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies["a"]["domain"], "")
        # Even local subdomains
        request = self.factory.get("/", host="localhost.localdomain")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies["a"]["domain"], "")

    @override_settings(ALLOWED_HOSTS=get_allowed_hosts("ai", "www.ai"))
    def test_simple_tld(self):
        """Assert top-level domains are not mutated."""
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        request = self.factory.get("/", host="ai")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies["a"]["domain"], "")
        # Domains inside a TLD are OK
        request = self.factory.get("/", host="www.ai")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies["a"]["domain"], ".www.ai")

    @override_settings(ALLOWED_HOSTS=get_allowed_hosts("com.ai", "nic.com.ai"))
    def test_effective_tld(self):
        """Assert effective top-level domains with a webserver are
        not mutated.
        """
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        request = self.factory.get("/", host="com.ai")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies["a"]["domain"], "")
        # Domains within an effective TLD are OK
        request = self.factory.get("/", host="nic.com.ai")
        response = CookieDomainMiddleware(http_response)(request)
        self.assertEqual(response.cookies["a"]["domain"], ".nic.com.ai")

    @override_settings(MULTISITE_COOKIE_DOMAIN_DEPTH=1)
    def test_subdomain_depth(self):
        """Assert ignores top-level domains but not subdomains."""
        # At depth 1:
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        middleware = CookieDomainMiddleware(http_response)
        # Top-level domains are ignored
        request = self.factory.get("/", host="com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], "")
        # As are domains within a TLD
        request = self.factory.get("/", host="example.com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], "")
        # But subdomains will get matched
        request = self.factory.get("/", host="test.example.com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], ".test.example.com")
        # And sub-subdomains will get matched to 1 level deep
        response.cookies["a"]["domain"] = ""
        request = self.factory.get("/", host="app.test1.example.com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], ".test1.example.com")

    @override_settings(MULTISITE_COOKIE_DOMAIN_DEPTH=2)
    def test_subdomain_depth_2(self):
        """Assert at MULTISITE_COOKIE_DOMAIN_DEPTH 2, subdomains are
        matched two levels deep.
        """
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        middleware = CookieDomainMiddleware(http_response)
        request = self.factory.get("/", host="app.test2.example.com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], ".app.test2.example.com")
        response.cookies["a"]["domain"] = ""
        request = self.factory.get("/", host="new.app.test3.example.com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], ".app.test3.example.com")

    @override_settings(
        MULTISITE_COOKIE_DOMAIN_DEPTH=2, ALLOWED_HOSTS=get_allowed_hosts(".test.example.com")
    )
    def test_wildcard_subdomains(self):
        """Assert at MULTISITE_COOKIE_DOMAIN_DEPTH 2, subdomains are
        matched to two levels deep against the wildcard.
        """
        http_response = get_test_http_response(dict(key="a", value="a", domain=None))
        middleware = CookieDomainMiddleware(http_response)
        request = self.factory.get("/", host="foo.test.example.com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], ".foo.test.example.com")
        response.cookies["a"]["domain"] = ""
        request = self.factory.get("/", host="foo.bar.test.example.com")
        response = middleware(request)
        self.assertEqual(response.cookies["a"]["domain"], ".bar.test.example.com")
