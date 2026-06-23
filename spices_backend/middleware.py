"""Request-language activation for django-modeltranslation.

The storefront has no URL-prefixed locales; instead the frontend sends the
active language as a `?lang=` query param (or an `X-Language` header). This
middleware activates that language for the request so modeltranslation returns
the matching translated columns (with English fallback). Unknown/blank values
leave the default language active.
"""
from django.conf import settings
from django.utils import translation

_VALID_LANGUAGES = {code for code, _ in settings.LANGUAGES}


class LanguageQueryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = (request.GET.get('lang') or request.headers.get('X-Language') or '').strip().lower()
        activated = False
        if lang in _VALID_LANGUAGES:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
            activated = True
        try:
            return self.get_response(request)
        finally:
            if activated:
                translation.deactivate()
