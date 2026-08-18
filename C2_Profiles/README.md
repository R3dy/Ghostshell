# C2_Profiles

ghostshell uses Mythic's **built-in** C2 profiles — it does not ship custom profile packages. The agent-side adapters (`Payload_Type/ghostshell/ghostshell/agent_code/base_agent/c2/http.py` and `dynamic_http.py`) speak the wire protocol of Mythic's standard `http` and `dynamic_http` profiles.

When you install ghostshell in Mythic, ensure the built-in `http` and `dynamic_http` C2 profiles are also installed (they ship with Mythic by default; verify in the Mythic UI under "C2 Profiles").

To add a custom transport (e.g. a `tcp` exercise), a student subclasses `C2Adapter` (see `docs/writing-a-command.md`) — but that requires a matching Mythic-side C2 profile package, which is out of MVP scope (see `PARKING_LOT.md`).
