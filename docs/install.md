# Install guide (instructor)

ghostshell installs into a running Mythic server. You need Mythic v3.3.x (see ADR-006 for the version pin).

## Option A: AWS Mythic AMI (fastest)

1. Launch the Mythic AMI in AWS (search the AWS Marketplace for "Mythic" or use the community AMI). Use a `t3.large` or larger.
   - **Security group:** open 7443 (Mythic HTTPS) + 22 (SSH) from your IP only.
   - **Write the instance ID to your tracking doc immediately** (Mythic test servers are billing leaks if left running — stop/terminate when done).
2. SSH in, wait for cloud-init to finish (the Mythic containers start automatically — check `sudo docker ps`).
3. Get the Mythic admin password: `sudo cat /opt/mythic/.env | grep MYTHIC_ADMIN_USER` + `MYTHIC_ADMIN_PASSWORD`.
4. Install ghostshell:
   ```bash
   cd /opt/mythic
   sudo ./mythic-cli install github https://github.com/R3dy/Ghostshell
   ```
5. Verify the `ghostshell` translator + the `http`/`dynamic_http` C2 profile containers are healthy:
   ```bash
   sudo ./mythic-cli status
   ```
6. Open `https://<instance-ip>:7443/`, log in, and confirm `ghostshell` appears in "Create Payload".

**Teardown:** when done, `aws ec2 terminate-instances --instance-ids <id>`. Never leave the AMI running between sessions.

## Option B: local Mythic (Docker)

1. Clone Mythic: `git clone https://github.com/its-afeature/Mythic && cd Mythic`
2. Install: `sudo ./install_docker_ubuntu.sh` (follow prompts)
3. Install ghostshell: `sudo ./mythic-cli install github https://github.com/R3dy/Ghostshell`
4. `sudo ./mythic-cli status` — confirm `ghostshell` is healthy.

## Troubleshooting

- **ghostshell not in the UI after install:** `sudo ./mythic-cli status` — if the `ghostshell` container is `unhealthy`, check `sudo docker logs mythic_ghostshell`. The most common cause is a `mythic_container` SDK version mismatch (ADR-006) — re-pull the ghostshell image after updating the SDK pin in the Dockerfile.
- **Build fails with "missing command files":** the translator couldn't find a selected command's `agent_code/<cmd>.py`. Ensure the file exists + the command name matches.
- **Callback never appears:** check the agent's stdout (`python3 payload.py`) for tracebacks; check the Mythic server is reachable from the lab VM (`curl -k https://<mythic-ip>:7443/`).

## Mythic version pin

ghostshell is tested against Mythic v3.3.x. The `mythic_container` SDK version is pinned in `Payload_Type/ghostshell/Dockerfile`. To upgrade ghostshell for a newer Mythic: update the SDK pin, re-verify the install + build + callback flow, bump the ghostshell version (ADR-004), and update the "Tested against" line in the README.
