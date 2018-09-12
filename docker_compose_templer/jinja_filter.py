""" Custom Jinja2 filters """
import json
import re
from distutils.util import strtobool

import ruamel.yaml as yaml
from jinja2 import StrictUndefined, UndefinedError


class MandatoryError(UndefinedError):
    def __init__(self, message):
        super().__init__(message)


def mandatory(value, error_message=u''):
    """Raise an 'UndefinedError' with an custom error massage, when value is undefined"""
    if type(value) is StrictUndefined:
        raise MandatoryError(str(error_message))

    return value


def regex_escape(string):
    """Escape special characters in a string so it can be used in regular expressions"""
    return re.escape(string)


def regex_findall(value, pattern, replacement, ignorecase=False, multiline=False):
    """Do a regex findall on 'value'"""
    flags = 0
    if ignorecase:
        flags |= re.I
    if multiline:
        flags |= re.M
    compiled_pattern = re.compile(pattern, flags=flags)
    return compiled_pattern.findall(str(value))


def regex_replace(value, pattern, replacement, ignorecase=False, multiline=False):
    """Do a regex search and replace on 'value'"""
    flags = 0
    if ignorecase:
        flags |= re.I
    if multiline:
        flags |= re.M
    compiled_pattern = re.compile(pattern, flags=flags)
    return compiled_pattern.sub(replacement, str(value))


def regex_search(value, pattern, *args, **kwargs):
    """Do a regex search on 'value'"""
    groups = []
    for arg in args:
        match = re.match(r'\\(\d+)', arg)
        if match:
            groups.append(int(match.group(1)))
            continue

        match = re.match(r'^\\g<(\S+)>', arg)
        if match:
            groups.append(match.group(1))
            continue

        raise Exception("Unknown argument: '{}'".format(str(arg)))

    flags = 0
    if kwargs.get('ignorecase'):
        flags |= re.I
    if kwargs.get('multiline'):
        flags |= re.M
    compiled_pattern = re.compile(pattern, flags=flags)
    match = re.search(compiled_pattern, str(value))

    if match:
        if not groups:
            return match.group()
        else:
            items = []
            for item in groups:
                items.append(match.group(item))
            return items

def string_contains(value, pattern, ignorecase=False, multiline=False):
    """Search the 'value' for 'pattern' and return True if at least one match was found"""
    match = regex_search(value, pattern, ignorecase, multiline)
    if match[0]:
        return True
    else:
        return False


def to_bool(string, default_value=None):
    """Convert a string representation of a boolean value to an actual bool"""
    return bool(strtobool(string).strip())


def to_yaml(value, indent=2, *args, **kw):
    """Convert the value to human readable YAML"""
    return yaml.dump(value, indent=indent, allow_unicode=True, default_flow_style=False, **kw)


def to_json(value, *args, **kw):
    """Convert the value to JSON"""
    return json.dumps(value, *args, **kw)


def to_nice_json(value, indent=4, *args, **kw):
    """Convert the value to human readable JSON"""
    return json.dumps(value, indent=indent, sort_keys=True, separators=(',', ': '), *args, **kw)


# register the filters
filters = {
    'mandatory': mandatory,
    'regex_escape': regex_escape,
    'regex_findall': regex_findall,
    'regex_replace': regex_replace,
    'regex_search': regex_search,
    'string_contains': string_contains,
    'to_yaml': to_yaml,
    'to_json': to_json,
    'to_nice_json': to_nice_json,
}
