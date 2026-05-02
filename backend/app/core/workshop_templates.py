from __future__ import annotations

import sys

from app.core import templates as _templates

sys.modules[__name__] = _templates
setattr(sys.modules['app.core'], 'workshop_templates', _templates)
