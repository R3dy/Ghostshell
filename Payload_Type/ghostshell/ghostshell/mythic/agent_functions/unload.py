"""Mythic-side definition for the ghostshell `unload` command."""

from mythic_container.MythicCommandBase import (
    CommandBase, CommandAttributes, TaskArguments, CommandParameter,
    MythicTask, PTTaskMessageAllData, PTTaskProcessResponseMessageResponse,
    SupportedOS, ParameterType, ParameterGroupInfo,
)


class UnloadArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="module",
                type=ParameterType.String,
                description="The command module to unload from the agent.",
                parameter_group_info=[ParameterGroupInfo(required=True, group_name="Default")],
            ),
        ]

    async def parse_arguments(self):
        if self.command_line.startswith("{"):
            self.load_args_from_json_string(self.command_line)
        else:
            self.add_arg("module", self.command_line.strip(), ParameterType.String)


class UnloadCommand(CommandBase):
    cmd = "unload"
    needs_admin = False
    help_cmd = "unload <module>"
    description = "Unload a command module from the running agent. Refuses load/unload."
    version = 1
    author = "@ghostshell"
    attackmapping = []
    supported_ui_features = ["loaded_commands:unload"]
    argument_class = UnloadArguments
    attributes = CommandAttributes(
        supported_python_versions=["Python 3"],
        supported_os=[SupportedOS.Linux, SupportedOS.Windows, SupportedOS.MacOS],
    )

    async def create_tasking(self, task: MythicTask) -> MythicTask:
        module = task.args.get_arg("module") if task.args else self.command_line
        task.display_params = "Unloading module: {}".format(module)
        return task

    async def process_response(self, task: PTTaskMessageAllData, response) -> PTTaskProcessResponseMessageResponse:
        return PTTaskProcessResponseMessageResponse(TaskID=task.Task.ID, Success=True)
