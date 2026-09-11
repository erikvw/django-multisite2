import warnings
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.checks.registry import registry
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.utils import timezone

from multisite import SiteID
from multisite.exceptions import MultisiteTimezoneError
from multisite.middleware import DynamicSiteMiddleware, DynamicSiteTimezoneMiddleware
from multisite.system_checks import (
    DYNAMIC_SITE_MIDDLEWARE,
    DYNAMIC_SITE_TIMEZONE_MIDDLEWARE,
    multisite_middleware_check,
    multisite_timezone_setting_check,
)
from multisite.utils import get_multisite_timezone

from ..get_test_allowed_hosts import get_test_allowed_hosts
from .request_factory import RequestFactory

DAR = "Africa/Dar_es_Salaam"
NYC = "America/New_York"


class ViewSpy:
    """A `get_response` callable that records the timezone that was
    active when it was called.
    """

    def __init__(self, exc: Exception | None = None):
        self.exc = exc
        self.timezone_name: str | None = None
        self.call_count = 0

    def __call__(self, request):
        self.call_count += 1
        self.timezone_name = timezone.get_current_timezone_name()
        if self.exc:
            raise self.exc
        return HttpResponse()


middleware_with_tz = [
    "multisite.middleware.DynamicSiteMiddleware",
    "multisite.middleware.DynamicSiteTimezoneMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
]


class GetMultisiteTimezoneTest(TestCase):
    def tearDown(self):
        if isinstance(settings.SITE_ID, SiteID):
            settings.SITE_ID.reset()
        timezone.deactivate()
        super().tearDown()

    @override_settings(SITE_ID=SiteID(default=1))
    def test_raises_if_setting_not_defined(self):
        with self.assertRaises(MultisiteTimezoneError) as cm:
            get_multisite_timezone()
        self.assertIn("Middleware needed for function", str(cm.exception))

    @override_settings(SITE_ID=SiteID(default=1), MULTISITE_TIME_ZONES={})
    def test_raises_if_setting_empty(self):
        with self.assertRaises(MultisiteTimezoneError) as cm:
            get_multisite_timezone()
        self.assertIn("Middleware needed for function", str(cm.exception))

    @override_settings(
        SITE_ID=SiteID(default=99),
        MULTISITE_TIME_ZONES={1: DAR},
        MIDDLEWARE=middleware_with_tz,
    )
    def test_raises_if_current_site_not_a_key(self):
        with self.assertRaises(MultisiteTimezoneError) as cm:
            get_multisite_timezone(99)
        self.assertIn("missing timezone for site_id", str(cm.exception))

    @override_settings(
        SITE_ID=SiteID(default=1), MULTISITE_TIME_ZONES={1: DAR}, MIDDLEWARE=middleware_with_tz
    )
    def test_returns_timezone_for_current_site(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            self.assertEqual(get_multisite_timezone(), DAR)

    @override_settings(
        SITE_ID=SiteID(default=1),
        MULTISITE_TIME_ZONES={1: DAR, 2: NYC},
        MIDDLEWARE=middleware_with_tz,
    )
    def test_follows_site_id(self):
        """The lookup is dynamic. A SiteID key matches an int key."""
        self.assertEqual(get_multisite_timezone(), DAR)
        settings.SITE_ID.set(2)
        self.assertEqual(get_multisite_timezone(), NYC)
        settings.SITE_ID.reset()
        self.assertEqual(get_multisite_timezone(), DAR)

    @override_settings(
        SITE_ID=SiteID(default=1),
        MULTISITE_TIME_ZONES={1: DAR, 2: NYC},
        MIDDLEWARE=middleware_with_tz,
    )
    def test_follows_site_id_override(self):
        with settings.SITE_ID.override(2):
            self.assertEqual(get_multisite_timezone(), NYC)
        self.assertEqual(get_multisite_timezone(), DAR)

    @override_settings(
        SITE_ID=SiteID(default=1), MULTISITE_TIME_ZONES={1: DAR}, MIDDLEWARE=middleware_with_tz
    )
    def test_return_value_is_accepted_by_zoneinfo(self):
        """Callers pass the result straight to ZoneInfo()."""
        self.assertEqual(ZoneInfo(get_multisite_timezone()), ZoneInfo(DAR))

    @override_settings(
        SITE_ID=SiteID(default=1), MULTISITE_TIME_ZONES={1: DAR}, MIDDLEWARE=middleware_with_tz
    )
    def test_returns_str_for_a_str_value(self):
        self.assertIsInstance(get_multisite_timezone(), str)

    @override_settings(
        SITE_ID=SiteID(default=99),
        MULTISITE_TIME_ZONES={1: ZoneInfo(DAR)},
        MIDDLEWARE=middleware_with_tz,
    )
    def test_returns_str_when_falling_back(self):
        time_zone = get_multisite_timezone()
        self.assertIsInstance(time_zone, str)
        self.assertEqual(time_zone, settings.TIME_ZONE)


@override_settings(
    SITE_ID=SiteID(default=1),
    MULTISITE_TIME_ZONES={1: DAR, 2: NYC},
    MIDDLEWARE=middleware_with_tz,
)
class DynamicSiteTimezoneMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory(host="example.com")
        timezone.deactivate()

    def tearDown(self):
        if isinstance(settings.SITE_ID, SiteID):
            settings.SITE_ID.reset()
        timezone.deactivate()
        super().tearDown()

    def test_activates_site_timezone_for_the_request(self):
        view = ViewSpy()
        self.assertEqual(
            DynamicSiteTimezoneMiddleware(view)(self.factory.get("/")).status_code, 200
        )
        self.assertEqual(view.timezone_name, DAR)

    def test_deactivates_after_the_request(self):
        DynamicSiteTimezoneMiddleware(ViewSpy())(self.factory.get("/"))
        self.assertEqual(timezone.get_current_timezone_name(), settings.TIME_ZONE)

    def test_deactivates_if_the_view_raises(self):
        """Threads are reused from the pool, so the timezone must not
        leak out of a failed request.
        """
        view = ViewSpy(exc=ValueError("boom"))
        with self.assertRaises(ValueError):
            DynamicSiteTimezoneMiddleware(view)(self.factory.get("/"))
        self.assertEqual(view.timezone_name, DAR)
        self.assertEqual(timezone.get_current_timezone_name(), settings.TIME_ZONE)

    def test_follows_site_id_between_requests(self):
        middleware = DynamicSiteTimezoneMiddleware(view := ViewSpy())
        middleware(self.factory.get("/"))
        self.assertEqual(view.timezone_name, DAR)
        settings.SITE_ID.set(2)
        middleware(self.factory.get("/"))
        self.assertEqual(view.timezone_name, NYC)

    @override_settings(SITE_ID=SiteID(default=99))
    def test_falls_back_to_settings_time_zone_for_unconfigured_site(self):
        view = ViewSpy()
        DynamicSiteTimezoneMiddleware(view)(self.factory.get("/"))
        self.assertEqual(view.timezone_name, settings.TIME_ZONE)


@override_settings(
    ROOT_URLCONF="multisite_app.urls",
    SITE_ID=SiteID(default=0),
    CACHE_MULTISITE_ALIAS="multisite",
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
        "multisite": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    },
    MULTISITE_FALLBACK=None,
    ALLOWED_HOSTS=get_test_allowed_hosts("example.com", "anothersite.example", replace=True),
    MULTISITE_TIME_ZONES={1: DAR, 2: NYC},
    MIDDLEWARE=middleware_with_tz,
)
class DynamicSiteTimezoneMiddlewareOrderTest(TestCase):
    """DynamicSiteTimezoneMiddleware must be listed AFTER
    DynamicSiteMiddleware, which is what resolves SITE_ID.
    """

    def setUp(self):
        Site.objects.all().delete()
        self.site = Site.objects.create(pk=1, domain="example.com")
        self.site2 = Site.objects.create(pk=2, domain="anothersite.example")
        timezone.deactivate()

    def tearDown(self):
        if isinstance(settings.SITE_ID, SiteID):
            settings.SITE_ID.reset()
        timezone.deactivate()
        super().tearDown()

    def test_host_determines_the_activated_timezone(self):
        for host, expected in [("example.com", DAR), ("anothersite.example", NYC)]:
            with self.subTest(host=host):
                view = ViewSpy()
                chain = DynamicSiteMiddleware(DynamicSiteTimezoneMiddleware(view))
                self.assertEqual(chain(RequestFactory(host=host).get("/")).status_code, 200)
                self.assertEqual(view.timezone_name, expected)

    def test_wrong_order_cannot_resolve_the_site(self):
        """Listed first, it runs before SITE_ID has been resolved and
        falls back to settings.TIME_ZONE.
        """
        view = ViewSpy()
        chain = DynamicSiteTimezoneMiddleware(DynamicSiteMiddleware(view))
        # with self.assertWarns(RuntimeWarning) as cm:
        chain(RequestFactory(host="anothersite.example").get("/"))
        # self.assertIn("missing timezone for site 0", str(cm.warning))
        self.assertEqual(view.timezone_name, settings.TIME_ZONE)


class MultisiteMiddlewareCheckTest(TestCase):
    """Tests for `multisite_middleware_check` (order) and
    `multisite_timezone_setting_check` (setting has an effect).
    """

    @staticmethod
    def ids(messages):
        return [m.id for m in messages]

    @override_settings(MIDDLEWARE=[DYNAMIC_SITE_MIDDLEWARE, DYNAMIC_SITE_TIMEZONE_MIDDLEWARE])
    def test_correct_order_is_silent(self):
        self.assertEqual(multisite_middleware_check(None), [])

    @override_settings(
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
            DYNAMIC_SITE_MIDDLEWARE,
            "django.contrib.sites.middleware.CurrentSiteMiddleware",
            DYNAMIC_SITE_TIMEZONE_MIDDLEWARE,
        ]
    )
    def test_correct_order_is_silent_when_not_adjacent(self):
        self.assertEqual(multisite_middleware_check(None), [])

    @override_settings(MIDDLEWARE=[DYNAMIC_SITE_TIMEZONE_MIDDLEWARE, DYNAMIC_SITE_MIDDLEWARE])
    def test_wrong_order_raises_error(self):
        messages = multisite_middleware_check(None)
        self.assertEqual(self.ids(messages), ["multisite.E001"])
        self.assertIn("must be listed after", messages[0].msg)

    @override_settings(MIDDLEWARE=[DYNAMIC_SITE_TIMEZONE_MIDDLEWARE])
    def test_timezone_middleware_without_dynamic_site_middleware_error(self):
        messages = multisite_middleware_check(None)
        self.assertEqual(self.ids(messages), ["multisite.E003"])

    @override_settings(MIDDLEWARE=[DYNAMIC_SITE_MIDDLEWARE])
    def test_silent_if_timezone_middleware_not_used(self):
        self.assertEqual(multisite_middleware_check(None), [])

    @override_settings(MIDDLEWARE=[])
    def test_silent_if_no_middleware(self):
        self.assertEqual(multisite_middleware_check(None), [])

    @override_settings(
        MIDDLEWARE=[DYNAMIC_SITE_MIDDLEWARE, DYNAMIC_SITE_TIMEZONE_MIDDLEWARE],
        MULTISITE_TIME_ZONES={1: DAR},
    )
    def test_setting_check_silent_when_middleware_installed(self):
        self.assertEqual(multisite_timezone_setting_check(None), [])

    @override_settings(MIDDLEWARE=[DYNAMIC_SITE_MIDDLEWARE], MULTISITE_TIME_ZONES={})
    def test_setting_check_silent_when_setting_empty(self):
        self.assertEqual(multisite_timezone_setting_check(None), [])

    def test_checks_are_registered(self):
        registered = [c.__name__ for c in registry.get_checks()]
        self.assertIn("multisite_middleware_check", registered)
        registered_deploy = [
            c.__name__ for c in registry.get_checks(include_deployment_checks=True)
        ]
        self.assertIn("multisite_timezone_setting_check", registered_deploy)
