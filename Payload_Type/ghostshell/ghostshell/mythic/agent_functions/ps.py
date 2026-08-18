"""Mythic-side definition for the ghostshell `ps` command.

This is the operator-facing contract Mythic uses to render the UI tasking form
+ route the agent's response. It's a thin scaffold over mythic_container's
CommandBase -- the agent-side function (agent_code/ps.py) is where the
tradecraft logic lives. Students copy this file as the template for a new
command's Mythic-side half (see docs/writing-a-command.md).
"""

from mythic_container.MythicCommandBase import (
    CommandBase, CommandAttributes, TaskArguments, MythicTask,
    PTTaskMessageAllData, PTTaskProcessResponseMessageResponse,
    SupportedOS, BrowserScript,
)
from mythic_container.MythicRPC import MythicRPC


class PsArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        # one CommandArgument(...) per parameter; empty list = no-arg command
        self.args = []

    async def parse_arguments(self):
        # `ps` takes no arguments, so nothing to parse. For a command with
        # args, parse self.command_line and raise on bad input (see the
        # mythic_container docs for the exact exception type).
        pass


class PsCommand(CommandBase):
    cmd = "ps"
    needs_admin = False
    help_cmd = "ps"
    description = "Get a limited process listing (pid, ppid, user, comm)."
    version = 1
    author = "@ghostshell"
    attackmapping = ["T1057"]  # MITRE ATT&CK: Process Discovery
    supported_ui_features = ["process_browser:list"]
    argument_class = PsArguments
    browser_script = BrowserScript(script_name="ps", author="@ghostshell", for_new_ui=True)
    attributes = CommandAttributes(
        supported_python_versions=["Python 3"],
        supported_os=[SupportedOS.Linux, SupportedOS.Windows, SupportedOS.MacOS],
    )

    async def create_tasking(self, task: MythicTask) -> MythicTask:
        task.display_params = "Getting process listing"
        return task

    async def process_response(self, task: PTTaskMessageAllData, response) -> PTTaskProcessResponseMessageResponse:
        return PTTaskProcessResponseMessageResponse(TaskID=task.Task.ID, Success=True)
