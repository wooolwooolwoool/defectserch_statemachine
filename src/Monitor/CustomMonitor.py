from .Monitor import Monitor

class CustomMonitor(Monitor):
    def __init__(self, category="custom"):
        super().__init__()
        self.category = category
        self.current_state = "unknown"
        self.register_check_state(category, self.check_state)

    def check_state(self, category):
        return self.current_state

    def set_state(self, category, value):
        self.current_state = value

