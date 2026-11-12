from datetime import datetime
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('notify_backup_failure', ROOT / 'backend/scripts/notify_backup_failure.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_message_names_failure_reason_and_where_to_look():
    text = module.build_message('备份中止：剩余空间 900MB', datetime(2026, 11, 13, 2, 30))
    assert text.startswith('【数据中枢】每日备份失败（11-13 02:30）')
    assert '原因：备份中止：剩余空间 900MB' in text
    assert 'journalctl -u xintai-daily-backup' in text


def test_message_without_reason_is_still_explicit():
    assert '原因：未取到失败原因' in module.build_message('  ', datetime(2026, 11, 13, 2, 30))


def test_default_recipient_is_zhang_zhaojia(monkeypatch):
    monkeypatch.setattr(module.settings, 'OPS_ALERT_USER_IDS', '983')
    assert module.recipient_ids() == [983]


def test_backup_unit_triggers_alert_on_failure():
    unit = (ROOT / 'scripts/prod/xintai-daily-backup.service').read_text(encoding='utf-8')
    alert = (ROOT / 'scripts/prod/xintai-backup-alert.service').read_text(encoding='utf-8')
    assert 'OnFailure=xintai-backup-alert.service' in unit
    assert 'scripts/notify_backup_failure.py' in alert
    assert 'EnvironmentFile=/srv/aluminum-bypass/backend/.env' in alert
    assert 'SupplementaryGroups=systemd-journal' in alert
    # systemd 会先展开 $，命令行里的 $ 必须写成 $$
    assert 'reason=$$(' in alert and '"$$reason"' in alert
    assert 'reason=$(' not in alert
