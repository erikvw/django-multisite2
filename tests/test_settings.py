import os

from multisite import SiteID

SILENCED_SYSTEM_CHECKS = ["sites.E101"]
SECRET_KEY = "iufoj=mibkpdz*%bob952x(%49rqgv8gg45k36kjcg76&-y5=!"  # nosec B105
SITE_ID = SiteID(default=1)

# Defaults to sqlite so `runtests.py` needs no setup. CI sets
# DATABASE_ENGINE per matrix leg so that mysql and postgres are
# actually exercised. sqlite cannot distinguish an integer from a
# boolean, so it hides backend-specific type errors.
DATABASE_ENGINE = os.environ.get("DATABASE_ENGINE", "sqlite")

if DATABASE_ENGINE == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "postgres"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
elif DATABASE_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("MYSQL_DATABASE", "mysql"),
            "USER": os.environ.get("MYSQL_USER", "root"),
            "PASSWORD": os.environ.get("MYSQL_PASSWORD", "mysql"),
            "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.environ.get("MYSQL_PORT", "3306"),
        }
    }
else:
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
    "multisite",
    "multisite_app",
]
MIDDLEWARE = [
    "multisite.middleware.DynamicSiteMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
]
