"""ghostshell Mythic command definitions.

Importing this package registers the payload type + its commands with Mythic
(the mythic_container SDK discovers CommandBase/PayloadType subclasses on
import). The builder (translator) + the three command defs are imported here.
"""

from .builder import Ghostshell  # noqa: F401 -- registers the PayloadType
from .ps import PsCommand  # noqa: F401
from .load import LoadCommand  # noqa: F401
from .unload import UnloadCommand  # noqa: F401

__all__ = ["Ghostshell", "PsCommand", "LoadCommand", "UnloadCommand"]
