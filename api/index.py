"""Vercel Serverless Function entrypoint for FastAPI backend."""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to Python path
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app

# Vercel ASGI handler
handler = app
