"""规则引擎单元测试"""
from app.rules.validation import validate_shift_report
from app.rules.auto_confirm import evaluate_auto_confirm


class TestValidation:
    """校验规则测试"""

    def test_valid_data_passes(self):
        """完整合法数据应通过校验"""
        data = {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 95.0,
            'scrap_weight': 5.0,
            'electricity_daily': 5000.0,
            'gas_daily': 1000.0,
        }
        result = validate_shift_report(data)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_missing_attendance_fails(self):
        """缺少出勤人数应失败"""
        data = {
            'input_weight': 100.0,
            'output_weight': 95.0,
        }
        result = validate_shift_report(data)
        assert result.passed is False
        assert any('出勤' in e for e in result.errors)

    def test_output_exceeds_input_fails(self):
        """产出大于投入应失败"""
        data = {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 150.0,
        }
        result = validate_shift_report(data)
        assert result.passed is False
        assert any('产出' in e or '投入' in e for e in result.errors)

    def test_negative_weight_fails(self):
        """负数重量应失败"""
        data = {
            'attendance_count': 10,
            'input_weight': -10.0,
            'output_weight': 5.0,
        }
        result = validate_shift_report(data)
        assert result.passed is False

    def test_attendance_too_high_warns_but_passes(self):
        """出勤人数偏高应告警但不阻断提交"""
        data = {
            'attendance_count': 100,
            'input_weight': 100.0,
            'output_weight': 95.0,
        }
        result = validate_shift_report(data)
        assert result.passed is True
        assert any('偏高' in w for w in result.warnings)

    def test_optional_energy_bad_format_warns(self):
        """可选能耗字段格式错误应告警但不阻断提交"""
        data = {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 95.0,
            'electricity_daily': 'abc',
        }
        result = validate_shift_report(data)
        assert result.passed is True
        assert any('日电耗格式不正确' in w for w in result.warnings)


class TestAutoConfirm:
    """自动确认规则测试"""

    def test_valid_data_auto_confirms(self):
        """合法数据应自动确认"""
        data = {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 95.0,
            'scrap_weight': 5.0,
        }
        result = evaluate_auto_confirm(data)
        assert result.confirmed is True

    def test_invalid_data_not_confirmed(self):
        """不合法数据不应确认"""
        data = {
            'attendance_count': 10,
            'input_weight': 50.0,
            'output_weight': 100.0,  # 产出 > 投入
        }
        result = evaluate_auto_confirm(data)
        assert result.confirmed is False

    def test_warning_data_still_auto_confirms(self):
        """仅有 warning 的数据应自动确认"""
        data = {
            'attendance_count': 55,
            'input_weight': 100.0,
            'output_weight': 95.0,
        }
        result = evaluate_auto_confirm(data)
        assert result.confirmed is True
        assert any('偏高' in w for w in result.validation.warnings)
