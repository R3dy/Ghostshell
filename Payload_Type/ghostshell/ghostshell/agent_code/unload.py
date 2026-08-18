"""ghostshell `unload` command (agent-side).

The counterpart to `load`: remove a command from the running agent's registry
and tell Mythic it's no longer available. After `unload <cmd>`, the command
disappears from `help` and is not taskable.

Refuses to unload `load` or `unload` themselves -- the agent must always stay
extensible (otherwise a student could brick their callback with one command).
"""


def unload(self, task_id, **params):
    """Unload a command module from the running agent."""
    module = params.get("module") or params.get("command")

    if not module:
        return "unload error: no module specified"
    if module in ("load", "unload"):
        return "Cannot unload load/unload -- the agent must stay extensible."
    if module not in self.loaded_commands:
        return "'{}' is not loaded (nothing to unload).".format(module)

    self.loaded_commands.pop(module, None)
    self._notify_mythic_command("remove", module)
    return "Unloaded command: {}".format(module)
