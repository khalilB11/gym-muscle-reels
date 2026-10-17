"""PySide6 editor app (optional extra: pip install "musclereels[app]").

The editor is built in spec 002 Phase 3 (US1). Until then `launch` explains that.
"""
from __future__ import annotations

import sys


def launch(path: str | None = None) -> int:
    print("The editor app isn't built yet (spec 002, Phase 3). Use `musclereels render` for now.",
          file=sys.stderr)
    return 2
