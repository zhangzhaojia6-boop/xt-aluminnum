"""企业微信账号映射批量检查脚本。

用于试点前批量核对企业微信账号能否稳定映射到系统用户。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.wecom_mapping_service import resolve_wecom_user


def _read_userids(file_path: Path) -> list[str]:
    """读取待检查的企业微信账号列表。"""

    rows: list[str] = []
    for raw in file_path.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        rows.append(text.split(",")[0].strip())
    return rows


def main() -> int:
    """执行批量映射检查。"""

    parser = argparse.ArgumentParser(description="企业微信账号映射批量检查")
    parser.add_argument("--input", required=True, help="账号清单文件（每行一个企业微信账号，支持注释行 #）")
    parser.add_argument("--json", dest="json_mode", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"输入文件不存在：{input_path}")
        return 2

    userids = _read_userids(input_path)
    if not userids:
        print("输入文件没有可检查的账号。")
        return 2

    sessionmaker = get_sessionmaker()
    try:
        with sessionmaker() as db:
            results = []
            for item in userids:
                mapping = resolve_wecom_user(db, wecom_userid=item)
                results.append(
                    {
                        "wecom_userid": item,
                        "status": mapping.status,
                        "matched_by": mapping.matched_by,
                        "user_id": mapping.user.id if mapping.user else None,
                        "username": mapping.user.username if mapping.user else None,
                        "display_name": mapping.user.name if mapping.user else None,
                        "conflicts": [user.username for user in mapping.conflicts],
                    }
                )
    except SQLAlchemyError as exc:
        payload = {
            "status": "error",
            "code": "DATABASE_UNAVAILABLE",
            "message": f"无法连接数据库：{exc.__class__.__name__}",
            "suggestion": "请确认数据库已启动，且 .env 中数据库账号密码正确。",
        }
        if args.json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload["message"])
            print(f"处理建议：{payload['suggestion']}")
        return 3

    stats = {
        "total": len(results),
        "matched": len([item for item in results if item["status"] == "matched"]),
        "not_found": len([item for item in results if item["status"] == "not_found"]),
        "inactive": len([item for item in results if item["status"] == "inactive"]),
        "ambiguous": len([item for item in results if item["status"] == "ambiguous"]),
        "invalid": len([item for item in results if item["status"] == "invalid"]),
    }
    all_passed = stats["matched"] == stats["total"]
    payload = {
        "all_passed": all_passed,
        "stats": stats,
        "items": results,
    }

    if args.json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"总数：{stats['total']}，可映射：{stats['matched']}")
        print(
            "失败明细："
            f"未匹配 {stats['not_found']}，停用 {stats['inactive']}，冲突 {stats['ambiguous']}，无效 {stats['invalid']}"
        )
        for item in results:
            if item["status"] == "matched":
                continue
            print(f"- {item['wecom_userid']}: {item['status']}")
            if item["conflicts"]:
                print(f"  冲突账号：{', '.join(item['conflicts'])}")

    return 0 if all_passed else 2


if __name__ == "__main__":
    sys.exit(main())
