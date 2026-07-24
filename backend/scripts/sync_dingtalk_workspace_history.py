from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TextIO
from zoneinfo import ZoneInfo

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_sessionmaker
from app.models.agent_communication import MultimodalEvidence
from scripts.dingtalk_real_fact_backfill import run_backfill

FILE_MESSAGE_RE = re.compile(
    r"^\[文件\]\s+(?P<name>.+?)\s+fileId:\s*(?P<file_id>\S+)(?:\s+注意：.*)?$",
    re.DOTALL,
)
IMAGE_MESSAGE_RE = re.compile(r"^\[图片消息\]\(mediaId=(?P<media_id>[^)]+)\)")
DEFAULT_IGNORED_SENDERS = {"鑫泰hermes"}


class DingTalkWorkspaceSyncError(RuntimeError):
    pass


class DingTalkWorkspaceClient:
    def __init__(self, dws_bin: str = "dws") -> None:
        self.dws_bin = shutil.which(dws_bin) or dws_bin

    def list_messages(
        self,
        *,
        start: datetime,
        end: datetime,
        limit: int = 50,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        cursor = "0"
        messages: list[dict[str, Any]] = []
        for _page in range(max(1, max_pages)):
            payload = self._run_json(
                [
                    "chat",
                    "message",
                    "list-all",
                    "--start",
                    start.strftime("%Y-%m-%d %H:%M:%S"),
                    "--end",
                    end.strftime("%Y-%m-%d %H:%M:%S"),
                    "--limit",
                    str(max(1, min(int(limit), 50))),
                    "--cursor",
                    cursor,
                ]
            )
            result = payload.get("result")
            if not isinstance(result, Mapping):
                raise DingTalkWorkspaceSyncError("dws_list_result_missing")
            messages.extend(_flatten_conversation_messages(result))
            if not bool(result.get("hasMore")):
                return messages
            next_cursor = str(result.get("nextCursor") or "").strip()
            if not next_cursor or next_cursor == cursor:
                raise DingTalkWorkspaceSyncError("dws_list_cursor_invalid")
            cursor = next_cursor
        raise DingTalkWorkspaceSyncError("dws_list_page_limit_exceeded")

    def download_file(self, *, file_id: str, output_path: Path) -> None:
        self._run(
            [
                "drive",
                "download",
                "--node",
                file_id,
                "--output",
                str(output_path),
            ]
        )
        if not output_path.is_file():
            raise DingTalkWorkspaceSyncError("dws_file_download_missing")

    def download_image(
        self,
        *,
        media_id: str,
        message_id: str,
        conversation_id: str,
        output_path: Path,
    ) -> None:
        self._run(
            [
                "chat",
                "message",
                "download-media",
                "--type",
                "mediaId",
                "--resource-id",
                media_id,
                "--message-id",
                message_id,
                "--open-conversation-id",
                conversation_id,
                "--output",
                str(output_path),
            ]
        )
        if not output_path.is_file():
            raise DingTalkWorkspaceSyncError("dws_image_download_missing")

    def _run_json(self, args: list[str]) -> dict[str, Any]:
        completed = self._run(args)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DingTalkWorkspaceSyncError("dws_json_invalid") from exc
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise DingTalkWorkspaceSyncError("dws_command_failed")
        return payload

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self.dws_bin, *args, "--format", "json"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise DingTalkWorkspaceSyncError("dws_command_failed") from exc


def _flatten_conversation_messages(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    conversations = result.get("conversationMessagesList")
    if not isinstance(conversations, list):
        return []
    rows: list[dict[str, Any]] = []
    for conversation in conversations:
        if not isinstance(conversation, Mapping):
            continue
        conversation_id = str(conversation.get("openConversationId") or "").strip()
        messages = conversation.get("messages")
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, Mapping):
                continue
            row = dict(message)
            row.setdefault("openConversationId", conversation_id)
            row.setdefault("conversationTitle", conversation.get("title"))
            row.setdefault("singleChat", bool(conversation.get("singleChat")))
            rows.append(row)
    return rows


def load_existing_message_ids(*, limit: int = 5000) -> set[str]:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        rows = (
            db.query(MultimodalEvidence.payload)
            .order_by(MultimodalEvidence.id.desc())
            .limit(max(1, int(limit)))
            .all()
        )
    result: set[str] = set()
    for row in rows:
        payload = row[0] if isinstance(row, tuple) else getattr(row, "payload", row)
        if not isinstance(payload, Mapping):
            continue
        message_id = str(payload.get("message_id") or payload.get("messageId") or "").strip()
        if message_id:
            result.add(message_id)
    return result


def prepare_backfill_rows(
    messages: list[Mapping[str, Any]],
    *,
    files_root: Path,
    client: DingTalkWorkspaceClient,
    existing_message_ids: set[str] | None = None,
    ignored_sender_names: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    existing_ids = set(existing_message_ids or set())
    ignored_names = {item.strip().casefold() for item in (ignored_sender_names or DEFAULT_IGNORED_SENDERS) if item.strip()}
    downloads_root = files_root / "downloads"
    downloads_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    summary = {
        "listed": len(messages),
        "prepared": 0,
        "skipped_existing": 0,
        "skipped_self": 0,
        "skipped_invalid": 0,
        "downloaded": 0,
        "download_failures": 0,
    }

    for message in messages:
        message_id = _first_text(message.get("openMessageId"), message.get("messageId"), message.get("msgId"))
        conversation_id = _first_text(message.get("openConversationId"), message.get("conversationId"))
        sender_name = _first_text(message.get("sender"), message.get("senderName"))
        if sender_name and sender_name.casefold() in ignored_names:
            summary["skipped_self"] += 1
            continue
        if not message_id or not conversation_id:
            summary["skipped_invalid"] += 1
            continue
        if message_id in existing_ids or message_id in seen_ids:
            summary["skipped_existing"] += 1
            continue
        seen_ids.add(message_id)

        content = str(message.get("content") or "").strip()
        base_row = {
            "openConversationId": conversation_id,
            "messageId": message_id,
            "senderOpenDingTalkId": _first_text(message.get("senderOpenDingTalkId")),
            "senderName": sender_name,
            "createTime": _first_text(message.get("createTime")),
            "conversationType": "private" if bool(message.get("singleChat")) else "group",
        }
        file_match = FILE_MESSAGE_RE.match(content)
        image_match = IMAGE_MESSAGE_RE.match(content)
        try:
            if file_match:
                file_name = file_match.group("name").strip()
                file_id = file_match.group("file_id").strip()
                local_path = downloads_root / f"{_message_digest(message_id)}-{_safe_file_name(file_name)}"
                client.download_file(file_id=file_id, output_path=local_path)
                rows.append(
                    {
                        **base_row,
                        "fileName": file_name,
                        "fileId": file_id,
                        "localFilePath": local_path.relative_to(files_root).as_posix(),
                    }
                )
                summary["downloaded"] += 1
            elif image_match:
                media_id = image_match.group("media_id").strip()
                local_path = downloads_root / f"{_message_digest(message_id)}-image.png"
                client.download_image(
                    media_id=media_id,
                    message_id=message_id,
                    conversation_id=conversation_id,
                    output_path=local_path,
                )
                rows.append(
                    {
                        **base_row,
                        "fileName": "image.png",
                        "fileId": media_id,
                        "localFilePath": local_path.relative_to(files_root).as_posix(),
                    }
                )
                summary["downloaded"] += 1
            elif content:
                rows.append({**base_row, "content": content})
            else:
                summary["skipped_invalid"] += 1
                continue
        except DingTalkWorkspaceSyncError:
            summary["download_failures"] += 1
            continue
        summary["prepared"] += 1
    return rows, summary


def sync_workspace_history(
    *,
    client: DingTalkWorkspaceClient,
    end: datetime,
    lookback_minutes: int,
    max_pages: int,
) -> dict[str, Any]:
    start = end - timedelta(minutes=max(1, int(lookback_minutes)))
    messages = client.list_messages(start=start, end=end, max_pages=max_pages)
    existing_ids = load_existing_message_ids()
    with tempfile.TemporaryDirectory(prefix="xintai-dingtalk-workspace-") as temp_dir:
        root = Path(temp_dir)
        rows, summary = prepare_backfill_rows(
            messages,
            files_root=root,
            client=client,
            existing_message_ids=existing_ids,
        )
        backfill_summary: dict[str, Any] = {
            "accepted": 0,
            "duplicates": 0,
            "rejected": 0,
            "file_text": 0,
            "message_text": 0,
        }
        if rows:
            input_path = root / "messages.jsonl"
            input_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            backfill_summary = run_backfill(
                input_jsonl=input_path,
                files_root=root,
                days=max(3, (max(1, int(lookback_minutes)) // 1440) + 2),
            )
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        **summary,
        "backfill": backfill_summary,
    }


def _message_digest(message_id: str) -> str:
    return hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:16]


def _safe_file_name(value: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "").strip())
    clean = clean.rstrip(". ")
    return clean[:160] or "attachment.bin"


def _first_text(*values: Any) -> str | None:
    for value in values:
        clean = str(value or "").strip()
        if clean:
            return clean
    return None


def _parse_end(value: str | None, timezone_name: str) -> datetime:
    timezone = ZoneInfo(timezone_name)
    if not value:
        return datetime.now(timezone)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dws-bin", default="dws")
    parser.add_argument("--lookback-minutes", type=int, default=120)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--end")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    try:
        summary = sync_workspace_history(
            client=DingTalkWorkspaceClient(args.dws_bin),
            end=_parse_end(args.end, args.timezone),
            lookback_minutes=args.lookback_minutes,
            max_pages=args.max_pages,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"钉钉全会话同步失败：{exc.__class__.__name__}", file=error_output)
        return 1
    print(json.dumps(summary, ensure_ascii=False), file=output)
    return 2 if int(summary.get("download_failures", 0)) > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
