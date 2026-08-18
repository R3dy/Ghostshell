"""ghostshell Mythic-side package (translator + command definitions).

Importing this package loads the PayloadType + CommandBase subclasses so the
mythic_container SDK discovers them via __subclasses__(). The agent_functions
package __init__ imports the builder + each command def, which loads them.
"""
from . import agent_functions  # noqa: F401 -- triggers class loading
from .agent_functions.builder import Ghostshell  # noqa: F401
from .agent_functions.ps import PsCommand  # noqa: F401
from .agent_functions.load import LoadCommand  # noqa: F401
from .agent_functions.unload import UnloadCommand  # noqa: F401
