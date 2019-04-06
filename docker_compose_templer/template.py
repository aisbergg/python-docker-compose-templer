import os

from docker_compose_templer.cached_file import CachedFile
from docker_compose_templer.jinja_renderer import JinjaRenderer
from docker_compose_templer.log import Log
from docker_compose_templer.utils import dump_yaml
from docker_compose_templer.utils import load_yaml


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
        _file (CachedFile): The template file

    """

    def __init__(self, src, dest, relative_path, context, force_overwrite=False, watch_changes=False):
        self.src = src
        self.dest = dest
        self.relative_path = relative_path
        self.context = context
        self.force_overwrite = force_overwrite
        self.watch_changes = watch_changes

        self._file = CachedFile.get_file(self._create_path(self.src), self.watch_changes)
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
            self._file = CachedFile.get_file(path, self.watch_changes)
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
            processed_content = dump_yaml(JinjaRenderer.remove_omit_from_dict(
                load_yaml(rendered_file_content, safe=False)))

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
