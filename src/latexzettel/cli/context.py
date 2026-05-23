# src/latexzettel/cli/context.py
from __future__ import annotations

from dataclasses import dataclass
from latexzettel.config.settings import Settings


@dataclass(frozen=True)
class CLIContext:
    """
    Contexto compartido entre comandos Click.

    settings:
      configuración ensamblada (paths, renderers, platform, etc.)
    """

    settings: Settings
