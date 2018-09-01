""" Custom Jinja2 filters """

import yaml
import json

from jinja2 import StrictUndefined, UndefinedError


class MandatoryError(UndefinedError):
    def __init__(self, message):
        super().__init__(message)


def mandatory(value, error_message=u''):
    """Throws an 'UndefinedError' with an custom error massage, when value is undefined

    Args:
        value: Some value
        error_message (str): Massage to be displayed, when an exception is thrown

    Returns:
        value.  Unchanged value

    """
    if type(value) is StrictUndefined:
        raise MandatoryError(str(error_message))

    return value


def to_yaml(a, *args, **kw):
    """Convert the value to YAML"""
    return yaml.dump(a, allow_unicode=True, **kw)


def to_nice_yaml(a, indent=4, *args, **kw):
    """Make verbose, human readable YAML"""
    return yaml.dump(a, indent=indent, allow_unicode=True, default_flow_style=False, **kw)


def to_json(a, *args, **kw):
    """Convert the value to JSON"""
    return json.dumps(a, *args, **kw)


def to_nice_json(a, indent=4, *args, **kw):
    """Make verbose, human readable JSON"""
    try:
        return json.dumps(a, indent=indent, sort_keys=True, separators=(',', ': '), *args, **kw)
    except Exception as e:
        # Fallback to the to_json filter
        return to_json(a, *args, **kw)



# register the filters
filters = {
    'mandatory': mandatory,
    'to_yaml': to_yaml,
    'to_nice_yaml': to_nice_yaml,
    'to_json': to_json,
    'to_nice_json': to_nice_json,
}
