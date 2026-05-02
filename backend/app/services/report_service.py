from __future__ import annotations

import sys

from app.services import report as _report

sys.modules[__name__] = _report
setattr(sys.modules['app.services'], 'report_service', _report)
