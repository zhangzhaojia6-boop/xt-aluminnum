from __future__ import annotations

import argparse
import json
import os
from uuid import uuid4

import requests


def build_payload(*, text: str, dingtalk_user_id: str, dingtalk_union_id: str | None, trace_id: str) -> dict:
    payload = {
        "senderStaffId": dingtalk_user_id,
        "text": {"content": text},
        "agentCode": "factory_dispatch",
        "traceId": trace_id,
    }
    if dingtalk_union_id:
        payload["senderUnionId"] = dingtalk_union_id
    return payload


def mask_secret(value: str) -> str:
    clean = str(value or "")
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:4]}...{clean[-4:]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("HERMES_SMOKE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("HERMES_DINGTALK_INBOUND_TOKEN") or os.getenv("DINGTALK_INBOUND_TOKEN"))
    parser.add_argument("--user-id", default=os.getenv("HERMES_SMOKE_ROOT_OWNER_USER_ID"))
    parser.add_argument("--union-id", default=os.getenv("HERMES_SMOKE_ROOT_OWNER_UNION_ID", ""))
    parser.add_argument("--text", default="今天咋样")
    parser.add_argument("--trace-id", default=f"root-owner-smoke-{uuid4().hex}")
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("inbound token is required through --token or env")
    if not args.user_id:
        raise SystemExit("root owner DingTalk user_id is required through --user-id or env")

    url = args.base_url.rstrip("/") + "/api/v1/dingtalk/agent-inbound"
    payload = build_payload(
        text=args.text,
        dingtalk_user_id=args.user_id,
        dingtalk_union_id=args.union_id,
        trace_id=args.trace_id,
    )
    response = requests.post(
        url,
        headers={"x-dingtalk-inbound-token": args.token},
        json=payload,
        timeout=20,
    )
    result = {
        "url": url,
        "token": mask_secret(args.token),
        "trace_id": args.trace_id,
        "status_code": response.status_code,
        "response": response.json()
        if response.headers.get("content-type", "").startswith("application/json")
        else response.text,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    response.raise_for_status()


if __name__ == "__main__":
    main()
