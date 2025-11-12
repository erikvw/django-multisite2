|pypi| |actions| |codecov| |downloads| |uv| |ruff|



django_multisite2
=================

With ``django_multisite2`` a single instance of a Django project can serve multiple sites using a single settings file (multi-tenant). The current ``SITE_ID`` is extracted from the URL.

In ``settings``, the static ``SITE_ID`` is replaced with ``django_multisite2`` dynamic ``SiteID``::

    # settings.py
    SITE_ID = SiteID(default=1)

the dynamic ``SiteID`` behaves like an integer. When combined with ``django_multisite2`` middleware, ``SiteID`` will return the current ``SITE_ID`` based on the url. For example, each url below is an alias of the same server instance. With ``django_multisite2`` you might have something like this::

    # https://harare.example.com
    >>> from django.conf import settings
    >>> settings.SITE_ID
    10

    # https://kampala.example.com
    >>> from django.conf import settings
    >>> settings.SITE_ID
    20


Python 3.11+ Django 4.2+. New releases are cut from the ``main`` branch.

Older versions of Django are supported by the original `django-multisite`_ project.

Important:
    Starting with version 3.0.0, the module will be renamed from ``multisite`` to ``django_multisite2``. To use version 3.0.0+, update your settings INSTALLED_APPS, MIDDLEWARE, CACHES and update any import paths.

Installation
============

Install with pip:

.. code-block::

    pip install django-multisite2


Replace your ``SITE_ID`` in ``settings.py`` to:

.. code-block::

    from django_multisite2 import SiteID
    SITE_ID = SiteID(default=1)


add to INSTALLED_APPS:

.. code-block::

    INSTALLED_APPS = [
        ...
        'django.contrib.sites',
        'django_multisite2',
        ...
    ]


Edit settings.py MIDDLEWARE:

.. code-block::

    MIDDLEWARE = (
        ...
        'django_multisite2.middleware.DynamicSiteMiddleware',
        ...
    )


Using a custom cache
--------------------
Append to settings.py, in order to use a custom cache that can be
safely cleared::

    # The cache connection to use for django-multisite2.
    # Default: 'default'
    CACHE_MULTISITE_ALIAS = 'django_multisite2'

    # The cache key prefix that django-multisite2 should use.
    # If not set, defaults to the KEY_PREFIX used in the defined
    # CACHE_MULTISITE_ALIAS or the default cache (empty string if not set)
    CACHE_MULTISITE_KEY_PREFIX = ''

If you have set CACHE\_MULTISITE\_ALIAS to a custom value, *e.g.*
``'django_multisite2'``, add a separate backend to settings.py CACHES::

    CACHES = {
        'default': {
            ...
        },
        'django_multisite2': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'TIMEOUT': 60 * 60 * 24,  # 24 hours
            ...
        },
    }


Domain fallbacks
----------------

By default, if the domain name is unknown, django_multisite2 will respond with
an HTTP 404 Not Found error. To change this behaviour, add to
settings.py::

    # The view function or class-based view that django-multisite2 will
    # use when it cannot match the hostname with a Site. This can be
    # the name of the function or the function itself.
    # Default: None
    MULTISITE_FALLBACK = 'django.views.generic.base.RedirectView

    # Keyword arguments for the MULTISITE_FALLBACK view.
    # Default: {}
    MULTISITE_FALLBACK_KWARGS = {'url': 'http://example.com/',
                                 'permanent': False}

Templates
---------

This feature has been removed in version 2.0.0.

If required, create template subdirectories for domain level templates (in a
location specified in settings.TEMPLATES['DIRS'].

Multisite's template loader will look for templates in folders with the names of
domains, such as::

    templates/example.com


The template loader will also look for templates in a folder specified by the
optional MULTISITE_DEFAULT_TEMPLATE_DIR setting, e.g.::

    templates/multisite_templates


Cross-domain cookie support
---------------------------

In order to support `cross-domain cookies`_ , for purposes like single-sign-on, prepend the following to the top of
settings.py MIDDLEWARE (MIDDLEWARE_CLASSES for Django < 1.10)::

    MIDDLEWARE = (
        'django_multisite2.middleware.CookieDomainMiddleware',
        ...
    )

CookieDomainMiddleware will consult the `Public Suffix List`_
for effective top-level domains.
It caches this file
in the system's default temporary directory
as ``effective_tld_names.dat``.
To change this in settings.py::

    MULTISITE_PUBLIC_SUFFIX_LIST_CACHE = '/path/to/multisite_tld.dat'

By default,
any cookies without a domain set
will be reset to allow \*.domain.tld.
To change this in settings.py::

    MULTISITE_COOKIE_DOMAIN_DEPTH = 1  # Allow only *.subdomain.domain.tld

In order to fetch a new version of the list,
run::

    manage.py update_public_suffix_list


Post-migrate signal: post_migrate_sync_alias
--------------------------------------------
The ``post-migrate`` signal ``post_migrate_sync_alias`` is registered in the ``apps.py``. ``post_migrate_sync_alias``
ensures the ``domain`` in django_multisite2's ``Alias`` model is updated to match that of django's ``Site`` model. This signal must
run AFTER any ``post-migrate`` signals that manipulate Django's ``Site`` model. If you have an app that manipulates Django's
``Site`` model, place it before ``django_multisite2`` in `settings. INSTALLED_APPS`. If this is not possible, you may configure ``django_multisite2``
to not connect the ``post-migrate`` signal in ``apps.py`` so that you can do it somewhere else in your code.

To configure `django_multisite2` to not connect the `post-post_migrate_sync_alias` in the `apps.py`, update your settings::

    MULTISITE_REGISTER_POST_MIGRATE_SYNC_ALIAS = False

With the `settings` attribute set to `False`, it is your responsibility to connect the signal in your code. Note that if you do not sync the `Alias` and `Site`
models after the `Site` model has changed, django_multisite2 may not recognize the domain and switch to the fallback view or
raise a `Http404` error.

Development Environments
------------------------
Multisite returns a valid Alias when in "development mode" (defaulting to the
alias associated with the default SiteID.

Development mode is either:
    - Running tests, i.e. manage.py test
    - Running locally in settings.DEBUG = True, where the hostname is a top-level name, i.e. localhost

In order to have django_multisite2 use aliases in local environments, add entries to
your local etc/hosts file to match aliases in your applications.  E.g. ::

    127.0.0.1 example.com
    127.0.0.1 examplealias.com

And access your application at example.com:8000 or examplealias.com:8000 instead of
the usual localhost:8000.

Tests
-----

To run the tests:

.. code-block:: bash

    uv run runtests.py

or

.. code-block:: bash

    uv run tox

.. _django-multisite: https://github.com/ecometrica/django-multisite
.. _cross-domain cookies: http://en.wikipedia.org/wiki/HTTP_cookie#Domain_and_Path
.. _Public Suffix List: http://publicsuffix.org/

.. |pypi| image:: https://img.shields.io/pypi/v/django-multisite2.svg
  :target: https://pypi.python.org/pypi/django-multisite2

.. |actions| image:: https://github.com/erikvw/django-multisite2/actions/workflows/build.yml/badge.svg
  :target: https://github.com/erikvw/django-multisite2/actions/workflows/build.yml

.. |codecov| image:: https://codecov.io/gh/erikvw/django-multisite2/branch/develop/graph/badge.svg
  :target: https://codecov.io/gh/erikvw/django-multisite2

.. |downloads| image:: https://pepy.tech/badge/django-multisite2
   :target: https://pepy.tech/project/django-multisite2

.. |uv| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
  :target: https://github.com/astral-sh/uv

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Ruff
