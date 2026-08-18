# Environment — ghostshell Experience Runner setup

For the S11 live-Mythic end-to-end verification (see `docs/03-solutioning/experience-script-s11.md`).

## How to run it locally / on AWS

### Mythic server
- **AWS AMI path (recommended):** launch the Mythic AMI (search AWS Marketplace / community AMIs for "Mythic"). `t3.large` minimum. SG: 7443 (HTTPS) + 22 (SSH) from your IP only. Write the instance ID to `PHASE_STATE.md` `infra_state` immediately on launch. Stop/terminate when done (billing leak risk).
- **Local Docker path:** `git clone https://github.com/its-afeature/Mythic && cd Mythic && sudo ./install_docker_ubuntu.sh`.
- **Ready signal:** `sudo ./mythic-cli status` reports all containers `healthy`; `curl -sk https://<ip>:7443/` returns the Mythic landing page.
- **Creds:** Mythic admin user/password from `/opt/mythic/.env` (AMI) or the install prompts (local).

### Install ghostshell + the C2 profiles
```bash
cd /opt/mythic  # (or your Mythic root)
sudo ./mythic-cli install github https://github.com/R3dy/Ghostshell
sudo ./mythic-cli status   # confirm ghostshell + http + dynamic_http are healthy
```

### mythic-mcp (programmatic tasking — optional but recommended)
Clone `R3dy/mythic-mcp`, configure `config.yaml` with the Mythic server IP/port/creds, run `python -m mythic_mcp --config ./config.yaml`. Use it to drive the install/build/callback/ps/unload/load flow without clicking the UI (see the S11 Experience Script scenarios).

### Lab VM (agent side)
- Python 3.8+ (the only dependency — the built payload is stdlib-only).
- Network reachability to the Mythic server on 7443.
- Run: `python3 payload.py` (the file downloaded from the Mythic UI's "Create Payload" flow).

## Teardown
```bash
aws ec2 terminate-instances --instance-ids <id-from-infra_state>
aws ec2 describe-instances --filters Name=tag:ghostshell,Values=true   # orphan check (zero running)
```
Update `PHASE_STATE.md` `infra_state` to reflect termination.
