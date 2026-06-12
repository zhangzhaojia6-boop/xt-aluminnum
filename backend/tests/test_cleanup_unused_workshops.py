from app.models.master import Workshop
from scripts.cleanup_unused_workshops import should_keep_workshop


def _workshop(code: str, name: str, *, is_active: bool = True) -> Workshop:
    return Workshop(code=code, name=name, is_active=is_active)


def test_cleanup_keeps_thirteen_active_production_workshops() -> None:
    keep, reason = should_keep_workshop(_workshop('CH', '淬火车间'))

    assert keep is True
    assert '13个生产车间' in reason


def test_cleanup_keeps_finished_goods_storage_and_inactive_workshops() -> None:
    keep_storage, storage_reason = should_keep_workshop(_workshop('CPK', '成品库'))
    keep_inactive, inactive_reason = should_keep_workshop(_workshop('OLD', '冷轧三车间', is_active=False))

    assert keep_storage is True
    assert '成品库' in storage_reason
    assert keep_inactive is True
    assert '未启用' in inactive_reason


def test_cleanup_deactivates_active_useless_workshop() -> None:
    keep, reason = should_keep_workshop(_workshop('ZR5', '铸轧五'))

    assert keep is False
    assert '停用' in reason
