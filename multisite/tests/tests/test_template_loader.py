import logging
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase


class UpdatePublicSuffixListCommandTestCase(TestCase):
    def setUp(self):
        self.cache_dir = tempfile.gettempdir()
        # save the tldextract logger output to a buffer to test output
        self.out = StringIO()
        self.logger = logging.getLogger("tldextract")
        self.logger.setLevel(logging.DEBUG)
        stdout_handler = logging.StreamHandler(self.out)
        stdout_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(stdout_handler)

        # patch tldextract to avoid actual requests
        self.patcher = mock.patch("tldextract.TLDExtract")
        self.tldextract = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def tldextract_update_side_effect(self, *args, **kwargs):
        self.logger.debug("TLDExtract.update called")

    def test_command(self):
        call_command("update_public_suffix_list")
        expected_calls = [
            mock.call(cache_dir=self.cache_dir),
            mock.call().update(fetch_now=True),
        ]
        self.assertEqual(self.tldextract.mock_calls, expected_calls)

    def test_command_output(self):
        # make sure that the logger receives output from the method
        self.tldextract().update.side_effect = self.tldextract_update_side_effect

        call_command("update_public_suffix_list", verbosity=3)
        update_message = "Updating {}".format(self.cache_dir)
        self.assertIn(update_message, self.out.getvalue())
        self.assertIn("TLDExtract.update called", self.out.getvalue())
