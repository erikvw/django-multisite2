#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

import django

if __name__ == "__main__":
    os.environ["DJANGO_SETTINGS_MODULE"] = "multisite.tests.test_settings"
    django.setup()
    from django.test.runner import DiscoverRunner

    tags = [t.split("=")[1] for t in sys.argv if t.startswith("--tag")]
    failfast = any([True for t in sys.argv if t.startswith("--failfast")])
    keepdb = any([True for t in sys.argv if t.startswith("--keepdb")])
    opts = dict(failfast=failfast, tags=tags, keepdb=keepdb)
    failures = DiscoverRunner(**opts).run_tests(["multisite.tests.tests"], **opts)
    sys.exit(failures)
