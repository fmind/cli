"""Read Médéric Hurier's (Fmind) portfolio and daily news from the terminal.

Every command renders live documents published by https://www.fmind.dev, so this
package carries no copy of its own and needs no release when the content changes.
"""

from typing import TYPE_CHECKING

__all__ = ["__version__"]

if TYPE_CHECKING:
    __version__: str


def __getattr__(name: str) -> str:
    """Resolve package version lazily so importing `fmind` skips `importlib.metadata`."""
    if name == "__version__":
        from importlib.metadata import version

        value = version("fmind")
        globals()["__version__"] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
