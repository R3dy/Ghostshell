"""Mythic-side TEMPLATE for a ghostshell command.

Copy this file to `mythic/agent_functions/<your_command>.py` and rename the
classes to match your command. This is the operator-facing contract Mythic
uses to render the UI tasking form + route responses. The agent-side function
(agent_code/_template/hello.py) is where the tradecraft lives.

See docs/writing-a-command.md for the line-by-line walkthrough.
"""

from mythic_container.MythicCommandBase import (
    CommandBase, CommandAttributes, TaskArguments, CommandArgument,
    MythicTask, PTTaskMessageAllData, PTTaskProcessResponseMessageResponse,
    SupportedOS, BrowserScript, ParameterType,
)


class HelloArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        # one CommandArgument(...) per parameter; empty list = no-arg command
        self.args = []

    async def parse_arguments(self):
        # `hello` takes no arguments. For a command with args, parse
        # self.command_line and raise on bad input (see mythic_container docs).
        pass


class HelloCommand(CommandBase):
    cmd = "hello"                                      # the command name (must match the agent-side def)
    needs_admin = False
    help_cmd = "hello"                                 # what the operator types
    description = "<one-line description for the Mythic UI>"
    version = 1
    author = "@student"
    attackmapping = []                                 # MITRE ATT&CK technique IDs, e.g. ["T1057"]
    supported_ui_features = []
    argument_class = HelloArguments
    attributes = CommandAttributes(
        supported_python_versions=["Python 3"],
        supported_os=[SupportedOS.Linux, SupportedOS.Windows, SupportedOS.MacOS],
    )

    async def create_tasking(self, task: MythicTask) -> MythicTask:
        task.display_params = "Running hello"
        return task

    async def process_response(self, task: PTTaskMessageAllData, response) -> PTTaskProcessResponseMessageResponse:
        return PTTaskProcessResponseMessageResponse(TaskID=task.Task.ID, Success=True)
