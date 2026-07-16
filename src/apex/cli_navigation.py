"""Professional workflow navigation for the Apex CLI."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from apex import __version__
from apex.config import load_settings


@dataclass(frozen=True)
class CommandRoute:
    source: str
    group: str
    name: str
    help: str


_ROUTES: tuple[CommandRoute