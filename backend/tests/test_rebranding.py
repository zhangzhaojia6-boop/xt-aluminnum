from app.services import bootstrap
from tests.path_helpers import REPO_ROOT


def _repo_root():
    if (REPO_ROOT / 'frontend').exists():
        return REPO_ROOT
    return REPO_ROOT.parent


def test_bootstrap_defaults_use_xintai_branding_and_chinese_shift_labels() -> None:
    assert bootstrap.DEFAULT_SYSTEM_CONFIGS[0] == ('system_name', '河南鑫泰铝业生产管理系统', '系统显示名称')
    assert bootstrap.DEFAULT_SHIFT_CONFIGS == [
        ('A', '白班', 'day', bootstrap.time(7, 0), bootstrap.time(15, 0), False, 0, 1),
        ('B', '小夜', 'evening', bootstrap.time(15, 0), bootstrap.time(23, 0), True, 0, 2),
        ('C', '大夜', 'night', bootstrap.time(23, 0), bootstrap.time(7, 0), True, -1, 3),
    ]

    template_names = {item['template_code']: item['template_name'] for item in bootstrap.DEFAULT_FIELD_MAPPING_TEMPLATES}
    assert template_names == {
        'attendance_schedule_default': '考勤排班默认模板',
        'attendance_clock_default': '考勤打卡默认模板',
        'production_shift_default': '班次产量默认模板',
        'energy_default': '能耗默认模板',
        'mes_export_default': 'MES导出默认模板',
    }


def test_user_facing_brand_strings_are_updated() -> None:
    repo_root = _repo_root()
    login_text = (repo_root / 'frontend' / 'src' / 'views' / 'Login.vue').read_text(encoding='utf-8')
    manage_shell_text = (repo_root / 'frontend' / 'src' / 'layout' / 'ManageShell.vue').read_text(encoding='utf-8')
    entry_shell_text = (repo_root / 'frontend' / 'src' / 'layout' / 'EntryShell.vue').read_text(encoding='utf-8')
    app_shell_text = (repo_root / 'frontend' / 'src' / 'layout' / 'AppShell.vue').read_text(encoding='utf-8')
    router_text = (repo_root / 'frontend' / 'src' / 'router' / 'index.js').read_text(encoding='utf-8')
    index_text = (repo_root / 'frontend' / 'index.html').read_text(encoding='utf-8')
    config_text = (repo_root / 'backend' / 'app' / 'config.py').read_text(encoding='utf-8')

    assert '鑫泰铝业' in login_text
    assert '生产数据系统' in login_text
    assert '钉钉' in login_text
    assert '管理控制台' in manage_shell_text
    assert '独立填报端' in entry_shell_text
    assert '鑫' in app_shell_text
    assert '鑫泰铝业协同平台' in app_shell_text
    assert "const appTitle = import.meta.env.VITE_APP_TITLE || '鑫泰铝业'" in router_text
    assert '<title>鑫泰铝业</title>' in index_text
    assert "APP_NAME: str = '鑫泰铝业'" in config_text
