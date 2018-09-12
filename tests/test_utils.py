from unittest import TestCase

from _ruamel_yaml import YAMLError

from docker_compose_templer.cli import Utils

class TestUtils(TestCase):
    def test_merge_dicts(self):
        d1 = {'a': 'foo', 'b': 123.456, 'c': True, 'd': {'x': 1, 'y': 2, 'z': 3},
                               'e': ['my', 'very', 'own', 'context']}
        d2 = {'a': 'bar', 'd': {'x': 0.99, 'zz': {}},
                               'e': ['new', 'list']}
        r  = {'a': 'bar', 'b': 123.456, 'c': True, 'd': {'x': 0.99, 'y': 2, 'z': 3, 'zz': {}}, 'e': ['new', 'list']}
        self.assertEqual(Utils.merge_dicts(d1, d2), r)

    def test_load_yaml(self):
        self.assertEqual(
            Utils.load_yaml(
                'a: foo\nb: 123.456\nc: true\nd:\n  x: 1\n  y: 2\n  z: 3\ne:\n  - my\n  - very\n  - own\n  - context\n'
            ),
            {'a': 'foo', 'b': 123.456, 'c': True, 'd': {'x': 1, 'y': 2, 'z': 3},
             'e': ['my', 'very', 'own', 'context']}
        )
        self.assertRaises(YAMLError, Utils.load_yaml, '  :wrong\na: foo\n')