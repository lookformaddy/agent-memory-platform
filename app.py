"""Entrypoint for the optional FastAPI service.

Run:  uvicorn app:app --reload
Requires fastapi + uvicorn (see requirements.txt). The core package works
without them; this module simply re-exports the API app.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_memory.api import app  # noqa: E402,F401  (FastAPI required here)

__all__ = ["app"]
