from __future__ import annotations


def attendance_rate(shi_dao_ren_shu_count: int, ying_dao_ren_shu_count: int) -> float:
    """出勤率口径：实到人数 / 应到人数；来源见 docs/domain/xintai-real-fields.md「考勤」小节。"""
    if ying_dao_ren_shu_count == 0:
        return 0.0
    return shi_dao_ren_shu_count / ying_dao_ren_shu_count


def overtime_hours(jia_ban_fen_zhong_minute: int) -> float:
    """加班小时口径：加班分钟 / 60；来源见 docs/domain/xintai-real-fields.md「考勤」小节。"""
    return jia_ban_fen_zhong_minute / 60


def makeup_card_rate(bu_ka_ci_shu_count: int, da_ka_ci_shu_count: int) -> float:
    """补卡率口径：补卡次数 / 打卡次数；来源见 docs/domain/xintai-real-fields.md「考勤」小节。"""
    if da_ka_ci_shu_count == 0:
        return 0.0
    return bu_ka_ci_shu_count / da_ka_ci_shu_count
