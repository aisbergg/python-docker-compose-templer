import argparse
import io
import os
import sys
import time
import traceback
from ast import literal_eval
from copy import deepcopy
from distutils.util import strtobool

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
            x (dict): 
            y (dict): Second dict

        Returns:
            dict: 

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
    def load_yaml(string, Loader=yaml.CSafeLoader):
        """Parse a YAML string and produce the corresponding Python object.

        Args:
            string (str): The input string to be parsed
            Loader (yaml.Loader): Loader to use for parsing

        Returns:
            dict: The parsed YAML

        Raises:
            yaml.YAMLError: If the YAML string is malformed
        """
        try:
            Log.debug("Parsing YAML...")
            return yaml.load(string, Loader=Loader) or dict()
        except yaml.YAMLError as e:
            raise yaml.YAMLError("YAML parsing error: {0}".format(e.problem))
        except Exception:
            raise

    @staticmethod
    def hash(*args):
        hash = ''
        for string in args:
            hash = sha1((hash + str(string)).encode()).hexdigest()
        return hash


class Log(object):
    """Stupid logger that writes messages to stdout or stderr accordingly"""

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
        if indent > 0:
            lines = string.splitlines()
            return '\n'.join([' '*indent + l for l in string.splitlines()])
        else:
            return string

class JinjaRenderer(object):

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
        except Exception as e:
            try:
                # evaluate bool from different variations
                return bool(strtobool(string.strip()))
            except Exception as e:
                # string cannot be evaluated -> return string
                return string

    class Omit(object):
        pass

    @classmethod
    def render_string(cls, template_string, context):
        # add omit variable to context
        context['omit'] = JinjaRenderer.omit_placeholder

        try:
            return cls.env.from_string(template_string).render(context)
        except jinja_filter.MandatoryError as e:
            raise e
        except jinja2.UndefinedError as e:
            raise jinja2.exceptions.UndefinedError('Variable {0}'.format(str(e.message)))
        except jinja2.TemplateError as e:
            raise jinja2.exceptions.TemplateError('Jinja template error: {0}'.format(str(e.message)))
        except Exception as e:
            raise e

    @classmethod
    def render_dict_and_add_to_context(cls, the_dict, context):
        new_context = deepcopy(context)
        for k, v in the_dict.items():
            processed_value = cls._render_dict(v, new_context)
            if type(processed_value) is not JinjaRenderer.Omit:
                new_context = Utils.merge_dicts(new_context, {k: processed_value})
        return new_context

    @classmethod
    def _render_dict(cls, value, context):
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
                processed_item = cls._render_dict(li, context)
                if type(processed_item) is not JinjaRenderer.Omit:
                    new_list.append(processed_item)
            return new_list

        # dicts
        elif type(value) is dict:
            new_dict = dict()
            for k, v in value.items():
                processed_value = cls._render_dict(v, context)
                if type(processed_value) is not JinjaRenderer.Omit:
                    new_dict[k] = processed_value
            return new_dict

        # other types
        else:
            return value

    @classmethod
    def remove_omit_from_dict(cls, value):
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
    files = dict()

    def __init__(self, path, watch_changes=False):
        self._path = path

        self.cache = None
        self.on_change_event = Event()
        self.notifier = None
        if watch_changes:
            mask = pyinotify.IN_CREATE | pyinotify.IN_MODIFY
            self.wm = pyinotify.WatchManager()
            self.wm.add_watch(self.path, mask, rec=False)
            self.notifier = pyinotify.Notifier(self.wm, self._on_change, timeout=10)

    def __del__(self):
        self.remove()

    def remove(self):
        if self.notifier:
            self.notifier.stop()

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path):
        self._path = path

    def exists(self):
        return os.path.exists(self.path)

    def read(self):
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
        """Writes the given content into the file

        Args:
            content (str): Content to write into the file

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
        old_hash = self.cache['hash']
        self.cache = None
        self.read()
        if old_hash != self.cache['hash']:
            Log.debug("File '{0}' changed".format(self.path))
            self.on_change_event()

    @classmethod
    def get_file(cls, path, watch_changes=False):
        if path not in cls.files:
            cls.files[path] = cls(path, watch_changes)
        return cls.files[path]

    @classmethod
    def cleanup_unused_files(cls):
        for k in list(cls.files.keys()):
            if len(cls.files[k].on_change_event) == 0:
                cls.files[k].remove()
                del cls.files[k]


class ContextChainElement(object):

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
        if self.cache is not None:
            return self.cache
        else:
            return self._create_context()

    def _create_context(self):
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
        old_hash = self.cache_hash
        try:
            self._create_context()
        except Exception as e:
            Log.error("Faild to create context: {0}".format(str(e)))
            raise
        if self.cache_hash != old_hash:
            self.on_change_event()

    def remove(self):
        if type(self.source) == File:
            self.source.on_change_event -= self._on_change


class ContextChain(object):

    def __init__(self, watch_changes=False):
        self.chain_elements = []
        self.watch_changes = watch_changes
        self.on_change_event = Event()

    def add_context(self, context, origin_path):
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
        return self.chain_elements[-1].get_context()

    def remove(self):
        for ce in self.chain_elements:
            ce.remove()
        self.chain_elements = None


class Event(list):
    """Event subscription.

    """

    def __iadd__(self, handler):
        self.append(handler)
        return self

    def __isub__(self, handler):
        if handler in self:
            self.remove(handler)
        return self

    def __call__(self, *args, **kwargs):
        for f in self:
            f(*args, **kwargs)


class Definition(object):

    def __init__(self, path, force_overwrite=True, watch_changes=False):
        self.force_overwrite = force_overwrite
        self.watch_changes = watch_changes

        self.file = File.get_file(path, watch_changes)
        self.file.on_change_event += self._on_change
        self.templates = dict()
        self.changed_templates = list()
        self.failed_renders = list()

    def process(self):
        Log.info("\nProcess Definition: '{0}'".format(self.file.path))
        try:
            self._parse()
        except Exception as e:
            Log.error("Error loading options from definition file: {0}".format(str(e)), 2)
            return False

        return self._render_templates()

    def _parse(self):
        templates = dict()
        self.changed_templates = list()

        file_content = self.file.read()
        file_content = Utils.load_yaml(file_content)
        file_path = self.file.path

        if 'templates' not in file_content:
            raise ValueError("Missing key 'templates' in template definition")

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

            thash = Utils.hash(global_options['include_vars'], global_options['vars'], template_options['include_vars'], template_options['vars'], template_options['src'], template_options['dest'])

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
        all_renders_successfull = True
        for thash in self.changed_templates:
            t = self.templates[thash]
            if not t.render():
                all_renders_successfull = False
        return all_renders_successfull

    def _on_change(self, *args, **kwargs):
        self.process()


class Template(object):
    """ Represents a template file to be rendered with jinja2

    Args:
        src (str): Path to template file
        dest (str): Path for rendered file
        context (dict): Jinja2 context
        force_overwrite (bool): Overwrite existing file

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
        self.context.remove()
        self._file.on_change_event -= self.render

    @property
    def file(self):
        path = self._create_path(self.src)
        if self._file.path == path:
            return self._file
        else:
            self._file -= self.render
            self._file = File.get_file(path, self.watch_changes)
            self._file.on_change_event += self.render
            return self._file

    def _create_path(self, path, absolute=True):
        path = JinjaRenderer.render_string(path, self.context.get_context())
        if absolute and not os.path.isabs(path):
            return os.path.join(self.relative_path, path)
        else:
            return path

    def render(self):
        """Renders the template file with jinja2"""
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
            processed_content = yaml.dump(
                JinjaRenderer.remove_omit_from_dict(
                    Utils.load_yaml(rendered_file_content, Loader=yaml.RoundTripLoader)
                ),
                indent=2,
                block_seq_indent=2,
                allow_unicode=True,
                default_flow_style=False,
                Dumper=yaml.RoundTripDumper
            )

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

    def __init__(self, definitions):
        self.definitions = definitions

    def start(self):
        Log.info("Auto renderer started")

        # render on start
        for d in self.definitions:
            d.process()

        Log.debug("Listening for file changes...")

        # start file change listener
        while(True):
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
                time.sleep(0.1)
            except KeyboardInterrupt:
                break

        Log.info("\nAuto renderer stopped")


def cli():
    """ CLI entry point """
    # parsing arguments
    parser = argparse.ArgumentParser(
        prog='docker_compose_templer',
        description='Render Docker Compose file templates with the power of Jinja2',
        add_help=False)
    parser.add_argument('-a', '--auto-render', dest='auto_render',
                        action='store_true', default=False, help="Automatically render templates when a file changed")
    parser.add_argument('-f', '--force', dest='force_overwrite',
                        action='store_true', default=False, help="Overwrite existing files")
    parser.add_argument("-h", "--help", action="help",
                        help="Show this help message and exit")
    parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                        default=0, help="Enable verbose mode")
    parser.add_argument('--version', action='version', version='Templer {0}, Jinja2 {1}'.format(
        __version__, jinja2.__version__), help="Prints the program version and quits")
    parser.add_argument('definition_files', nargs='+',
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
        ) for path in args.definition_files
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
