from __future__ import annotations

from pathlib import Path
import runpy


BACKEND_SCRIPT = Path(__file__).resolve().parents[1] / 'backend' / 'scripts' / 'configure_zzj_custom_robot_channels.py'


if __name__ == '__main__':
    runpy.run_path(str(BACKEND_SCRIPT), run_name='__main__')
