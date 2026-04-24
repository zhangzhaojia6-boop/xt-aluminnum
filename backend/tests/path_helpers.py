from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ROOT = BACKEND_ROOT.parent if (BACKEND_ROOT.parent / 'frontend').exists() else BACKEND_ROOT
REPO_ROOT = Path(os.getenv('ALUMINUM_BYPASS_REPO_ROOT', DEFAULT_REPO_ROOT)).resolve()
