"""Mythic-side definition for the ghostshell `load` command.

`load` presents only compatible commands (via supported_python_versions /
supported_os attributes + MythicRPC get_callback_commands) for loading into a
live callback. When tasked, Mythic stages the selected command's agent code as
a chunked file and the task parameters carry the file_id + module name.
"""

from mythic_container.MythicCommandBase import (
    CommandBase, CommandAttributes, TaskArguments, CommandArgument,
    MythicTask, PTTaskMessageAllData, PTTaskProcessResponseMessageResponse,
    SupportedOS, BrowserScript, ParameterType,
)
from mythic_container.MythicRPC import MythicRPC


class LoadArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandArgument(
                name="module",
                type=ParameterType.String,
                description="The command module to load into the agent.",
                parameter_group_info=[{"group_name": "Default", "required": True}],
            ),
            CommandArgument(
                name="file_id",
                type=ParameterType.File,
                description="Mythic-staged file id of the command's agent code.",
                parameter_group_info=[{"group_name": "Default", "required": True}],
            ),
        ]

    async def parse_arguments(self):
        if self.command_line.startswith("{"):
            await self.load_args_from_json_string(self.command_line)
        else:
            # tolerate "load <module>" typed at the prompt
            await self.add_arg("module", self.command_line.strip(), ParameterType.String)


class LoadCommand(CommandBase):
    cmd = "load"
    needs_admin = False
    help_cmd = "load <module>"
    description = "Load a command module into the running agent."
    version = 1
    author = "@ghostshell"
    attackmapping = ["T1129"]  # MITRE ATT&CK: Shared Modules
    supported_ui_features = ["loaded_commands:load"]
    argument_class = LoadArguments
    attributes = CommandAttributes(
        supported_python_versions=["Python 3"],
        supported_os=[SupportedOS.Linux, SupportedOS.Windows, SupportedOS.MacOS],
    )

    async def create_tasking(self, task: MythicTask) -> MythicTask:
        module = task.args.get_arg("module") if task.args else self.command_line
        task.display_params = "Loading module: {}".format(module)
        return task

    async def process_response(self, task: PTTaskMessageAllData, response) -> PTTaskProcessResponseMessageResponse:
        return PTTaskProcessResponseMessageResponse(TaskID=task.Task.ID, Success=True)
