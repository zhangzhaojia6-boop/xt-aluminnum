from datetime import time

from scripts import seed_shift_config, update_shifts


def test_seed_shift_script_uses_canonical_business_shifts() -> None:
    assert seed_shift_config.SHIFTS == [
        ('A', 'day', '长白班', time(7, 30), time(15, 30), False, 0, 1),
        ('B', 'evening', '小夜班', time(15, 30), time(23, 30), False, 0, 2),
        ('C', 'night', '大夜班', time(23, 30), time(7, 30), True, 0, 3),
    ]


def test_update_shifts_script_disables_legacy_codes() -> None:
    assert update_shifts.UPDATES == {
        'A': ('长白班', 'day', time(7, 30), time(15, 30), False, 0, 1),
        'B': ('小夜班', 'evening', time(15, 30), time(23, 30), False, 0, 2),
        'C': ('大夜班', 'night', time(23, 30), time(7, 30), True, 0, 3),
    }
    assert update_shifts.LEGACY_SHIFT_CODES == {'DAY', 'MID', 'NIGHT'}
