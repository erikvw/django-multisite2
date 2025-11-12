from django_multisite2 import SiteID

SILENCED_SYSTEM_CHECKS = ["sites.E101"]
SECRET_KEY = "iufoj=mibkpdz*%bob952x(%49rqgv8gg45k36kjcg76&-y5=!"  # nosec B105
SITE_ID = SiteID(default=1)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    # "django.contrib.auth",
    # "django.contrib.contenttypes",
    "django.contrib.sites",
    "django_multisite2",
    "multisite_app",
]
MIDDLEWARE = [
    "django_multisite2.middleware.DynamicSiteMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
]
