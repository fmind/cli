"""Read Médéric Hurier's (Fmind) portfolio and daily news from the terminal.

Every command renders live documents published by https://www.fmind.dev, so this
package carries no copy of its own and needs no release when the content changes.
"""

from importlib.metadata import version

__all__ = ["__version__"]

__version__ = version("fmind")
