import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_hermes_root_owner_private_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_hermes_root_owner_private_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_uses_private_root_owner_fields() -> None:
    module = _load_module()

    payload = module.build_payload(
        text="今天咋样",
        dingtalk_user_id="dt-root-001",
        dingtalk_union_id="union-root-001",
        trace_id="trace-smoke-001",
    )

    assert payload["senderStaffId"] == "dt-root-001"
    assert payload["senderUnionId"] == "union-root-001"
    assert payload["text"]["content"] == "今天咋样"
    assert payload["traceId"] == "trace-smoke-001"
    assert "conversationId" not in payload


def test_mask_secret_hides_token() -> None:
    module = _load_module()

    assert module.mask_secret("abcdef123456") == "abcd...3456"
    assert module.mask_secret("") == ""
