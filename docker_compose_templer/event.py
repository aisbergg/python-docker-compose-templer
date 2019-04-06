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
