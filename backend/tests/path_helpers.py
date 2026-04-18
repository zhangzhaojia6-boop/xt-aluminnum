from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(os.getenv('ALUMINUM_BYPASS_REPO_ROOT', BACKEND_ROOT)).resolve()
