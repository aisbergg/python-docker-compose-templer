import io
import os

from docker_compose_templer.event import Event
from docker_compose_templer.log import Log
from docker_compose_templer.utils import hash


class CachedFile(object):
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
    files = {}

    def __init__(self, path, watch_changes=False):
        self.path = path

        self.cache = None
        self.on_change_event = Event()
        self.notifier = None
        if watch_changes:
            import pyinotify
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
            self.cache = {}

            if not self.exists():
                raise FileNotFoundError("File does not exist: '{0}'".format(self.path))
            if not os.path.isfile(self.path):
                raise IOError("Is not a file: '{0}".format(self.path))

            Log.debug("Loading file '{0}'...".format(self.path))
            with io.open(self.path, 'r', encoding='utf8') as f:
                file_content = f.read()

            self.cache['path'] = self.path
            self.cache['content'] = file_content
            self.cache['hash'] = hash(file_content)
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
            CachedFile: An instance of File with the given path
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
