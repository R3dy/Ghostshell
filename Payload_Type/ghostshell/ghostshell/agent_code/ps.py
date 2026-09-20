"""ghostshell `ps` command (agent-side).

This is the example command students read first. Copy this file as the
template for a new command (see docs/writing-a-command.md).

Two things make `ps` special compared to a basic command:

1. **No subprocess.** It enumerates processes in-process, platform-native:
     - Linux: walks /proc (stat, status, exe, cmdline)
     - Windows: Toolhelp32 snapshot via ctypes (kernel32)
     - macOS: libproc via ctypes (proc_listallpids + proc_pidpath)
   Spawning `/bin/ps` or `tasklist` is loud on EDR process-creation
   telemetry and pointless anyway -- everything they report is available
   in-process. Everything here is stdlib (os, ctypes, platform).

2. **Structured output for Mythic's Process Browser.** Returning plain
   text renders only as task output. To populate Mythic's process
   browser (unified per-host process list, hierarchy tree, sortable
   table), the agent must return the special `processes` structure
   documented at docs.mythic-c2.net -> Process Browser. This command
   returns a *dict*:
       {"processes": {"host": ..., "os": ..., "processes": [...]}}
   The base agent detects a dict result with a "processes" key and
   spreads it into the post_response envelope instead of user_output
   (see base_agent/core.py). Browser scripts + Mythic server side both
   consume the structured form.
"""

import os
import platform


def ps(self, task_id, **params):
    """Get a process listing (pid, ppid, user, name, path, cmdline)."""
    # stop-check: if the operator clicked "stop" on this task, bail out early.
    # Every long-running command MUST poll this; a command that ignores the
    # stop flag can only be killed by terminating the agent.
    if [t for t in self.taskings if t["task_id"] == task_id][0]["stopped"]:
        return "Job stopped."

    system = platform.system().lower()
    try:
        if system == "linux":
            processes = _ps_linux()
        elif system == "windows":
            processes = _ps_windows()
        elif system == "darwin":
            processes = _ps_macos()
        else:
            return "ps error: unsupported platform '{}'".format(system)
    except Exception as e:
        return "ps error: " + str(e)

    return {
        "processes": {
            "host": platform.node(),
            "os": "macos" if system == "darwin" else system,
            "processes": processes,
        }
    }


# ---- Linux: /proc ----

def _ps_linux():
    """Process listing from /proc. Returns a list of process dicts in
    Mythic's process-browser format. Pure stdlib, no subprocess."""
    procs = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        p = _linux_read_process(pid)
        if p is not None:
            procs.append(p)
    procs.sort(key=lambda p: p["process_id"])
    return procs


def _linux_read_process(pid):
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


# ---- Windows: Toolhelp32 snapshot via ctypes ----
#
# The win32 way to enumerate processes without WMI or a helper binary:
# CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS) walks the system's process
# list in kernel32. Structures come from tlhelp32.h. All user-mode,
# low-privilege calls -- PROCESS_QUERY_LIMITED_INFORMATION is enough for
# the image path, and system processes we can't open are simply omitted.

def _ps_windows():
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    MAX_PATH = 260

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * MAX_PATH),
        ]

    procs = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError("CreateToolhelp32Snapshot failed (err {})".format(ctypes.get_last_error()))
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            pid = entry.th32ProcessID
            proc = {
                "process_id": pid,
                "parent_process_id": entry.th32ParentProcessID,
                "name": entry.szExeFile,
                "command_line": entry.szExeFile,  # cmdline unavailable via Toolhelp; exe name is the honest floor
            }
            # Image path + user need an open handle -- skip on access denied
            # (system processes / protected processes).
            path = _windows_process_path(kernel32, pid)
            if path:
                proc["bin_path"] = path
                proc["command_line"] = path
            user = _windows_process_user(kernel32, advapi32, pid)
            if user:
                proc["user"] = user
            procs.append(proc)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)

    procs.sort(key=lambda p: p["process_id"])
    return procs


def _windows_process_path(kernel32, pid):
    """QueryFullProcessImageNameW with PROCESS_QUERY_LIMITED_INFORMATION
    (0x1000) -- the least-privileged access right that still returns the
    image path. Returns None if the process can't be opened."""
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(handle)


def _windows_process_user(kernel32, advapi32, pid):
    """Owner of the process primary token: OpenProcessToken -> GetTokenInformation
    (TokenUser) -> LookupAccountSidW. All low-privilege; returns 'DOMAIN\\\\user'
    or just 'user', or None on access denied."""
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TOKEN_QUERY = 0x0008
    TokenUser = 1

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(handle, TOKEN_QUERY, ctypes.byref(token)):
            return None
        try:
            # Two-call pattern: first call fails with the needed size.
            needed = wintypes.DWORD()
            advapi32.GetTokenInformation(token, TokenUser, None, 0, ctypes.byref(needed))
            if not needed.value:
                return None
            buf = ctypes.create_string_buffer(needed.value)
            if not advapi32.GetTokenInformation(token, TokenUser, buf, needed.value, ctypes.byref(needed)):
                return None
            # TOKEN_USER = SID_AND_ATTRIBUTES { PSID Sid; DWORD Attributes; }
            sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
            name_len = wintypes.DWORD(256)
            dom_len = wintypes.DWORD(256)
            name = ctypes.create_unicode_buffer(name_len.value)
            domain = ctypes.create_unicode_buffer(dom_len.value)
            use = wintypes.DWORD()
            if not advapi32.LookupAccountSidW(None, ctypes.c_void_p(sid), name,
                                              ctypes.byref(name_len), domain,
                                              ctypes.byref(dom_len), ctypes.byref(use)):
                # Resolvable-but-odd SIDs fall back to the string form.
                sid_str = ctypes.create_unicode_buffer(128)
                if advapi32.ConvertSidToStringSidW(ctypes.c_void_p(sid), ctypes.byref(sid_str)):
                    return sid_str.value
                return None
            if domain.value:
                return "{}\\\\{}".format(domain.value, name.value)
            return name.value
        finally:
            kernel32.CloseHandle(token)
    finally:
        kernel32.CloseHandle(handle)


# ---- macOS: libproc via ctypes ----
#
# macOS has no /proc. libproc.dylib exposes proc_listallpids (the pid
# array) and proc_pidinfo(PROC_PIDTBSDINFO) for per-pid ownership.
# proc_pidpath gives the image path. All non-privileged calls.

def _ps_macos():
    import ctypes
    import ctypes.util

    libproc = ctypes.CDLL(ctypes.util.find_library("libproc") or "libproc.dylib")
    libproc.proc_listallpids.restype = ctypes.c_int
    libproc.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
    libproc.proc_pidpath.restype = ctypes.c_int
    libproc.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]

    # Count, then fetch (two-call pattern, same as GetTokenInformation).
    n = libproc.proc_listallpids(None, 0)
    if n <= 0:
        return []
    buf = (ctypes.c_int * (n * 2))()  # over-allocate; list may grow between calls
    n = libproc.proc_listallpids(buf, ctypes.sizeof(buf))
    if n <= 0:
        return []

    MAXCOMLEN = 16
    MAXPATHLEN = 1024

    # struct proc_bsdinfo (libproc.h): the fields we care about are
    # pbi_pid/pbi_ppid (offset 16), pbi_uid (offset 24), pbi_comm[16]
    # (offset 64), pbi_name[32] (offset 80). Define the head of the
    # struct; proc_pidinfo fills whatever size we hand it.
    class proc_bsdinfo_head(ctypes.Structure):
        _fields_ = [
            ("pbi_flags", ctypes.c_uint32),
            ("pbi_status", ctypes.c_uint32),
            ("pbi_xstatus", ctypes.c_uint32),
            ("pbi_pid", ctypes.c_uint32),
            ("pbi_ppid", ctypes.c_uint32),
            ("pbi_uid", ctypes.c_uint32),
            ("pbi_gid", ctypes.c_uint32),
            ("pbi_ruid", ctypes.c_uint32),
            ("pbi_rgid", ctypes.c_uint32),
            ("pbi_svuid", ctypes.c_uint32),
            ("pbi_svgid", ctypes.c_uint32),
            ("rfu_1", ctypes.c_uint32),
            ("pbi_comm", ctypes.c_char * MAXCOMLEN),
            ("pbi_name", ctypes.c_char * 32),
        ]

    libproc.proc_pidinfo.restype = ctypes.c_int
    libproc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                     ctypes.c_void_p, ctypes.c_int]
    PROC_PIDTBSDINFO = 1

    procs = []
    for i in range(n):
        pid = buf[i]
        proc = {"process_id": pid}
        info = proc_bsdinfo_head()
        if libproc.proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, ctypes.byref(info),
                                ctypes.sizeof(info)) == ctypes.sizeof(info):
            proc["parent_process_id"] = info.pbi_ppid
            proc["name"] = (info.pbi_name or info.pbi_comm).decode("utf-8", "replace").strip("\x00") or str(pid)
            proc["user"] = _uid_to_name(info.pbi_uid)
        else:
            # Inaccessible pid (e.g. kernel tasks) -- name unknown.
            proc["name"] = str(pid)
            proc["parent_process_id"] = 0
        path = ctypes.create_string_buffer(MAXPATHLEN)
        if libproc.proc_pidpath(pid, path, MAXPATHLEN) > 0:
            proc["bin_path"] = path.value.decode("utf-8", "replace")
        procs.append(proc)

    procs.sort(key=lambda p: p["process_id"])
    return procs
