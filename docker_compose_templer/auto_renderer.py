import time

from docker_compose_templer.cached_file import CachedFile
from docker_compose_templer.log import Log

import pyinotify


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
                for notifier in [f.notifier for _, f in CachedFile.files.items()]:
                    try:
                        if notifier.check_events():
                            notifier.read_events()
                            notifier.process_events()
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        break
                time.sleep(0.5)
            except KeyboardInterrupt:
                break

        Log.info("\nAuto renderer stopped")
