def merge_dicts(x, y):
    """Recursively merges two dicts.

    When keys exist in both the value of 'y' is used.

    Args:
        x (dict): First dict
        y (dict): Second dict

    Returns:
        dict: The merged dict
    """
    if x is None and y is None:
        return {}
    if x is None:
        return y
    if y is None:
        return x

    merged = dict(x, **y)
    xkeys = x.keys()

    for key in xkeys:
        if type(x[key]) is dict and key in y:
            merged[key] = merge_dicts(x[key], y[key])
    return merged


def load_yaml(string, safe=True):
    """Parses a YAML string and produce the corresponding Python object.

    Args:
        string (str): The input string to be parsed
        safe (bool): If True the CSafeLoader is used otherwise the RoundTripLoader

    Returns:
        dict: The parsed YAML

    Raises:
        yaml.YAMLError: If the YAML string is malformed
    """

    import ruamel.yaml as yaml
    from docker_compose_templer.log import Log

    try:
        Log.debug("Parsing YAML...")
        if safe:
            yml = yaml.YAML(typ='safe')
        else:
            yml = yaml.YAML(typ='rt')
        return yml.load(string) or {}
    except yaml.YAMLError as e:
        raise yaml.YAMLError("YAML parsing error: {0}".format(e.problem))
    except Exception:
        raise


def dump_yaml(data):
    """Dumps a Python object as a YAML string.

    Args:
        data (dict): The data to be dumped as YAML

    Returns:
        str: The dumped YAML

    Raises:
        yaml.TypeError: If a YAML type error occurred
    """

    import ruamel.yaml as yaml
    from io import StringIO
    from docker_compose_templer.log import Log

    yml = yaml.YAML()
    yml.indent(mapping=2, sequence=4, offset=2)
    yml.width = 1000
    try:
        Log.debug("Dumping YAML...")
        sio = StringIO()
        yml.dump(data, sio)
        return sio.getvalue()
    except yaml.TypeError as e:
        raise yaml.TypeError("YAML dump error: {0}".format(e.problem))
    except Exception:
        raise


def hash(*args):
    """Creates a single sha1 hash value of the given objects.

    Args:
        *args: The objects to be hashed

    Returns:
        str: sha1 hash of all objects given
    """

    import json
    from hashlib import sha1

    calculated_hash = ''
    for object in args:
        if type(object) is dict:
            calculated_hash = sha1((calculated_hash + json.dumps(object, sort_keys=True)).encode()).hexdigest()
        else:
            calculated_hash = sha1((calculated_hash + str(object)).encode()).hexdigest()
    return calculated_hash
