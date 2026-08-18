"""ghostshell command-module TEMPLATE (agent-side).

Copy this file to `agent_code/<your_command>.py` and rename the function to
match your command name. The function name == the command name == the file
name (e.g. `hello.py` -> `def hello(self, task_id, **params)`).

See docs/writing-a-command.md for the 15-minute walkthrough.
"""


def hello(self, task_id, **params):
    """<one-line help string -- shows up in the Mythic UI>"""
    # stop-check: include this in any long-running command so the operator
    # can stop the task from the UI.
    if [t for t in self.taskings if t["task_id"] == task_id][0]["stopped"]:
        return "Job stopped."

    # Your tradecraft logic here. `self` is the GhostshellAgent instance --
    # see docs/module-interface.md for the full list of what you can call
    # (self.postMessageAndRetrieveResponse, self.sendTaskOutputUpdate, etc.).
    return "hello from ghostshell"
