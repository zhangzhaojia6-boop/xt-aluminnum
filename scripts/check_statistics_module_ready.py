"""Repo-root compatibility wrapper for the backend readiness checker."""

from __future__ import annotations

import runpy
import sys
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / 'backend'
BACKEND_SCRIPT = BACKEND_ROOT / 'scripts' / 'check_statistics_module_ready.py'

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.chdir(BACKEND_ROOT)
runpy.run_path(str(BACKEND_SCRIPT), run_name='__main__')
