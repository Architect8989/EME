class ActionExecutor:
    def execute(self, action):
        if not hasattr(action, "run") or not callable(action.run):
            raise TypeError("Action must implement run()")
        return action.run()
