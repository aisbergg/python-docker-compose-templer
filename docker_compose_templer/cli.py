import argparse
import os
import sys
import traceback
import jinja2
import ruamel.yaml as yaml
import io

from docker_compose_templer import __version__
from docker_compose_templer import jinja_filter

try:
    from hashlib import sha1
except ImportError:
    from sha import sha as sha1


def merge_dicts(x, y):
    """ Recursively merges two dicts.

    When keys exist in both the value of 'y' is used.

    Args:
        x (dict): First dict
        y (dict): Second dict

    Returns:
        dict: Merged dict containing values of x and y

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
            merged[key] = merge_dicts(x[key], y[key])
    return merged


def load_yaml(string, Loader=yaml.SafeLoader):
    try:
        Log.debug("Parsing YAML...")
        return yaml.load(string, Loader=Loader) or dict()
    except yaml.YAMLError as e:
        if hasattr(e, 'problem_mark'):
            raise yaml.YAMLError(
                "YAML parsing error:\n{0}\n  {1}\n  {2}".format(e.context_mark, e.problem, e.problem_mark))
        else:
            raise yaml.YAMLError("YAML parsing error: {0}".format(str(e)))
    except Exception as e:
        raise Exception("YAML parsing error: {0}".format(str(e)))


class Log(object):
    """ Stupid logger that writes messages to stdout or stderr accordingly"""

    ERROR = 30
    INFO = 20
    DEBUG = 10
    level = ERROR

    @staticmethod
    def debug(msg):
        if Log.level <= 10:
            sys.stdout.write(msg + "\n")

    @staticmethod
    def info(msg):
        if Log.level <= 20:
            sys.stdout.write(msg + "\n")

    @staticmethod
    def error(msg):
        sys.stderr.write(msg + "\n")


class Context(object):
    """Represents a context creator

    Args:
        variables (dict): Variables passed via 'vars'
        variable_files (list): YAML files to be used as context files

    """

    def __init__(self, variables, variable_files, definition_file_path):
        self.variables = variables
        self.variable_files = variable_files
        self.definition_file_path = definition_file_path

        # for formatting
        self._scope = ''

    def get(self):
        """Get the context

        Returns:
            dict: The context

        """
        context = dict()
        for f in self.variable_files:
            if not os.path.isabs(f):
                f = os.path.join(os.path.dirname(self.definition_file_path), f)
            context = merge_dicts(context, ContextFile(f).read())

        context = merge_dicts(context, self.variables)

        return context


class SilentUndefined(jinja2.Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return ''


class BaseFile(object):
    def __init__(self, path):
        self.path = path

    def read(self):
        if not os.path.exists(self.path):
            raise IOError(self._format_error("Error reading file", "File does not exist"))
        if not os.path.isfile(self.path):
            raise IOError(self._format_error("Error reading file", "Is not a file"))

        Log.debug("Loading file '{0}'...".format(self.path))
        with io.open(self.path, 'r', encoding='utf8') as f:
            file_content = f.read()

        return file_content

    def _format_error(self, heading, description):
        """ Formats an error for pretty cli output

        Args:
            heading (str): The error message
            description (str): The error message

        Returns:
            str: Formatted error message

        """
        description = description.replace('\n', '\n               ')
        return "{0}:\n  Description: {1}\n        Scope: {2}\n         Path: {3}".format(heading, description,
                                                                                         self._scope, self.path)


class ContextFile(BaseFile):
    def __init__(self, path):
        super().__init__(path)
        self._scope = 'Variable File'

    def read(self):
        file_content = super().read()
        try:
            return load_yaml(file_content)
        except Exception as e:
            raise Exception(self._format_error("Error loading variables from file", str(e)))
            raise e


class DefinitionFile(BaseFile):
    def __init__(self, path, file_mode=None, force_overwrite=True, ignore_undefined_variables=None):
        super().__init__(path)
        self.file_mode = file_mode
        self.force_overwrite = force_overwrite
        self.ignore_undefined_variables = ignore_undefined_variables

        self.templates = []
        self._scope = 'Definition File'

    def read(self):
        file_content = super().read()
        try:
            return load_yaml(file_content)
        except Exception as e:
            raise Exception(self._format_error("Error loading variables from file", str(e)))
            raise e

    def parse(self):
        self.templates = []
        file_content = self.read()

        # options passed through cli
        overwrite_options = {
            "mode": self.file_mode,
            "ignore_undefined_variables": self.ignore_undefined_variables
        }

        # global options
        global_options = self._parse_options(file_content, True)

        # templates
        if 'templates' not in file_content:
            raise ValueError("Missing 'templates' definition")

        for t in file_content['templates']:
            template_options = self._parse_options(t, False)

            if 'src' in t:
                if type(t['src']) is str:
                    if os.path.isabs(t['src']):
                        template_options['src'] = t['src']
                    else:
                        template_options['src'] = os.path.join(os.path.dirname(self.path), t['src'])
                else:
                    raise ValueError("Value of 'src' must be of type string")
            else:
                raise ValueError("Missing key 'src' in template definition")

            if 'dest' in t:
                if type(t['dest']) is str:  # TODO: list merge
                    if os.path.isabs(t['dest']):
                        template_options['dest'] = t['dest']
                    else:
                        template_options['dest'] = os.path.join(os.path.dirname(self.path), t['dest'])
                else:
                    raise ValueError("Value of 'dest' must be of type string")
            else:
                raise ValueError("Missing key 'dest' in template definition")

            template_options = merge_dicts(global_options, template_options)
            template_options = merge_dicts(template_options, overwrite_options)

            self.templates.append(
                TemplateFile(
                    src=template_options['src'],
                    dest=template_options['dest'],
                    context=Context(
                        variables=template_options['vars'],
                        variable_files=template_options['include_vars'],
                        definition_file_path=self.path
                    ),
                    file_mode=template_options['mode'],
                    force_overwrite=self.force_overwrite,
                    ignore_undefined_variables=template_options['ignore_undefined_variables']
                )
            )

    def _parse_options(self, context, set_defaults):
        options = dict()

        if 'vars' in context:
            if type(context['vars']) is dict:
                options['vars'] = context['vars']
            else:
                raise ValueError("Value of 'vars' must be of type dict")
        elif set_defaults:
            options['vars'] = dict()

        if 'include_vars' in context:
            if type(context['include_vars']) is list:
                options['include_vars'] = context['include_vars']
            elif type(context['include_vars']) is str:
                options['include_vars'] = [context['include_vars']]
            else:
                raise ValueError("Value of 'include_vars' must be of type list or string")
        elif set_defaults:
            options['include_vars'] = []

        if 'mode' in context:
            if type(context['mode']) is str:
                options['mode'] = context['mode']
            else:
                raise ValueError("Value of 'mode' must be of type list or string")
        elif set_defaults:
            options['mode'] = None

        if 'ignore_undefined_variables' in context:
            if type(context['ignore_undefined_variables']) is bool:
                options['ignore_undefined_variables'] = context['ignore_undefined_variables']
            else:
                raise ValueError("Value of 'ignore_undefined_variables' must be of type list or string")
        elif set_defaults:
            options['ignore_undefined_variables'] = False

        return options

    def get_template_files(self):
        return self.templates

    def render_templates(self):
        if self.templates:
            failed_renders = []
            for t in self.templates:
                try:
                    t.render()
                except Exception as e:
                    failed_renders.append(t)
                    if Log.level <= 10:
                        Log.error(traceback.format_exc())
                    else:
                        Log.error(str(e))

            if len(failed_renders) > 0:
                Log.error("\nSome renders failed:")
                for fr in failed_renders:
                    Log.error("    " + fr.path)
                return False

            return True


class TemplateFile(BaseFile):
    """ Represents a template file to be rendered with jinja2

    Args:
        src (str): Path to template file
        dest (str): Path for rendered file
        context (dict): Jinja2 context
        file_mode (str): Mode for the rendered file
        force_overwrite (bool): Overwrite existing file
        ignore_undefined_variables (bool): Don't throw any error when a variable is not defined

    """

    def __init__(self, src, dest, context, file_mode=None, force_overwrite=False, ignore_undefined_variables=False):
        super().__init__(src)
        self.dest = dest
        self.context = context
        self.file_mode = file_mode
        self.force_overwrite = force_overwrite
        self.ignore_undefined_variables = ignore_undefined_variables

        self._scope = "Template File"

    def render(self):
        """Renders the template file with jinja2"""

        Log.debug("Loading the context...")
        context = self.context.get()
        # add omit variable
        omit_placeholder = '__omit_place_holder__%s' % sha1(os.urandom(64)).hexdigest()
        context['omit'] = omit_placeholder

        Log.debug("Loading template file '{0}'...".format(self.path))
        file_content = self.read()

        env = jinja2.Environment(
            lstrip_blocks=True,
            trim_blocks=True,
            undefined=SilentUndefined if self.ignore_undefined_variables else jinja2.StrictUndefined,
        )

        # Register additional filters
        env.filters = merge_dicts(env.filters, jinja_filter.filters)

        # render file with jinja2
        try:
            Log.debug("Rendering template file...")
            rendered_file_content = env.from_string(
                file_content).render(context)
        except jinja_filter.MandatoryError as e:
            raise e
        except jinja2.UndefinedError as e:
            raise jinja2.exceptions.UndefinedError(
                self._format_error("Error while rendering template", "Variable {0}".format(str(e.message))))
        except jinja2.TemplateError as e:
            raise jinja2.exceptions.TemplateError(
                self._format_error("Error while rendering template", "Template error: {0}".format(str(e))))
        except Exception as e:
            raise Exception(self._format_error("Error while rendering template", "Error: {0}".format(str(e))))

        # remove values containing an omit placeholder
        try:
            processed_content = yaml.dump(
                self._remove_omit(
                    load_yaml(rendered_file_content, Loader=yaml.RoundTripLoader),
                    omit_placeholder
                ),
                indent=2,
                block_seq_indent=2,
                allow_unicode=True,
                default_flow_style=False,
                Dumper=yaml.RoundTripDumper
            )
        except Exception as e:
            raise Exception(self._format_error("Error while rendering template", str(e))).with_traceback(
                e.__traceback__)

        # Write rendered file
        self._write_rendered_file(processed_content)
        Log.info("Created file '{0}' from '{1}'".format(self.dest, self.path))

    def _remove_omit(self, value, omit_placeholder):
        if value is None:
            return None

        elif type(value) is str:
            if value.find(omit_placeholder) != -1:
                return Omit()
            else:
                return value

        # lists
        elif type(value) is yaml.comments.CommentedSeq:
            vlen = len(value)
            for i in range(vlen - 1, -1, -1):
                processed_item = self._remove_omit(value[i], omit_placeholder)
                if type(processed_item) is Omit:
                    del value[i]
                    i -= 1

        # dicts
        elif type(value) is yaml.comments.CommentedMap:
            for key in list(value.keys()):
                processed_value = self._remove_omit(value[key], omit_placeholder)
                if type(processed_value) is Omit:
                    del value[key]
            return value

        else:
            return value

    def _write_rendered_file(self, content):
        """ Writes the rendered content into the rendered file

        Args:
            content (str): Rendered content

        Raises:
            FileExistsError: If desired output file exists and overwriting is not enforced
            NotAFileError: If output path is not a file
            NotADirectoryError: If output directory for given path is not a directory

        """
        if os.path.exists(self.dest):
            if os.path.isfile(self.dest):
                if not self.force_overwrite:
                    raise IOError(self._format_error("Error writing file",
                                                     "Destination already exists. Use '-f' flag to overwrite the file".format(
                                                         self.dest)))
            else:
                raise IOError(self._format_error("Error writing file",
                                                 "Destination exists and is not a file".format(self.dest)))
        else:
            # create dir
            if os.path.dirname(self.dest):
                os.makedirs(os.path.dirname(self.dest), exist_ok=True)

        # write content to file
        Log.debug("Writing file to: {0}".format(self.dest))
        with io.open(self.dest, 'w', encoding='utf8') as f:
            f.write(content)

        # set file permissions
        if self.file_mode:
            Log.debug(
                "Setting file mode '{0}'...".format(self.file_mode))
            os.chmod(self.dest, int(self.file_mode, 8))


class Omit(object):
    pass


class AutoRenderer(object):

    def __index__(self):
        pass


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
    parser.add_argument('-i', '--ignore-undefined-variables', dest='ignore_undefined_variables',
                        action='store_true', default=None, help="Ignore undefined variables")
    parser.add_argument('-m', '--mode', dest='file_mode', default=None,
                        help="File mode for rendered files")
    parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                        default=0, help="Enable verbose mode (-vv for debug mode)")
    parser.add_argument('--version', action='version', version='Templer {0}, Jinja2 {1}'.format(
        __version__, jinja2.__version__), help="Prints the program version and quits")
    parser.add_argument('definition_files', nargs='+',
                        help="File that defines what to do.")
    args = parser.parse_args(sys.argv[1:])

    # initialize dumb logger
    levels = [Log.ERROR, Log.INFO, Log.DEBUG]
    Log.level = levels[min(len(levels) - 1, args.verbose)]

    try:
        if args.auto_render:
            raise NotImplementedError()
        else:
            render_failed = False
            for path in args.definition_files:
                df = DefinitionFile(
                    path=path,
                    file_mode=args.file_mode,
                    force_overwrite=args.force_overwrite,
                    ignore_undefined_variables=args.ignore_undefined_variables
                )
                df.parse()
                if not df.render_templates():
                    render_failed = True

            if render_failed:
                exit(1)

    except Exception as e:
        # catch errors and print to stderr
        if args.verbose >= 2:
            Log.error(traceback.format_exc())
        else:
            Log.error(str(e))
        exit(1)

    exit(0)
