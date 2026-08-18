"""ghostshell translator entry point.

Mythic runs this to start the translator container, which listens on Mythic's
RabbitMQ bus for payload-build requests and invokes Ghostshell.build().
"""
import mythic_container
from ghostshell.mythic import *  # noqa: F401,F403 -- registers the PayloadType + commands

mythic_container.mythic_service.start_and_run_forever()
