"""Check or repair workshop binding for factory owner accounts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.exc import SQLAlchemyError

from app.database import get_sessionmaker
from app.services.config_readiness_service import build_owner_workshop_binding_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="专项 owner 账号车间绑定检查")
    parser.add_argument("--target-workshop-code", default="CPK", help="目标车间编码，默认 CPK")
    parser.add_argument("--apply", action="store_true", help="执行修复；默认只 dry-run")
    parser.add_argument("--json", dest="json_mode", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()

    sessionmaker = get_sessionmaker()
    try:
        with sessionmaker() as db:
            result = build_owner_workshop_binding_plan(
                db,
                target_workshop_code=args.target_workshop_code,
                apply=args.apply,
            )
            if args.apply and result["can_apply"]:
                db.commit()
    except SQLAlchemyError as exc:
        payload = {
            "ok": False,
            "code": "DATABASE_UNAVAILABLE",
            "message": f"owner 账号绑定检查无法连接数据库：{exc.__class__.__name__}",
            "suggestion": "请确认数据库已启动，且 .env 中数据库账号密码正确。",
        }
        if args.json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload["message"])
            print(f"处理建议：{payload['suggestion']}")
        return 3

    if args.json_mode:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"目标车间：{args.target_workshop_code}")
        print(f"模式：{'执行修复' if args.apply else 'dry-run'}")
        if result["blockers"]:
            print("阻断：")
            for item in result["blockers"]:
                print(f"- [{item['code']}] {item['message']}")
                print(f"  处理建议：{item['suggestion']}")
        if result["repairs"]:
            print("待处理账号：")
            for item in result["repairs"]:
                print(
                    f"- {item['username']}({item['name']}): "
                    f"{item['role']} -> {item['target_workshop_code']}"
                )
        else:
            print("专项 owner 账号车间绑定已就绪。")
        if result["applied"]:
            print(f"已修复：{result['applied_count']} 个账号")

    if result["blockers"]:
        return 2
    if result["needs_repair"] and not result["applied"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
