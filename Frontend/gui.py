"""GUI entry point — adds Backend and Frontend to sys.path, then launches the app."""

from __future__ import annotations

import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FRONTEND_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "Backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from app import SantoshApp  # noqa: E402

if __name__ == "__main__":
    SantoshApp().mainloop()
