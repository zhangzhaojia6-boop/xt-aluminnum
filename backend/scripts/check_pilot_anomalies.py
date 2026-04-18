"""试点异常检查脚本。
用于现场值班快速查看当日异常清单与摘要。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.anomaly_detection_service import detect_daily_anomalies


def _parse_date(value: str | None) -> date:
    """解析日期参数。"""

    text = (value or "").strip()
    if not text:
        return date.today()
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必须为 YYYY-MM-DD") from exc


def main() -> int:
    """执行异常检查。"""

    parser = argparse.ArgumentParser(description="试点异常检查")
    parser.add_argument("--date", type=_parse_date, default=date.today(), help="统计日期，默认今天")
    parser.add_argument("--workshop-id", type=int, default=None, help="按车间过滤")
    parser.add_argument("--json", dest="json_mode", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    sessionmaker = get_sessionmaker()
    try:
        with sessionmaker() as db:
            payload = detect_daily_anomalies(db, target_date=args.date, workshop_id=args.workshop_id)
    except SQLAlchemyError as exc:
        error_payload = {
            "status": "error",
            "code": "DATABASE_UNAVAILABLE",
            "message": f"无法连接数据库：{exc.__class__.__name__}",
            "suggestion": "请确认数据库已启动，且 .env 中数据库账号密码正确。",
        }
        if args.json_mode:
            print(json.dumps(error_payload, ensure_ascii=False, indent=2))
        else:
            print(error_payload["message"])
            print(error_payload["suggestion"])
        return 3

    if args.json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload.get("summary", {})
        print(f"日期：{payload.get('date')}")
        print(f"异常总数：{summary.get('total', 0)}")
        print(f"摘要：{summary.get('digest', '未发现关键异常')}")
        items = payload.get("items", [])
        for index, item in enumerate(items[:20], start=1):
            print(
                f"{index}. [{item.get('severity')}] {item.get('label')} | "
                f"车间={item.get('workshop_id')} 班次={item.get('shift_id')} | {item.get('detail')}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())

