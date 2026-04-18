"""试点前配置自检脚本。

用于在现场试点前快速检查关键配置是否齐全，避免出现无法上报、
应报清单失真或账号归属异常。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.exc import SQLAlchemyError

from app.database import get_sessionmaker
from app.services.config_readiness_service import inspect_pilot_config


def _parse_date(raw: str | None) -> date:
    """解析命令行日期参数。"""

    if not raw:
        return date.today()
    return datetime.strptime(raw, "%Y-%m-%d").date()


def main() -> int:
    """执行配置自检并输出结果。"""

    parser = argparse.ArgumentParser(description="试点前配置自检")
    parser.add_argument("--date", dest="target_date", help="检查日期，格式 YYYY-MM-DD，默认今天")
    parser.add_argument("--json", dest="json_mode", action="store_true", help="以 JSON 输出完整结果")
    args = parser.parse_args()

    target_date = _parse_date(args.target_date)
    sessionmaker = get_sessionmaker()
    try:
        with sessionmaker() as db:
            result = inspect_pilot_config(db, target_date=target_date)
    except SQLAlchemyError as exc:
        error_text = f"配置自检无法连接数据库：{exc.__class__.__name__}"
        payload = {
            "target_date": target_date.isoformat(),
            "hard_gate_passed": False,
            "hard_issues": [
                {
                    "level": "hard",
                    "code": "DATABASE_UNAVAILABLE",
                    "message": error_text,
                    "suggestion": "请确认数据库已启动，且 .env 中数据库账号密码正确。",
                }
            ],
            "warning_issues": [],
            "stats": {},
        }
        if args.json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(error_text)
            print("处理建议：请确认数据库已启动，且 .env 中数据库账号密码正确。")
        return 3

    if args.json_mode:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"配置检查日期：{result['target_date']}")
        print(f"硬门槛是否通过：{'是' if result['hard_gate_passed'] else '否'}")
        print("统计信息：")
        for key, value in result["stats"].items():
            print(f"- {key}: {value}")
        if result["hard_issues"]:
            print("\n硬门槛问题：")
            for item in result["hard_issues"]:
                print(f"- [{item['code']}] {item['message']}")
                print(f"  处理建议：{item['suggestion']}")
                if item.get("sample"):
                    print(f"  示例：{', '.join(item['sample'])}")
        if result["warning_issues"]:
            print("\n建议修复问题：")
            for item in result["warning_issues"]:
                print(f"- [{item['code']}] {item['message']}")
                print(f"  处理建议：{item['suggestion']}")
                if item.get("sample"):
                    print(f"  示例：{', '.join(item['sample'])}")

    return 0 if result["hard_gate_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
