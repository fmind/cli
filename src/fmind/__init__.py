"""Read Médéric Hurier's (Fmind) portfolio from the terminal.

Every command renders https://www.fmind.dev/api/profile, so this package carries
no copy of its own and needs no release when the website changes.
"""

from importlib.metadata import version

__all__ = ["__version__"]

__version__ = version("fmind")
