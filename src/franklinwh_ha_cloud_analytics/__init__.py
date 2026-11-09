"""The FranklinWH cloud's energy reporting, shared by the FranklinWH bridges.

A bridge passes in its logged-in franklinwh-cloud client; :func:`fetch` makes the one
library call a period needs (cached), and :func:`build` turns the reply into the payload
the page panel in ``static/`` draws. The bridge keeps credentials, routes and storage.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from .payload import build
from .periods import PERIODS, Period, resolve
from .service import Cache, fetch

__version__ = "0.1.10"
__all__ = ["PERIODS", "Cache", "Period", "build", "fetch", "resolve", "static_dir"]


def static_dir() -> Path:
    """The folder a bridge serves at ``/cloud-analytics/`` (cloud-analytics.js and .css)."""
    return Path(str(resources.files(__package__) / "static"))
