from unittest import TestCase

import jinja2

from docker_compose_templer.cli import JinjaRenderer


class TestJinjaRenderer(TestCase):
    sample_context = {'a': 'foo', 'b': 123.456, 'c': True, 'd': {'x': 1, 'y': 2, 'z': 3},
                      'e': ['my', 'very', 'own', 'context']}

    def test_render_string(self):
        # simple string without Jinja
        si = "Lorem ipsum dolor sit amet, ...   "
        so = si
        self.assertEqual(JinjaRenderer.render_string(si, self.sample_context), so)

        # simple string with Jinja
        si = "The height of {{ a }} is {{ b - d.x }}"
        so = "The height of foo is 122.456"
        self.assertEqual(JinjaRenderer.render_string(si, self.sample_context), so)

        # undefined variable
        self.assertRaises(jinja2.exceptions.UndefinedError, JinjaRenderer.render_string, si, {})

        # template error
        si = "{{ bar"
        self.assertRaises(jinja2.exceptions.TemplateError, JinjaRenderer.render_string, si, self.sample_context)

    def test_jinja_filter(self):
        # filter: mandatory
        from docker_compose_templer.jinja_filter import MandatoryError
        self.assertRaises(MandatoryError, JinjaRenderer.render_string, "{{ bar|mandatory() }}", {})

        # filter: regex_escape
        self.assertEqual(
            JinjaRenderer.render_string("{{ '[foo](bar)'|regex_escape() }}", {}),
            "\[foo\]\(bar\)"
        )

        # filter: regex_findall
        self.assertEqual(
            JinjaRenderer.render_string("{{ 'Lorem ipsum dolor sit amet'|regex_findall('[ae]m') }}", {}),
            "['em', 'am']"
        )

        # filter: regex_replace
        self.assertEqual(
            JinjaRenderer.render_string("{{ 'foobar'|regex_replace('^foo', 'Cocktail') }}", {}),
            'Cocktailbar'
        )

        # filter: regex_search
        self.assertEqual(
            JinjaRenderer.render_string("{{ 'Lorem ipsum dolor sit amet'|regex_search('ip(\S+)') }}", {}),
            "ipsum"
        )
        self.assertEqual(
            JinjaRenderer.render_string(r"{{ 'Lorem ipsum dolor sit amet'|regex_search('ip(\S+)', '\\1') }}", {}),
            "['sum']"
        )

        # filter: regex_contains
        self.assertEqual(
            JinjaRenderer.render_string("{{ 'foobar'|regex_contains('^foo[bB]ar$') }}", {}),
            'True'
        )
        self.assertEqual(
            JinjaRenderer.render_string("{{ 'foobar'|regex_contains('barfoo') }}", {}),
            'False'
        )

        # filter: to_yaml
        #print("|{}|".format(JinjaRenderer.render_string("{{ c|to_yaml }}", {'c': self.sample_context})))
        self.assertEqual(
            JinjaRenderer.render_string("{{ c|to_yaml }}", {'c': self.sample_context}),
            'a: foo\nb: 123.456\nc: true\nd:\n  x: 1\n  y: 2\n  z: 3\ne:\n  - my\n  - very\n  - own\n  - context\n'
        )

        # filter: to_json
        #print("|{}|".format(JinjaRenderer.render_string("{{ c|to_json }}", {'c': self.sample_context})))
        self.assertEqual(
            JinjaRenderer.render_string("{{ c|to_json }}", {'c': self.sample_context}),
            '{"a": "foo", "b": 123.456, "c": true, "d": {"x": 1, "y": 2, "z": 3}, "e": ["my", "very", "own", "context"]}'
        )

        # filter: to_nice_json
        #print("|{}|".format(JinjaRenderer.render_string("{{ c|to_nice_json }}", {'c': self.sample_context})))
        self.assertEqual(
            JinjaRenderer.render_string("{{ c|to_nice_json }}", {'c': self.sample_context}),
            '{\n    "a": "foo",\n    "b": 123.456,\n    "c": true,\n    "d": {\n        "x": 1,\n        "y": 2,\n        "z": 3\n    },\n    "e": [\n        "my",\n        "very",\n        "own",\n        "context"\n    ]\n}'
        )

    def test_evaluate_string(self):
        # str
        self.assertIsInstance(JinjaRenderer._evaluate_string(' abc '), str)

        # bool
        self.assertIsInstance(JinjaRenderer._evaluate_string(' n '), bool)
        self.assertIsInstance(JinjaRenderer._evaluate_string(' yes '), bool)
        self.assertIsInstance(JinjaRenderer._evaluate_string(' True '), bool)

        # int
        self.assertIsInstance(JinjaRenderer._evaluate_string(' 99 '), int)

        # float
        self.assertIsInstance(JinjaRenderer._evaluate_string(' 1.2 '), float)

        # list
        self.assertIsInstance(JinjaRenderer._evaluate_string(' [1,2,3] '), list)

        # dict
        self.assertIsInstance(JinjaRenderer._evaluate_string(' {"a": 1} '), dict)

    def test_render_dict_and_add_to_context(self):
        d = {'a': '{{ e[0] }}', 'c': '{{ 2 == 1 }}', 'f': '{{ "1.2" }}'}
        self.assertEqual(
            JinjaRenderer.render_dict_and_add_to_context(d, self.sample_context),
            {'a': 'my', 'b': 123.456, 'c': False, 'd': {'x': 1, 'y': 2, 'z': 3},
             'e': ['my', 'very', 'own', 'context'], 'f': 1.2, 'omit': JinjaRenderer.omit_placeholder}
        )

    def test_remove_omit_from_dict(self):
        d = { 'a': 'x', 'b': JinjaRenderer.omit_placeholder, 'c': {'d': 'y', 'e': JinjaRenderer.omit_placeholder}, 'f': [1, JinjaRenderer.omit_placeholder, 3, 4]}
        #d = { 'f': [1, JinjaRenderer.omit_placeholder, 3, 4]}
        self.assertEqual(
            JinjaRenderer.remove_omit_from_dict(d),
            {'a': 'x', 'c': {'d': 'y'}, 'f': [1, 3, 4]}
        )
