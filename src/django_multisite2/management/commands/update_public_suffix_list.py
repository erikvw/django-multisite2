from __future__ import absolute_import, print_function, unicode_literals

import logging
import tempfile

import tldextract
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, **options):
        self.setup_logging(verbosity=options.get("verbosity", 1))

        cache_dir = getattr(
            settings, "MULTISITE_PUBLIC_SUFFIX_LIST_CACHE_DIR", tempfile.gettempdir()
        )
        self.log("Updating {cache_dir}".format(cache_dir=cache_dir))

        extract = tldextract.TLDExtract(cache_dir=cache_dir)
        extract.update(fetch_now=True)
        self.log("Done.")

    def setup_logging(self, verbosity):
        self.verbosity = int(verbosity)

        # Connect to tldextract's logger
        self.logger = logging.getLogger("tldextract")
        if self.verbosity < 2:
            self.logger.setLevel(logging.CRITICAL)

    def log(self, msg):
        self.logger.info(msg)
