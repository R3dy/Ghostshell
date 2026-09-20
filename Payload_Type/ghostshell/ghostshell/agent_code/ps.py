"""ghostshell `ps` command (agent-side).

This is the example command students read first. Copy this file as the
template for a new command (see docs/writing-a-command.md).

Two things make `ps` special compared to a basic command:

1. **No subprocess.** It walks /proc directly (pure Python, in-process).
   Spawning `/bin/ps` is loud on an EDR's process-creation telemetry and
   pointless anyway -- everything `ps` reports comes from /proc. Also,
   the payload has no guarantee a `ps` binary exists (minimal containers,
   Windows). Everything here is stdlib.

2. **Structured output for Mythic's Process Browser.** Returning plain
   text renders only as task output. To populate Mythic's process
   browser (and get the unified per-host process list, hierarchy tree,
   and sortable table), the agent must return the special `processes`
   structure documented at docs.mythic-c2.net -> Process Browser. This
   command returns a *dict*:
       {"processes": {"host": ..., "os": ..., "processes": [...]}}
   The base agent detects a dict result with a "processes" key and
   spreads it into the post_response envelope instead of user_output
   (see base_agent/core.py). Browser scripts + Mythic server side both
   consume the structured form.
"""

import os


def ps(self, task_id, **params):
    """Get a process listing (pid, ppid, user, name, path, cmdline)."""
    # stop-check: if the operator clicked "stop" on this task, bail out early.
    # Every long-running command MUST poll this; a command that ignores the
    # stop flag can only be killed by terminating the agent.
    if [t for t in self.taskings if t["task_id"] == task_id][0]["stopped"]:
        return "Job stopped."

    try:
        processes = _ps_from_proc()
    except Exception as e:
        return "ps error: " + str(e)

    return {
        "processes": {
            "host": os.uname().nodename,
            "os": os.uname().sysname.lower(),
            "processes": processes,
        }
    }


def _ps_from_proc():
    """Process listing from /proc (Linux). Returns a list of process dicts
    in Mythic's process-browser format. Pure stdlib, no subprocess."""
    procs = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        p = _read_process(pid)
        if p is not None:
            procs.append(p)
    procs.sort(key=lambda p: p["process_id"])
    return procs


def _read_process(pid):
    """Read one process' info out of /proc. Returns None on race conditions
    (process exited mid-read) or unreadable entries (other-user processes
    under a hardened /proc)."""
    base = "/proc/" + pid

    # /proc/<pid>/stat: pid (comm) state ppid ... -- comm may contain spaces
    # and parens, so parse from the LAST '(' and split the remainder.
    try:
        with open(base + "/stat", "rb") as f:
            stat = f.read().decode("utf-8", "replace")
    except (OSError, ValueError):
        return None
    try:
        comm = stat[stat.index("(") + 1:stat.rindex(")")]
        fields = stat[stat.rindex(")") + 2:].split()
        ppid = int(fields[1])          # field 4 overall; 2 after state
        state = fields[0]
    except (ValueError, IndexError):
        return None

    proc = {
        "process_id": int(pid),
        "parent_process_id": ppid,
        "name": comm,
    }

    # /proc/<pid>/status: Uid line -> real uid; resolve to a name.
    uid = None
    try:
        with open(base + "/status") as f:
            for line in f:
                if line.startswith("Uid:"):
                    uid = int(line.split()[1])
                    break
    except (OSError, ValueError):
        pass
    if uid is not None:
        proc["user"] = _uid_to_name(uid)

    # bin_path + command_line: readlink /proc/<pid>/exe, read /proc/<pid>/cmdline.
    # Both need ptrace-style permission on the target -- unreadable for
    # other users' processes; omit the field rather than failing.
    try:
        proc["bin_path"] = os.readlink(base + "/exe")
    except OSError:
        pass
    try:
        with open(base + "/cmdline", "rb") as f:
            argv = f.read().split(b"\x00")
        argv = [a.decode("utf-8", "replace") for a in argv if a]
        proc["command_line"] = " ".join(argv) if argv else "[" + comm + "]"
    except OSError:
        pass

    # Kernel threads (state 'I'/'K' etc. with no cmdline) are noise but
    # still real processes -- keep them, just flag zombies so the operator
    # can filter. Extra fields land in Mythic's per-process "metadata".
    if state == "Z":
        proc["description"] = "zombie"

    return proc


def _uid_to_name(uid):
    """Resolve a uid to a username without pwd (works with hashed db-less
    containers too); falls back to the numeric uid."""
    try:
        import pwd  # stdlib on Unix; deferred import keeps Windows alive
        return pwd.getpwuid(uid).pw_name
    except Exception:
        return str(uid)
