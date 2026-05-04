from django.db import OperationalError, ProgrammingError


def _active_lang_codes():
    """
    Reads SiteSettings once per request call.
    Returns set of active language codes; 'uk' is always included.
    Falls back to all three languages if DB is unavailable (migrations, first deploy).
    """
    try:
        from core.models import SiteSettings
        row = SiteSettings.objects.values('enable_en', 'enable_ru').first()
        if not row:
            return {'uk'}
        codes = {'uk'}
        if row['enable_en']:
            codes.add('en')
        if row['enable_ru']:
            codes.add('ru')
        return codes
    except (OperationalError, ProgrammingError):
        return {'uk', 'en', 'ru'}


_LANG_PANEL_CLASSES = frozenset({'lang-uk', 'lang-en', 'lang-ru'})


class LangFilteredFieldsets:
    """
    Mixin for TranslationAdmin subclasses.

    Hides language fieldset panels whose language is disabled in SiteSettings.
    Language panels are detected by 'lang-uk', 'lang-en', 'lang-ru' CSS classes.
    Ukrainian is always visible regardless of settings.
    """

    def get_fieldsets(self, request, obj=None):
        active = _active_lang_codes()
        result = []
        for name, opts in super().get_fieldsets(request, obj):
            classes = set(opts.get('classes', ()))
            panel_langs = classes & _LANG_PANEL_CLASSES
            if panel_langs:
                # strip 'lang-' prefix (always 5 chars)
                lang_code = next(iter(panel_langs))[5:]
                if lang_code not in active:
                    continue
            result.append((name, opts))
        return result
