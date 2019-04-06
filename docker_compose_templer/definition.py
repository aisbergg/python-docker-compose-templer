import os

from docker_compose_templer.cached_file import CachedFile
from docker_compose_templer.context import ContextChain
from docker_compose_templer.log import Log
from docker_compose_templer.template import Template
from docker_compose_templer.utils import hash
from docker_compose_templer.utils import load_yaml


class Definition(object):
    """Resembles a definition file.

    Args:
        path (str): Path of the definition file
        force_overwrite (str): Force overwriting of existing files
        watch_changes (bool): Enable watching for file changes
    Attributes:
        force_overwrite (str): Force overwriting of existing files
        watch_changes (bool): Enable watching for file changes
        file (CachedFile): The definition file
        templates (dict): The loaded templates (SHA1 hashes are used as keys)
        changed_templates (list): List of templates that changed (only in auto render mode)
    """

    def __init__(self, path, force_overwrite=True, watch_changes=False):
        self.force_overwrite = force_overwrite
        self.watch_changes = watch_changes

        self.file = CachedFile.get_file(path, watch_changes)
        self.file.on_change_event += self._on_change
        self.templates = {}
        self.changed_templates = []

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
        templates = {}
        self.changed_templates = []

        file_content = self.file.read()
        file_content = load_yaml(file_content)
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

            thash = hash(global_options['include_vars'], global_options['vars'], template_options['include_vars'],
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
        CachedFile.cleanup_unused_files()

        self.templates = templates

    def _parse_variable_options(self, options):
        """Parses common options and sets defaults.

        Args:
            options: Options that need to be parsed

        Returns:
            dict: The parsed options
        """
        processed_options = {}

        if 'vars' in options:
            if type(options['vars']) is dict:
                processed_options['vars'] = options['vars']
            else:
                raise ValueError("Value of 'vars' must be of type dict")
        else:
            processed_options['vars'] = {}

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
