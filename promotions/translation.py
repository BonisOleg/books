from modeltranslation.translator import TranslationOptions, register

from .models import GiftPickerOption, GiftPickerQuestion, Promotion


@register(Promotion)
class PromotionTranslationOptions(TranslationOptions):
    fields = ('title', 'description')


@register(GiftPickerQuestion)
class GiftPickerQuestionTranslationOptions(TranslationOptions):
    fields = ('text',)


@register(GiftPickerOption)
class GiftPickerOptionTranslationOptions(TranslationOptions):
    fields = ('text',)
