import os

from docker_compose_templer.event import Event
from docker_compose_templer.cached_file import CachedFile
from docker_compose_templer.jinja_renderer import JinjaRenderer
from docker_compose_templer.log import Log
from docker_compose_templer.utils import hash
from docker_compose_templer.utils import load_yaml


class ContextChainElement(object):
    """Represents a context chain element that is part of a ContextChain.

    Args:
        source (dict or CachedFile): Source of the context can either be a File or a dict
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
        if type(source) == CachedFile:
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
        parent_context = self.prev.get_context() if self.prev else {}
        if type(self.source) == CachedFile:
            file_content = self.source.read()
            try:
                self.cache = JinjaRenderer.render_dict_and_add_to_context(
                    load_yaml(file_content),
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

        self.cache_hash = hash(self.cache)
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
        if type(self.source) == CachedFile:
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
                source=CachedFile.get_file(path, self.watch_changes),
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

