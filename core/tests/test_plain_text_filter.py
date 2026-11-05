"""plain_text template filter: striptags + unescape, never mark_safe."""
from __future__ import annotations

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils.safestring import SafeData

from core.templatetags.core_tags import plain_text


class PlainTextFilterTests(SimpleTestCase):
    def test_named_entities_unescaped_tags_stripped(self):
        raw = (
            '<p>&laquo;Кобзар&raquo; &mdash; класика '
            'з <strong>золотим</strong> тисненням.</p>'
        )
        result = plain_text(raw)
        self.assertEqual(
            result,
            '«Кобзар» — класика з золотим тисненням.',
        )
        self.assertNotIn('<', result)
        self.assertNotIn('&laquo;', result)
        self.assertNotIn('&mdash;', result)
        self.assertNotIsInstance(result, SafeData)

    def test_double_encoded_entities(self):
        raw = '&amp;laquo;Текст&amp;raquo; &amp;mdash; далі'
        result = plain_text(raw)
        self.assertEqual(result, '«Текст» — далі')
        self.assertNotIsInstance(result, SafeData)

    def test_template_autoescape_keeps_ampersand_safe(self):
        tpl = Template(
            '{% load core_tags %}'
            '<div>{{ value|plain_text }}</div>'
        )
        html = tpl.render(Context({
            'value': '<b>&laquo;A&raquo; &amp; B</b>',
        }))
        self.assertIn('«A»', html)
        self.assertIn('&amp; B', html)
        self.assertNotIn('&amp;laquo;', html)
        self.assertNotIn('<b>', html)

    def test_empty_and_none(self):
        self.assertEqual(plain_text(''), '')
        self.assertEqual(plain_text(None), '')
