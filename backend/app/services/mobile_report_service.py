from __future__ import annotations

import sys

from app.services import mobile_report as _mobile_report

sys.modules[__name__] = _mobile_report
setattr(sys.modules['app.services'], 'mobile_report_service', _mobile_report)
