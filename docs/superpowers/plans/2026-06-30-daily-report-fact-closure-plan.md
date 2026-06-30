# 日报事实闭环实施计划

日期：2026-06-30

对应设计：`docs/superpowers/specs/2026-06-30-daily-report-fact-closure-design.md`

## 任务

- [x] 写入方案 B 设计规格。
- [x] 增加日报字段缺口归因服务。
- [x] 把缺口归因接入模板日报 payload 和 DailyFactBundle。
- [x] 把缺口归因接入 `check_daily_report_output_skill_alignment.py`。
- [x] 补单元测试。
- [x] 跑定向测试。
- [x] 本机只读跑 `D:\输出skill` 验收，记录本机数据库缺口。
- [ ] 提交改动。

## 验收命令

```powershell
python -m pytest backend/tests/test_daily_report_gap_analysis.py backend/tests/test_daily_fact_bundle_service.py backend/tests/test_template_daily_report.py backend/tests/test_check_daily_report_output_skill_alignment_script.py backend/tests/test_business_time_contract.py backend/tests/test_hermes_langchain_tools.py -q
python backend/scripts/check_daily_report_output_skill_alignment.py --output-skill-root D:\输出skill --date 2026-06-27 --date 2026-06-28 --date 2026-06-29 --json
git diff --check
```

## 不做

- 不改日报取数算法。
- 不改 MES 只读同步。
- 不改扫码登录。
- 不新增前端页面。
- 不删除旧文件。
