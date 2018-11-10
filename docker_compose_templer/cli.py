import argparse
import io
import os
import sys
import time
import traceback
from ast import literal_eval
from copy import deepcopy
from distutils.util import strtobool
from io import StringIO

import jinja2
import pyinotify
import ruamel.yaml as yaml

from docker_compose_templer import __version__
from docker_compose_templer import jinja_filter

try:
    from hashlib import sha1
except ImportError:
    from sha import sha as sha1


class Utils:

    @staticmethod
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
            return dict()
        if x is None:
            return y
        if y is None:
            return x

        merged = dict(x, **y)
        xkeys = x.keys()

        for key in xkeys:
            if type(x[key]) is dict and key in y:
                merged[key] = Utils.merge_dicts(x[key], y[key])
        return merged

    @staticmethod
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
        try:
            Log.debug("Parsing YAML...")
            if safe:
                yml = yaml.YAML(typ='safe')
            else:
                yml = yaml.YAML(typ='rt')
            return yml.load(string) or dict()
        except yaml.YAMLError as e:
            raise yaml.YAMLError("YAML parsing error: {0}".format(e.problem))
        except Exception:
            raise

    @staticmethod
    def dump_yaml(data):
        """Dumps a Python object as a YAML string.

        Args:
            data (dict): The data to be dumped as YAML

        Returns:
            str: The dumped YAML

        Raises:
            yaml.TypeError: If a YAML type error occurred
        """
        yml = yaml.YAML()
        yml.explicit_start = True
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

    @staticmethod
    def hash(*args):
        """Creates a single sha1 hash value of the given objects.

        Args:
            *args: The objects to be hashed

        Returns:
            str: sha1 hash of all objects given
        """
        hash = ''
        for string in args:
            hash = sha1((hash + str(string)).encode()).hexdigest()
        return hash


class Log(object):
    """Stupid logger that writes messages to stdout or stderr accordingly."""

    ERROR = 30
    INFO = 20
    DEBUG = 10
    level = ERROR

    @staticmethod
    def debug(msg, indent=0):
        if Log.level <= 10:
            sys.stdout.write(Log.indent_string(msg, indent) + "\n")

    @staticmethod
    def info(msg, indent=0):
        if Log.level <= 20:
            sys.stdout.write(Log.indent_string(msg, indent) + "\n")

    @staticmethod
    def error(msg, indent=0):
        sys.stderr.write(Log.indent_string(msg, indent) + "\n")
        if Log.level <= 10:
            traceback.print_exc(5)

    @staticmethod
    def indent_string(string, indent):
        """Adds indentation to a string.

        Args:
            string (str): String to be indented
            indent (int): Number of spaces to indent the string

        Returns:
            str: The indented string.
        """
        if indent > 0:
            lines = string.splitlines()
            return '\n'.join([' ' * indent + l for l in string.splitlines()])
        else:
            return string


class JinjaRenderer(object):
    """Supplies functions to render templates with Jinja.

    Attributes:
        omit_placeholder (str): The omit placeholder used for removing keys from a dict/yaml
        env: The jinja environment used to render strings

    """

    omit_placeholder = '__omit_place_holder__%s' % sha1(os.urandom(64)).hexdigest()
    env = jinja2.Environment(
        lstrip_blocks=True,
        trim_blocks=True,
        undefined=jinja2.StrictUndefined
    )
    env.filters = Utils.merge_dicts(env.filters, jinja_filter.filters)

    @staticmethod
    def _evaluate_string(string):
        """Evaluates a string containing a Python value.

        Args:
            string(str): A Python value represented as a string

        Returns:
            str, int, float, bool, list or dict: The value of the evaluated string
        """
        try:
            # evaluate to int, float, list, dict
            return literal_eval(string.strip())
        except (ValueError, SyntaxError) as e:
            try:
                # evaluate bool from different variations
                return bool(strtobool(string.strip()))
            except ValueError as e:
                # string cannot be evaluated -> return string
                return string

    class Omit(object):
        """Represents a omit object"""
        pass

    @classmethod
    def render_string(cls, template_string, context):
        """Renders a template string with Jinja.

        Args:
            template_string (str): The template string to be rendered
            context (dict): The context used for rendering

        Returns:
            str: The rendered string

        Raises:
            jinja_filter.MandatoryError: If a variable is undefined and the mandatory filter was used
            jinja2.UndefinedError: If a variable is undefined
            jinja2.TemplateError: If the template contains an invalid syntax
        """
        # add omit variable to context
        context['omit'] = JinjaRenderer.omit_placeholder

        try:
            return cls.env.from_string(template_string).render(context)
        except jinja_filter.MandatoryError as e:
            raise e
        except jinja2.UndefinedError as e:
            raise jinja2.UndefinedError('Undefined variable: {0}'.format(str(e.message)))
        except jinja2.TemplateError as e:
            raise jinja2.TemplateError('Jinja template error: {0}'.format(str(e.message)))

    @classmethod
    def render_dict_and_add_to_context(cls, the_dict, context):
        """Renders a dict and adds it to the context.

        Args:
            the_dict (dict): The dict to be rendered
            context (dict): The context that is used for rendering

        Returns:
            dict: The context that contains also the variables from the_dict

        Raises:
            jinja_filter.MandatoryError: If a variable is undefined and the mandatory filter was used
            jinja2.UndefinedError: If a variable is undefined
            jinja2.TemplateError: If the template contains an invalid syntax
        """
        new_context = deepcopy(context)
        for k, v in the_dict.items():
            processed_value = cls._render_recursively(v, new_context)
            if type(processed_value) is not JinjaRenderer.Omit:
                new_context = Utils.merge_dicts(new_context, {k: processed_value})
        return new_context

    @classmethod
    def _render_recursively(cls, value, context):
        """Renders a value recursively.

        Args:
            value: Value to be rendered
            context: The context used for rendering

        Returns:
            Value that has been rendered with Jinja

        Raises:
            jinja_filter.MandatoryError: If a variable is undefined and the mandatory filter was used
            jinja2.UndefinedError: If a variable is undefined
            jinja2.TemplateError: If the template contains an invalid syntax
        """
        if value is None:
            return None

        # str
        elif type(value) is str:
            rendered_value = cls.render_string(value, context)
            if rendered_value == value:
                return value
            else:
                if rendered_value.find(JinjaRenderer.omit_placeholder) != -1:
                    return JinjaRenderer.Omit()
                else:
                    return cls._evaluate_string(rendered_value)

        # lists
        elif type(value) is list:
            new_list = []
            for li in value:
                processed_item = cls._render_recursively(li, context)
                if type(processed_item) is not JinjaRenderer.Omit:
                    new_list.append(processed_item)
            return new_list

        # dicts
        elif type(value) is dict:
            new_dict = dict()
            for k, v in value.items():
                processed_value = cls._render_recursively(v, context)
                if type(processed_value) is not JinjaRenderer.Omit:
                    new_dict[k] = processed_value
            return new_dict

        # other types
        else:
            return value

    @classmethod
    def remove_omit_from_dict(cls, value):
        """Parses a YAML string and produce the corresponding Python object.

        Args:
            value: The value from which all occurrences of omit shall be removed

        Returns:
            dict: The processed dict
        """
        if value is None:
            return None

        elif type(value) is str:
            if value.find(JinjaRenderer.omit_placeholder) != -1:
                return JinjaRenderer.Omit()
            else:
                return value

        # lists
        elif isinstance(value, (yaml.comments.CommentedSeq, list)):
            vlen = len(value)
            for i in range(vlen - 1, -1, -1):
                processed_item = cls.remove_omit_from_dict(value[i])
                if type(processed_item) is JinjaRenderer.Omit:
                    del value[i]
                    i -= 1
            return value

        # dicts
        elif isinstance(value, (yaml.comments.CommentedMap, dict)):
            for key in list(value.keys()):
                processed_value = cls.remove_omit_from_dict(value[key])
                if type(processed_value) is JinjaRenderer.Omit:
                    del value[key]
            return value

        else:
            return value


class File(object):
    """Represents a file.

    The class implements file caching and a file watching functionality. File changes will dispatch all events that are
    listed in on_change_event.

    Args:
        path (str): The path of the file.
        watch_changes (bool): If true the file shall be watched for relevant changes.

    Attributes:
        files (dict): All loaded files stored with their path as the key
        path (str): The path of the file
        on_change_event (Event): List of subscribed events
        notifier (pyinotify.Notifier): Underlying file change listener

    """
    files = dict()

    def __init__(self, path, watch_changes=False):
        self.path = path

        self.cache = None
        self.on_change_event = Event()
        self.notifier = None
        if watch_changes:
            mask = pyinotify.IN_CREATE | pyinotify.IN_MODIFY
            wm = pyinotify.WatchManager()
            wm.add_watch(self.path, mask, rec=False)
            self.notifier = pyinotify.Notifier(wm, self._on_change, timeout=10)

    def __del__(self):
        self.remove()

    def remove(self):
        """Stop listening to file changes."""
        if self.notifier:
            self.notifier.stop()

    def exists(self):
        """Returns true if the file exists in the filesystem."""
        return os.path.exists(self.path)

    def read(self):
        """Reads the files content.

        The file content will cached. Consecutive reads will yield the cache content so the file doesn't have to be read
        twice.

        Returns:
            str: The content of the file.

        Raises:
            FileNotFoundError: If the file could not be found under the path
            IOError: If the given path does not contain a file
        """
        if self.cache and self.cache['path'] == self.path:
            Log.debug("Return cached file '{0}'...".format(self.path))
            return self.cache['content']

        else:
            self.cache = dict()

            if not self.exists():
                raise FileNotFoundError("File does not exist: '{0}'".format(self.path))
            if not os.path.isfile(self.path):
                raise IOError("Is not a file: '{0}".format(self.path))

            Log.debug("Loading file '{0}'...".format(self.path))
            with io.open(self.path, 'r', encoding='utf8') as f:
                file_content = f.read()

            self.cache['path'] = self.path
            self.cache['content'] = file_content
            self.cache['hash'] = Utils.hash(file_content)
            return self.cache['content']

    @staticmethod
    def write(content, path, force_overwrite=False):
        """Writes the content into a file with the given path.

        Args:
            content (str): Content to write into the file
            path (str): Path where the content shall be written to
            force_overwrite (bool): If true any existing file will be overwritten

        Raises:
            IOError: If desired output file exists or is not a file
        """
        if os.path.exists(path):
            if os.path.isfile(path):
                if not force_overwrite:
                    raise IOError("Destination already exists. Use '-f' flag to overwrite the file: '{0}".format(path))
            else:
                raise IOError("Destination exists and is not a file: '{0}".format(path))
        else:
            # create dir
            if os.path.dirname(path):
                os.makedirs(os.path.dirname(path), exist_ok=True)

        # write content to file
        Log.debug("Writing file '{0}'...".format(path))
        with io.open(path, 'w', encoding='utf8') as f:
            f.write(content)

    def _on_change(self, *args, **kwargs):
        """Gets executed on change event."""
        old_hash = self.cache['hash']
        self.cache = None
        self.read()
        if old_hash != self.cache['hash']:
            Log.debug("File '{0}' changed".format(self.path))
            self.on_change_event()

    @classmethod
    def get_file(cls, path, watch_changes=False):
        """Returns a file with the given path.

        If the file with the given path is already loaded into memory it will be returned instead of creating a new
        instance.

        Args:
            path: Path of the file
            watch_changes: Tell the file to watch for changes

        Returns:
            File: An instance of File with the given path
        """
        if path not in cls.files:
            cls.files[path] = cls(path, watch_changes)
        return cls.files[path]

    @classmethod
    def cleanup_unused_files(cls):
        """Removes loaded files from memory that aren't used anymore."""
        for k in list(cls.files.keys()):
            if len(cls.files[k].on_change_event) == 0:
                cls.files[k].remove()
                del cls.files[k]


class ContextChainElement(object):
    """Represents a context chain element that is part of a ContextChain.

    Args:
        source (dict or File): Source of the context can either be a File or a dict
        prev (ContextChainElement): Previous element in the chain
    Attributes:
        prev (ContextChainElement): Previous element in the chain
        next (ContextChainElement): Next element in the chain
        source (dict or File): Source of the context can either be a File or a dict
        cache (dict): Ready processed and cached context
        cache_hash (str): SHA1 hash of the cache to check for changes
        on_change_event (Event): Events that get dispatched on a change
    """

    def __init__(self, source, prev=None):
        self.prev = prev
        self.next = None
        self.source = source

        self.cache = None
        self.cache_hash = None
        self.on_change_event = Event()
        if type(source) == File:
            self.source.on_change_event += self._on_change

    def get_context(self):
        """Returns the composed context up to this chain element.

        If the context was already created earlier and cached, then the cache will be returned.

        Returns:
            dict: The composed context
        Raises:
            Exception: If the variables cannot be loaded for some reasons
        """
        if self.cache is not None:
            return self.cache
        else:
            return self._create_context()

    def _create_context(self):
        """Creates the context by rendering the context's source with Jinja and merging it with the contexts of previous
        elements in the chain.

        Returns:
            dict: The composed context
        Raises:
            Exception: If the variables cannot be loaded for some reasons
        """
        parent_context = self.prev.get_context() if self.prev else dict()
        if type(self.source) == File:
            file_content = self.source.read()
            try:
                self.cache = JinjaRenderer.render_dict_and_add_to_context(
                    Utils.load_yaml(file_content),
                    parent_context
                )
            except Exception as e:
                raise Exception("Cannot load variables from '{0}': {1}".format(self.source.path, str(e)))
        elif type(self.source) == dict:
            try:
                self.cache = JinjaRenderer.render_dict_and_add_to_context(
                    self.source['data'],
                    parent_context
                )
            except Exception as e:
                raise Exception("Cannot load variables from '{0}': {1}".format(self.source['path'], str(e)))

        self.cache_hash = Utils.hash(self.cache)
        return self.cache

    def _on_change(self, *args, **kwargs):
        """Gets executed on a change event."""
        old_hash = self.cache_hash
        try:
            self._create_context()
        except Exception as e:
            Log.error("Faild to create context: {0}".format(str(e)))
            raise
        if self.cache_hash != old_hash:
            self.on_change_event()

    def remove(self):
        """Stops listening for file changes."""
        if type(self.source) == File:
            self.source.on_change_event -= self._on_change


class ContextChain(object):
    """Represents a context that is composed of multiple ContextChainElements.

    Args:
        watch_changes (bool): Enable watching for file changes
    Attributes:
        chain_elements (list): The elements of the chain
        watch_changes (bool): Enable watching for file changes
        on_change_event (Event): Events that get dispatched on a file change
    """

    def __init__(self, watch_changes=False):
        self.chain_elements = []
        self.watch_changes = watch_changes
        self.on_change_event = Event()

    def add_context(self, context, origin_path):
        """Adds a context to the chain.

        Args:
            context (dict): The (unprocessed) context to add
            origin_path (str): The file path where the context originated (used for logging)
        """
        if context:
            tail = self.chain_elements[-1] if self.chain_elements else None
            elm = ContextChainElement(
                source={'path': origin_path, 'data': context},
                prev=tail
            )
            elm.on_change_event += self.on_change_event
            self.chain_elements.append(elm)
            if tail:
                tail.next = elm

    def add_files(self, files, relative_path):
        """Adds a list of YAML files to the context chain.

        Args:
            files (list): Paths of YAML files to add
            relative_path: Relative path to look for the files
        """
        for path in files:
            if not os.path.isabs(path):
                path = os.path.join(relative_path, path)
            tail = self.chain_elements[-1] if self.chain_elements else None
            elm = ContextChainElement(
                source=File.get_file(path, self.watch_changes),
                prev=tail
            )
            elm.on_change_event += self.on_change_event
            self.chain_elements.append(elm)
            if tail:
                tail.next = elm

    def get_context(self):
        """Returns the composed context."""
        return self.chain_elements[-1].get_context()

    def remove(self):
        """Stops listening for changes."""
        for ce in self.chain_elements:
            ce.remove()
        self.chain_elements = None


class Event(list):
    """Represent an subscribable event."""

    def __iadd__(self, handler):
        """Adds a handler to the subscribe list."""
        self.append(handler)
        return self

    def __isub__(self, handler):
        """Removes a handler from the subscribe list."""
        if handler in self:
            self.remove(handler)
        return self

    def __call__(self, *args, **kwargs):
        """Executes the stored handlers"""
        for f in self:
            f(*args, **kwargs)


class Definition(object):
    """Resembles a definition file.

    Args:
        path (str): Path of the definition file
        force_overwrite (str): Force overwriting of existing files
        watch_changes (bool): Enable watching for file changes
    Attributes:
        force_overwrite (str): Force overwriting of existing files
        watch_changes (bool): Enable watching for file changes
        file (File): The definition file
        templates (dict): The loaded templates (SHA1 hashes are used as keys)
        changed_templates (list): List of templates that changed (only in auto render mode)
    """

    def __init__(self, path, force_overwrite=True, watch_changes=False):
        self.force_overwrite = force_overwrite
        self.watch_changes = watch_changes

        self.file = File.get_file(path, watch_changes)
        self.file.on_change_event += self._on_change
        self.templates = dict()
        self.changed_templates = list()

    def process(self):
        """Process the definition.

        Parses the definition file, loads the external context from YAML files and renders the defined templates.

        Returns:
            bool: True if the processing finished without errors else False
        """
        Log.info("\nProcess Definition: '{0}'".format(self.file.path))
        try:
            self._parse()
        except Exception as e:
            Log.error("Error loading options from definition file: {0}".format(str(e)), 2)
            return False

        return self._render_templates()

    def _parse(self):
        """Parses the definition file.

        Raises:
            FileNotFoundError: If the file could not be found under the path
            IOError: If the given path does not contain a file
            yaml.YAMLError: If the YAML string is malformed
            ValueError: If the syntax of the definition file is wrong
        """
        templates = dict()
        self.changed_templates = list()

        file_content = self.file.read()
        file_content = Utils.load_yaml(file_content)
        file_path = self.file.path

        if 'templates' not in file_content:
            raise ValueError("Missing key 'templates' in template definition")
        if type(file_content['templates']) is not list:
            raise ValueError("Value of 'templates' must be of type list")

        global_options = self._parse_variable_options(file_content)

        for t in file_content['templates']:
            template_options = self._parse_variable_options(t)

            if 'src' in t:
                if type(t['src']) is str:
                    template_options['src'] = t['src']
                else:
                    raise ValueError("Value of 'src' must be of type string")
            else:
                raise ValueError("Missing key 'src' in template definition")

            if 'dest' in t:
                if type(t['dest']) is str:
                    template_options['dest'] = t['dest']
                else:
                    raise ValueError("Value of 'dest' must be of type string")
            else:
                raise ValueError("Missing key 'dest' in template definition")

            thash = Utils.hash(global_options['include_vars'], global_options['vars'], template_options['include_vars'],
                               template_options['vars'], template_options['src'], template_options['dest'])

            # reuse previous parsed templates (only in Auto Renderer mode)
            if thash in self.templates:
                templates[thash] = self.templates[thash]
                continue

            # load local variables
            tcc = ContextChain(self.watch_changes)
            tcc.add_files(global_options['include_vars'], os.path.dirname(file_path))
            tcc.add_context(global_options['vars'], file_path)
            tcc.add_files(template_options['include_vars'], os.path.dirname(file_path))
            tcc.add_context(template_options['vars'], file_path)

            templates[thash] = Template(
                src=template_options['src'],
                dest=template_options['dest'],
                relative_path=os.path.dirname(file_path),
                context=tcc,
                force_overwrite=self.force_overwrite,
                watch_changes=self.watch_changes
            )
            self.changed_templates.append(thash)

        # cleanup undefined templates (only in Auto Renderer mode)
        for thash, t in self.templates.items():
            if thash not in templates:
                t.remove()
        File.cleanup_unused_files()

        self.templates = templates

    def _parse_variable_options(self, options):
        """Parses common options and sets defaults.

        Args:
            options: Options that need to be parsed

        Returns:
            dict: The parsed options
        """
        processed_options = dict()

        if 'vars' in options:
            if type(options['vars']) is dict:
                processed_options['vars'] = options['vars']
            else:
                raise ValueError("Value of 'vars' must be of type dict")
        else:
            processed_options['vars'] = dict()

        if 'include_vars' in options:
            if type(options['include_vars']) is list:
                processed_options['include_vars'] = options['include_vars']
            elif type(options['include_vars']) is str:
                processed_options['include_vars'] = [options['include_vars']]
            else:
                raise ValueError("Value of 'include_vars' must be of type list or string")
        else:
            processed_options['include_vars'] = []

        return processed_options

    def _render_templates(self):
        """Renders the loaded templates.

        Returns:
            bool: True if the processing finished without errors else False
        """
        all_renders_successfull = True
        for thash in self.changed_templates:
            t = self.templates[thash]
            if not t.render():
                all_renders_successfull = False
        return all_renders_successfull

    def _on_change(self, *args, **kwargs):
        """Gets executed on change event."""
        self.process()


class Template(object):
    """Represents a template file to be rendered with jinja2

    Args:
        src (str): Path to template file
        dest (str): Path for rendered file
        context (dict): Jinja2 context
        force_overwrite (bool): Force overwrite of an existing file
        watch_changes (bool): Enable watching for file changes
    Attributes:
        src (str): Path to template file
        dest (str): Path for rendered file
        context (dict): Jinja2 context
        force_overwrite (bool): Force overwrite of an existing file
        watch_changes (bool): Enable watching for file changes
        _file (File): The template file

    """

    def __init__(self, src, dest, relative_path, context, force_overwrite=False, watch_changes=False):
        self.src = src
        self.dest = dest
        self.relative_path = relative_path
        self.context = context
        self.force_overwrite = force_overwrite
        self.watch_changes = watch_changes

        self._file = File.get_file(self._create_path(self.src), self.watch_changes)
        self._file.on_change_event += self.render
        self.context.on_change_event += self.render

    def remove(self):
        """Stop listening for changes."""
        self.context.remove()
        self._file.on_change_event -= self.render

    @property
    def file(self):
        """Returns the template file as File object"""
        # the path might change depending on the context used --> render src path and compare it to previous used path.
        # If it changed then a new file will be returned
        path = self._create_path(self.src)
        if self._file.path == path:
            return self._file
        else:
            self._file -= self.render
            self._file = File.get_file(path, self.watch_changes)
            self._file.on_change_event += self.render
            return self._file

    def _create_path(self, path, absolute=True):
        """Renders the given path with Jinja and returns the result.

        Args:
            path: The path to be rendered
            absolute: If true the returned path will be an absolute one

        Returns:
            str: The rendered path
        """
        path = JinjaRenderer.render_string(path, self.context.get_context())
        if absolute and not os.path.isabs(path):
            return os.path.join(self.relative_path, path)
        else:
            return path

    def render(self):
        """Renders the template file with Jinja and writes the output to the destination.

        Returns:
            bool: True if the processing finished without errors else false
        """
        src_rel = self.src
        dest_rel = self.dest

        try:
            try:
                src_rel = self._create_path(self.src, False)
                dest_rel = self._create_path(self.dest, False)
            finally:
                Log.info("Render template: '{0}' --> '{1}'".format(src_rel, dest_rel))

            file_content = self.file.read()

            # render the template with Jinja
            rendered_file_content = JinjaRenderer.render_string(file_content, self.context.get_context())

            # remove values containing an omit placeholder
            processed_content = Utils.dump_yaml(JinjaRenderer.remove_omit_from_dict(
                Utils.load_yaml(rendered_file_content, safe=False)))

            # write the rendered content into a file
            dest_path = self._create_path(self.dest)
            self.file.write(
                content=processed_content,
                path=dest_path,
                force_overwrite=self.force_overwrite
            )

            return True

        except Exception as e:
            Log.error("Error while rendering template: {0}".format(str(e)), 2)
            return False


class AutoRenderer(object):
    """The Auto Renderer periodically checks for file changes and dispatches any subscribed events.

    Args:
        definitions (Definition): The definitions
    Attributes:
        definitions (Definition): The definitions
    """

    def __init__(self, definitions):
        self.definitions = definitions

    def start(self):
        """Starts the Auto Renderer."""
        Log.info("Auto renderer started")

        # render on start
        for d in self.definitions:
            d.process()

        Log.info("\nWaiting for changes...")

        # start file change listener
        while (True):
            try:
                for notifier in [f.notifier for _, f in File.files.items()]:
                    try:
                        if notifier.check_events():
                            notifier.read_events()
                            notifier.process_events()
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        break
                time.sleep(0.3)
            except KeyboardInterrupt:
                break

        Log.info("\nAuto renderer stopped")


def cli():
    """The CLI entry point."""
    # parse arguments
    parser = argparse.ArgumentParser(
        prog='docker_compose_templer',
        description='Render Docker Compose file templates with the power of Jinja2',
        add_help=False)
    parser.add_argument('-a', '--auto-render', dest='auto_render',
                        action='store_true', default=False,
                        help="Monitor file changes and render templates automatically")
    parser.add_argument('-f', '--force', dest='force_overwrite',
                        action='store_true', default=False, help="Overwrite existing files")
    parser.add_argument("-h", "--help", action="help",
                        help="Show this help message and exit")
    parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                        default=0, help="Enable verbose mode")
    parser.add_argument('--version', action='version', version='Docker Compose Templer {0}, Jinja2 {1}'.format(
        __version__, jinja2.__version__), help="Print the program version and quit")
    parser.add_argument('definition_file', nargs='+',
                        help="File that defines what to do.")
    args = parser.parse_args(sys.argv[1:])

    # initialize dumb logger
    levels = [Log.ERROR, Log.INFO, Log.DEBUG]
    Log.level = levels[min(len(levels) - 1, args.verbose + 1)]

    definitions = [
        Definition(
            path=path,
            force_overwrite=args.force_overwrite,
            watch_changes=args.auto_render
        ) for path in args.definition_file
    ]
    for d in definitions:
        if not d.file.exists():
            Log.error("Definition file does not exist: '{0}'".format(d.file.path))
            exit(1)

    if args.auto_render:
        ar = AutoRenderer(definitions)
        ar.start()

    else:
        some_renders_failed = False
        # process definition files
        for df in definitions:
            if not df.process():
                some_renders_failed = True

        if some_renders_failed:
            Log.error("\nSome renders failed")
            exit(1)

    exit(0)
