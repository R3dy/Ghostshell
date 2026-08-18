# Build a payload from the Mythic UI (walkthrough)

Once ghostshell is installed (see `install.md`), building a payload takes about 2 minutes.

## Steps

1. **Open the Mythic UI** -> log in -> select your operation.
2. Click **Create Payload** (top nav).
3. In the payload-type dropdown, select **ghostshell**.
4. The build form appears with these fields:
   - **Selected commands:** defaults to `load`, `unload`, `ps`. (These three are always included — `load`/`unload` so the agent stays extensible, `ps` as the example command.)
   - **Python version:** `Python 3` (the only option for MVP).
5. Under **C2 Profiles**, select **http** (or **dynamic_http** for the rotating-URI variant).
6. Set the C2 profile parameters:
   - **callback_host:** `https://<your-mythic-server-ip>:7443` (include the scheme + port).
   - **callback_port:** `7443` (or whatever your Mythic listens on).
   - **callback_interval:** `10` (seconds between beacons — set lower for the demo).
   - **callback_jitter:** `10` (percent jitter).
   - **AESPSK:** leave blank to let Mythic generate the encryption key (recommended); Mythic reports it back in the build response.
   - **post_uri / get_uri / query_path_name:** leave at Mythic's defaults (the agent reads them).
7. Click **Build**. The build takes <30s (the translator container concatenates the agent + commands + injects the params).
8. When the build succeeds, click **Download** to save `payload.py`.
9. Copy `payload.py` to your lab VM (the realhax range, a local Linux box, or any Python 3 host).
10. Run it:
    ```bash
    python3 payload.py
    ```
    The process does not return (it's beaconing). No traceback on stdout = success.
11. Back in the Mythic UI, within 2x the configured interval, a **callback** appears in the Callbacks view. The callback's agent is `ghostshell`, the host is your lab VM's hostname.

## Next: task a command

With the callback live, click it -> the interaction panel opens. Type `ps` in the task bar -> submit. Within one beacon interval, the task completes and the output panel shows a process listing (PID, PPID, USER, COMM).

## Try load/unload

1. Task `unload ps`. The task completes with "Unloaded command: ps".
2. Task `ps` again — it's rejected ("ps is not loaded").
3. Task `load ps` (Mythic stages the `ps` agent code as a file; the agent fetches + execs it). The task completes with "Loaded command: ps".
4. Task `ps` — it works again.

This load/unload cycle is the teaching centerpiece: the student watches a command appear and disappear from the agent's registry in real time.

## dynamic_http variant

Repeat the build with the **dynamic_http** C2 profile. Set `uris` to a JSON list like `["/api/v1", "/update", "/check"]`. The built agent rotates its POST URI across that list per beacon — visible in the Mythic server's HTTP access logs.
