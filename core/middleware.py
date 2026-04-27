from django.conf import settings
from django.utils import translation


class LanguageGuardMiddleware:
    """
    Ensures that only languages enabled in SiteSettings remain active.
    Must be placed after django.middleware.locale.LocaleMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = translation.get_language()
        needs_reset = False

        if lang and lang != settings.LANGUAGE_CODE:
            try:
                from core.models import SiteSettings  # noqa: PLC0415  (avoid circular import at module level)
                site = SiteSettings.objects.first()
                if site:
                    disabled = (lang == 'ru' and not site.enable_ru) or \
                               (lang == 'en' and not site.enable_en)
                    if disabled:
                        translation.activate(settings.LANGUAGE_CODE)
                        request.LANGUAGE_CODE = settings.LANGUAGE_CODE
                        needs_reset = True
            except Exception:
                pass

        response = self.get_response(request)

        if needs_reset:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                settings.LANGUAGE_CODE,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
                secure=getattr(settings, 'LANGUAGE_COOKIE_SECURE', False),
                httponly=getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
            )

        return response
