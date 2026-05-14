from __future__ import annotations


def defect_rate(bu_he_ge_juan_count: int, he_ji_juan_count: int) -> float:
    """不合格率口径：不合格卷数 / 合计卷数；来源见 docs/domain/xintai-real-fields.md「质量」小节。"""
    if he_ji_juan_count == 0:
        return 0.0
    return bu_he_ge_juan_count / he_ji_juan_count


def pareto_top_n(que_xian_counts: dict[str, int], qian_n_ming_count: int) -> list[dict[str, float | int | str]]:
    """缺陷 Pareto 口径：按缺陷次数降序取前 N 并计算累计占比；来源见 docs/domain/xintai-real-fields.md「质量」小节。"""
    total_count = sum(int(value or 0) for value in que_xian_counts.values())
    sorted_items = sorted(que_xian_counts.items(), key=lambda item: (-int(item[1] or 0), item[0]))
    result: list[dict[str, float | int | str]] = []
    cumulative_count = 0
    for name, count in sorted_items[:qian_n_ming_count]:
        normalized_count = int(count or 0)
        cumulative_count += normalized_count
        result.append(
            {
                'name': name,
                'count': normalized_count,
                'ratio': 0.0 if total_count == 0 else normalized_count / total_count,
                'cumulative_ratio': 0.0 if total_count == 0 else cumulative_count / total_count,
            }
        )
    return result


def disposition_breakdown(chu_zhi_juan_count: dict[str, int]) -> dict[str, int | dict[str, dict[str, float | int]]]:
    """处置分布口径：各处置类型卷数 / 总处置卷数；来源见 docs/domain/xintai-real-fields.md「质量」小节。"""
    total_count = sum(int(value or 0) for value in chu_zhi_juan_count.values())
    items: dict[str, dict[str, float | int]] = {}
    for name, count in chu_zhi_juan_count.items():
        normalized_count = int(count or 0)
        items[name] = {
            'count': normalized_count,
            'ratio': 0.0 if total_count == 0 else normalized_count / total_count,
        }
    return {'total_count': total_count, 'items': items}
