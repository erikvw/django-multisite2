from typing import Callable

from django.http import HttpResponse


def get_test_http_response(*cookies) -> Callable:
    def http_response(request) -> HttpResponse:
        response = HttpResponse()
        for cookie in cookies:
            response.set_cookie(**cookie)
        return response

    return http_response
