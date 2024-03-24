from __future__ import annotations

import tempfile

import tldextract
from django.conf import settings

__all__ = ["CookieDomainMiddleware"]

from multisite.exceptions import MultisiteCookieDomainDepthError


def get_cookie_domain_depth():
    return getattr(settings, "MULTISITE_COOKIE_DOMAIN_DEPTH", 0)


def get_public_suffix_list_cache_dir():
    return getattr(settings, "MULTISITE_PUBLIC_SUFFIX_LIST_CACHE_DIR", None)


class CookieDomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self.depth = int(get_cookie_domain_depth())
        except ValueError:
            raise MultisiteCookieDomainDepthError(
                f"Invalid MULTISITE_COOKIE_DOMAIN_DEPTH. Got {get_cookie_domain_depth()}"
            )
        if self.depth < 0:
            raise MultisiteCookieDomainDepthError(
                f"Invalid MULTISITE_COOKIE_DOMAIN_DEPTH. Got {get_cookie_domain_depth()}"
            )
        self.psl_cache_dir = get_public_suffix_list_cache_dir()
        if self.psl_cache_dir is None:
            self.psl_cache_dir = tempfile.gettempdir()
        self._tldextract = None

    def __call__(self, request):
        response = self.get_response(request)
        matched = self.match_cookies(response)
        if not matched:
            return response  # No cookies to edit

        parsed = self.tldextract(request.get_host())
        if not parsed.suffix:
            return response  # IP address or local path
        if not parsed.domain:
            return response  # Only TLD

        subdomains = parsed.subdomain.split(".") if parsed.subdomain else []
        if not self.depth:
            subdomains = [""]
        elif len(subdomains) < self.depth:
            return response  # Not enough subdomain parts
        else:
            subdomains = [""] + subdomains[-self.depth :]

        domain = ".".join(subdomains + [parsed.domain, parsed.suffix])

        for morsel in matched:
            morsel["domain"] = domain
        return response

    def tldextract(self, url):
        if self._tldextract is None:
            self._tldextract = tldextract.TLDExtract(cache_dir=self.psl_cache_dir)
        return self._tldextract(url)

    @staticmethod
    def match_cookies(response):
        return [c for c in response.cookies.values() if not c["domain"]]
