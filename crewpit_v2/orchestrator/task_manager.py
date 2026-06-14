class TaskManager:
    def __init__(self, steps):
        self.steps = steps
        self.current = 0

    def has_next(self):
        return self.current < len(self.steps)

    def get_next(self):
        step = self.steps[self.current]
        self.current += 1
        return step