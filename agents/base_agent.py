class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self._listeners = {}

    def log(self, message: str):
        print(f"[{self.name}] {message}")

    def on(self, event_name: str, callback):
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def emit(self, event_name: str, data=None):
        for callback in self._listeners.get(event_name, []):
            callback(data)
