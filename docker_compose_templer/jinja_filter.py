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
        error_message = str(error_message) or "The variable '{0}' is undefined".format(value._undefined_name)
        raise MandatoryError(error_message)

    return value


def regex_escape(string):
    """Escape special characters in a string so it can be used in regular expressions"""
    return re.escape(string)


def regex_findall(value, pattern, ignorecase=False, multiline=False):
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

def regex_contains(value, pattern, ignorecase=False, multiline=False):
    """Search the 'value' for 'pattern' and return True if at least one match was found"""
    match = regex_search(value, pattern, ignorecase=ignorecase, multiline=multiline)
    if match:
        return True
    else:
        return False


def to_bool(string, default_value=None):
    """Convert a string representation of a boolean value to an actual bool

    Args:
        string (str): A string to be converted to bool
        default_value: Default value when 'string' is not an boolean value

    Returns:
        bool: Converted string

    """
    try:
        return bool(strtobool(string.strip()))
    except ValueError:
        if default_value is not None:
            return default_value
        else:
            raise ValueError("'{0}' is not a boolean value".format(string.strip()))


def to_yaml(value, indent=2, *args, **kw):
    """Convert the value to human readable YAML"""
    return yaml.dump(
        value,
        block_seq_indent=indent,
        indent=indent,
        allow_unicode=True,
        default_flow_style=False,
        **kw
    )

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
    'regex_contains': regex_contains,
    'to_bool': to_bool,
    'to_yaml': to_yaml,
    'to_json': to_json,
    'to_nice_json': to_nice_json,
}
