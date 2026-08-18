"""ghostshell `ps` command (agent-side).

This is the example command students read first. It's deliberately short: run
`ps`, return the listing, check the stop flag. Copy this file as the template
for a new command (see docs/writing-a-command.md).
"""

import subprocess


def ps(self, task_id, **params):
    """Get a limited process listing (pid, ppid, user, comm)."""
    # stop-check: if the operator clicked "stop" on this task, bail out early.
    # Every long-running command MUST poll this; a command that ignores the
    # stop flag can only be killed by terminating the agent.
    if [t for t in self.taskings if t["task_id"] == task_id][0]["stopped"]:
        return "Job stopped."

    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid,user,comm"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return "ps failed: " + out.stderr
        return out.stdout
    except FileNotFoundError:
        # Windows / minimal containers without `ps` -- fall back to /proc.
        return _ps_from_proc()
    except subprocess.TimeoutExpired:
        return "ps timed out"
    except Exception as e:
        return "ps error: " + str(e)


def _ps_from_proc():
    """Fallback process listing from /proc (Linux without the `ps` binary)."""
    import os
    lines = ["  PID  PPID USER              COMM"]
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open("/proc/{}/stat".format(pid)) as f:
                    stat = f.read().split()
                comm = stat[1].strip("()")
                ppid = stat[3]
                with open("/proc/{}/status".format(pid)) as f:
                    uid_line = [l for l in f if l.startswith("Uid:")]
                uid = uid_line[0].split()[1] if uid_line else "?"
                lines.append("{:>5} {:>6} {:<16}  {}".format(pid, ppid, uid, comm))
            except Exception:
                continue
    except Exception as e:
        return "ps_from_proc error: " + str(e)
    return "\n".join(lines)
