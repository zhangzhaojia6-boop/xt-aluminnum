from __future__ import annotations

import sys

from app.services import work_order as _work_order

sys.modules[__name__] = _work_order
setattr(sys.modules['app.services'], 'work_order_service', _work_order)
