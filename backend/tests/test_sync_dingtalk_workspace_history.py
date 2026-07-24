from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scripts.sync_dingtalk_workspace_history import (
    DingTalkWorkspaceClient,
    _flatten_conversation_messages,
    prepare_backfill_rows,
)


class _FakeDownloadClient:
    def __init__(self) -> None:
        self.file_downloads: list[tuple[str, Path]] = []
        self.image_downloads: list[tuple[str, str, str, Path]] = []

    def download_file(self, *, file_id: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("7月23日成品库入库357.73吨", encoding="utf-8")
        self.file_downloads.append((file_id, output_path))

    def download_image(
        self,
        *,
        media_id: str,
        message_id: str,
        conversation_id: str,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"image")
        self.image_downloads.append((media_id, message_id, conversation_id, output_path))


class _PagedClient(DingTalkWorkspaceClient):
    def __init__(self, pages):
        super().__init__("unused")
        self.pages = list(pages)

    def _run_json(self, _args):
        return self.pages.pop(0)


def test_flatten_conversation_messages_keeps_every_conversation() -> None:
    rows = _flatten_conversation_messages(
        {
            "conversationMessagesList": [
                {
                    "openConversationId": "group-a",
                    "title": "生产群",
                    "singleChat": False,
                    "messages": [{"openMessageId": "m1", "content": "产量100吨"}],
                },
                {
                    "openConversationId": "private-b",
                    "title": "私聊",
                    "singleChat": True,
                    "messages": [{"openMessageId": "m2", "content": "设备已恢复"}],
                },
            ]
        }
    )

    assert [row["openConversationId"] for row in rows] == ["group-a", "private-b"]
    assert rows[0]["singleChat"] is False
    assert rows[1]["singleChat"] is True


def test_dws_client_follows_all_pages_without_group_filter() -> None:
    client = _PagedClient(
        [
            {
                "success": True,
                "result": {
                    "conversationMessagesList": [
                        {"openConversationId": "group-a", "messages": [{"openMessageId": "m1"}]}
                    ],
                    "hasMore": True,
                    "nextCursor": "next",
                },
            },
            {
                "success": True,
                "result": {
                    "conversationMessagesList": [
                        {"openConversationId": "group-b", "messages": [{"openMessageId": "m2"}]}
                    ],
                    "hasMore": False,
                },
            },
        ]
    )

    rows = client.list_messages(
        start=datetime(2026, 7, 24, 13, 0, tzinfo=UTC),
        end=datetime(2026, 7, 24, 14, 0, tzinfo=UTC),
    )

    assert [row["openConversationId"] for row in rows] == ["group-a", "group-b"]


def test_prepare_rows_is_broad_but_silent_and_skips_hermes_output(tmp_path) -> None:
    client = _FakeDownloadClient()
    messages = [
        {
            "openConversationId": "group-a",
            "openMessageId": "existing",
            "sender": "责任人甲",
            "senderOpenDingTalkId": "open-a",
            "createTime": "2026-07-24 14:00:00",
            "content": "这条已经入库",
        },
        {
            "openConversationId": "group-a",
            "openMessageId": "bot",
            "sender": "鑫泰hermes",
            "senderOpenDingTalkId": "open-bot",
            "createTime": "2026-07-24 14:01:00",
            "content": "我刚刚已经回答过",
        },
        {
            "openConversationId": "group-b",
            "openMessageId": "text",
            "sender": "责任人乙",
            "senderOpenDingTalkId": "open-b",
            "createTime": "2026-07-24 14:02:00",
            "content": "这句话没有固定关键词，但也必须留证",
        },
        {
            "openConversationId": "group-c",
            "openMessageId": "file",
            "sender": "责任人丙",
            "senderOpenDingTalkId": "open-c",
            "createTime": "2026-07-24 14:03:00",
            "content": "[文件] 7月23日报表.txt fileId: file-node-1 注意：如需下载",
        },
        {
            "openConversationId": "group-d",
            "openMessageId": "image",
            "sender": "责任人丁",
            "senderOpenDingTalkId": "open-d",
            "createTime": "2026-07-24 14:04:00",
            "content": "[图片消息](mediaId=media-1) 注意：如需下载",
        },
    ]

    rows, summary = prepare_backfill_rows(
        messages,
        files_root=tmp_path,
        client=client,
        existing_message_ids={"existing"},
    )

    assert summary == {
        "listed": 5,
        "prepared": 3,
        "skipped_existing": 1,
        "skipped_self": 1,
        "skipped_invalid": 0,
        "downloaded": 2,
        "download_failures": 0,
    }
    assert [row["messageId"] for row in rows] == ["text", "file", "image"]
    assert rows[0]["content"] == "这句话没有固定关键词，但也必须留证"
    assert rows[1]["fileName"] == "7月23日报表.txt"
    assert (tmp_path / rows[1]["localFilePath"]).read_text(encoding="utf-8").endswith("357.73吨")
    assert rows[2]["fileName"] == "image.png"
    assert len(client.file_downloads) == 1
    assert len(client.image_downloads) == 1
