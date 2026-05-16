# 鑫泰真实报表字段目录

来源范围：只读扫描 `D:\鑫泰报表\5.1`、`5.2`、`5.3`、`5.4`、`5.5` 下全部 Excel，并对照项目模型、导入模板、MES Phase 1 映射与现有日报服务公式。  
字段行采用“Excel 原表头 + 行/列业务维度”的组合口径；量级为 5 天归档观测值，`典型值` 优先取 5.5 或最新可见值。未能从 5 天归档确认的字段标为 `TODO` 并列入 `Unresolved`。

## 生产

| 字段原名 | English slug | 单位 | 数值量级（典型 / 最大 / 最小） | 统计周期 | 聚合方式 | 业务口径 | 来源文件 | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 车间/项目 | che_jian_xiang_mu | - | 铸锭 / 冷轧-2050 / 园区剪切 | 日 | 维度 | 综合日报的生产主体维度，空白车间沿用上一行车间。 | 鑫泰每日产量5月.xls | 综合报表 |
| 投料量-日合 | tou_liao_liang_ri_he_ton | 吨 | 90.740 / 382.850 / 0.000 | 日 | 求和 | 当日投入到对应车间或机台的物料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 投料量-累计 | tou_liao_liang_lei_ji_ton | 吨 | 692.550 / 1761.996 / 0.000 | 月 | 求和 | 当月截至报表日的累计投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 日产量-日合 | ri_chan_liang_ri_he_ton | 吨 | 85.130 / 366.468 / 0.000 | 日 | 求和 | 当日对应车间或机台的产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 日产量-累计 | ri_chan_liang_lei_ji_ton | 吨 | 669.590 / 1678.246 / 0.000 | 月 | 求和 | 当月截至报表日的累计产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 日均 | ri_jun_ton | 吨/日 | TODO | 月 | 均值 | 月内累计产量折算的日均产量，5 天归档中字段存在但计算基准未完全确认。 | 鑫泰每日产量5月.xls | 综合报表 |
| 产生废料-日合 | chan_sheng_fei_liao_ri_he_ton | 吨 | 5.610 / 50.025 / -51.000 | 日 | 求和 | 当日投料与产出差异形成的废料或调整量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 产生废料-累计 | chan_sheng_fei_liao_lei_ji_ton | 吨 | 22.960 / 120.010 / -425.000 | 月 | 求和 | 当月累计废料或调整量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 月成品率 | yue_cheng_pin_lv | 比例 | 0.9668 / 1.0015 / 0.8772 | 月 | 比例 | 月累计产量除以月累计投料，部分特殊工序可超过 1。 | 鑫泰每日产量5月.xls | 综合报表 |
| 成品率指标 | cheng_pin_lv_zhi_biao | 比例 | 0.9600 / 0.9900 / 0.9220 | 月 | 目标值 | 对应车间或产品线的成品率考核目标。 | 鑫泰每日产量5月.xls | 综合报表 |
| 成品率对比 | cheng_pin_lv_dui_bi | 比例 | 0.0068 / 0.0329 / -0.0528 | 月 | 差分 | 月成品率与目标指标的差值。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸锭-日投料量 | zhu_ding_ri_tou_liao_liang_ton | 吨 | 331.650 / 382.850 / 331.650 | 日 | 求和 | 铸锭当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸锭-日产量 | zhu_ding_ri_chan_liang_ton | 吨 | 314.190 / 366.468 / 314.190 | 日 | 求和 | 铸锭当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸锭-月累计产量 | zhu_ding_yue_lei_ji_chan_liang_ton | 吨 | 1678.246 / 1678.246 / 366.468 | 月 | 求和 | 铸锭月内累计产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸二-日投料量 | zhu_er_ri_tou_liao_liang_ton | 吨 | 25.000 / 25.000 / 0.000 | 日 | 求和 | 铸二当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸二-日产量 | zhu_er_ri_chan_liang_ton | 吨 | 24.180 / 24.180 / 0.000 | 日 | 求和 | 铸二当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸三-日投料量 | zhu_san_ri_tou_liao_liang_ton | 吨 | 38.000 / 41.000 / 38.000 | 日 | 求和 | 铸三当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸三-日产量 | zhu_san_ri_chan_liang_ton | 吨 | 36.200 / 39.270 / 36.200 | 日 | 求和 | 铸三当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铣床-日投料量 | xi_chuang_ri_tou_liao_liang_ton | 吨 | 296.120 / 296.120 / 296.120 | 日 | 求和 | 热轧铣床当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铣床-日产量 | xi_chuang_ri_chan_liang_ton | 吨 | 278.130 / 278.130 / 278.130 | 日 | 求和 | 热轧铣床当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 热轧-日产量 | re_zha_ri_chan_liang_ton | 吨 | 0.000 / 0.000 / 0.000 | 日 | 求和 | 热轧主线当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 1650-日投料量 | yi_liu_wu_ling_ri_tou_liao_liang_ton | 吨 | 249.838 / 249.838 / 249.838 | 日 | 求和 | 1650 冷轧当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 1650-日产量 | yi_liu_wu_ling_ri_chan_liang_ton | 吨 | 224.540 / 224.540 / 224.540 | 日 | 求和 | 1650 冷轧当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 1850-日投料量 | yi_ba_wu_ling_ri_tou_liao_liang_ton | 吨 | 32.930 / 32.930 / 32.930 | 日 | 求和 | 1850 冷轧当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 1850-日产量 | yi_ba_wu_ling_ri_chan_liang_ton | 吨 | 31.080 / 31.080 / 31.080 | 日 | 求和 | 1850 冷轧当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 2050-日投料量 | er_ling_wu_ling_ri_tou_liao_liang_ton | 吨 | 90.740 / 90.740 / 90.740 | 日 | 求和 | 2050 冷轧当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 2050-日产量 | er_ling_wu_ling_ri_chan_liang_ton | 吨 | 85.130 / 85.130 / 85.130 | 日 | 求和 | 2050 冷轧当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 精整剪子-日产量 | jing_zheng_jian_zi_ri_chan_liang_ton | 吨 | 45.286 / 45.286 / 45.286 | 日 | 求和 | 精整剪子当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 精整纵剪-日产量 | jing_zheng_zong_jian_ri_chan_liang_ton | 吨 | 75.960 / 75.960 / 75.960 | 日 | 求和 | 精整纵剪当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 拉矫-日产量 | la_jiao_ri_chan_liang_ton | 吨 | 196.080 / 196.080 / 196.080 | 日 | 求和 | 拉矫当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 分切-日产量 | fen_qie_ri_chan_liang_ton | 吨 | 39.580 / 39.580 / 39.580 | 日 | 求和 | 分切当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 在线退火北线-日产量 | zai_xian_tui_huo_bei_xian_ri_chan_liang_ton | 吨 | 302.840 / 302.840 / 302.840 | 日 | 求和 | 新厂北线在线退火当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 园区北线-日产量 | yuan_qu_bei_xian_ri_chan_liang_ton | 吨 | 181.970 / 181.970 / 181.970 | 日 | 求和 | 园区北线当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 园区剪切-日投料量 | yuan_qu_jian_qie_ri_tou_liao_liang_ton | 吨 | 52.814 / 52.814 / 52.814 | 日 | 求和 | 园区剪切当日投料重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 园区剪切-日产量 | yuan_qu_jian_qie_ri_chan_liang_ton | 吨 | 49.483 / 49.483 / 49.483 | 日 | 求和 | 园区剪切当日产出重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 合计-日投料量 | he_ji_ri_tou_liao_liang_ton | 吨 | 1985.674 / 1985.674 / 1985.674 | 日 | 求和 | 综合日报所有生产行的当日投料合计。 | 鑫泰每日产量5月.xls | 综合报表 |
| 合计-日产量 | he_ji_ri_chan_liang_ton | 吨 | 1935.649 / 1935.649 / 1935.649 | 日 | 求和 | 综合日报所有生产行的当日产量合计。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸轧分厂-日产量 | zhu_zha_fen_chang_ri_chan_liang_ton | 吨 | 60.380 / 60.380 / 60.380 | 日 | 求和 | 汇总区中铸二与铸三的日生产量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 轧机-日产量 | zha_ji_ri_chan_liang_ton | 吨 | 340.750 / 340.750 / 340.750 | 日 | 求和 | 汇总区中 1650、1850、2050 的日生产量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 日道次 | ri_dao_ci_count | 次 | 97 / 169 / 27 | 日 | 求和 | 对应轧机或工序当日道次数。 | 鑫泰每日产量5月.xls | 综合报表 |
| 月累计道次 | yue_lei_ji_dao_ci_count | 次 | 466 / 858 / 146 | 月 | 求和 | 对应轧机或工序月内累计道次数。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸轧三车间-机列 | zhu_zha_san_che_jian_ji_lie | - | 2#;5052合金 / 3#3004合金 | 班 | 维度 | 机列能耗表中的机列与合金维度。 | 铸三5月5日能耗表.xls | Sheet2 |
| 铸轧二车间-机列 | zhu_zha_er_che_jian_ji_lie | - | 3#;5052合金 / 6#5052合金 | 班 | 维度 | 机列能耗表中的机列与合金维度。 | 铸二5月5日能耗表.xls | Sheet2 |
| 大夜产量 | da_ye_chan_liang_ton | 吨 | 11.700 / 48.000 / 2.200 | 班 | 求和 | 大夜班对应机列产量。 | 铸二5月5日能耗表.xls | Sheet2 |
| 白班产量 | bai_ban_chan_liang_ton | 吨 | 12.450 / 12.450 / 4.170 | 班 | 求和 | 白班对应机列产量。 | 铸二5月5日能耗表.xls | Sheet2 |
| 小夜产量 | xiao_ye_chan_liang_ton | 吨 | 6.500 / 24.320 / 6.500 | 班 | 求和 | 小夜班对应机列产量。 | 铸二5月5日能耗表.xls | Sheet2 |
| 深加工-飞剪开平成品 | shen_jia_gong_fei_jian_kai_ping_cheng_pin_ton | 吨 | 97.986 / 97.986 / 54.904 | 日 | 求和 | 深加工飞剪开平成品按日期列记录的产量。 | 鑫泰每日产量5月.xls | 深加工 |
| 外加工-园区剪切 | wai_jia_gong_yuan_qu_jian_qie_ton | 吨 | 51.973 / 51.973 / 0.000 | 日 | 求和 | 外加工表中园区剪切按日期列记录的外加工量。 | 鑫泰每日产量5月.xls | 外加工 |

## 能耗

| 字段原名 | English slug | 单位 | 数值量级（典型 / 最大 / 最小） | 统计周期 | 聚合方式 | 业务口径 | 来源文件 | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 电度/度 | dian_du_du | 度 | 24100 / 24100 / 659 | 日 | 求和 | 综合日报行级当日电表用电量，1 度按 1 kWh 处理。 | 鑫泰每日产量5月.xls | 综合报表 |
| 日耗电量（度） | ri_hao_dian_liang_du | kWh/t | 283.096 / 283.096 / 5.053 | 日 | 比例 | 当日电量除以当日产量得到的吨电耗。 | 鑫泰每日产量5月.xls | 综合报表 |
| 月耗电量（度） | yue_hao_dian_liang_du | kWh/t | 173.569 / 173.569 / 8.965 | 月 | 比例 | 月电度除以月累计产量得到的月吨电耗。 | 鑫泰每日产量5月.xls | 综合报表 |
| 电耗指标 | dian_hao_zhi_biao | kWh/t | 90 / 170 / 7 | 日/月 | 目标值 | 车间或工序吨电耗考核指标。 | 鑫泰每日产量5月.xls | 综合报表 |
| 电耗对比 | dian_hao_dui_bi | kWh/t | 83.569 / 83.569 / -70.000 | 日/月 | 差分 | 实际吨电耗与电耗指标的差值。 | 鑫泰每日产量5月.xls | 综合报表 |
| 天然气m³ | tian_ran_qi_m3 | 立方米 | 3004 / 25673 / 0 | 日 | 求和 | 综合日报行级当日天然气用量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 日耗气量m³ | ri_hao_qi_liang_m3_per_ton | m³/t | 124.235 / 124.235 / 0.000 | 日 | 比例 | 当日天然气用量除以当日产量得到吨气耗。 | 鑫泰每日产量5月.xls | 综合报表 |
| 月耗气量m³ | yue_hao_qi_liang_m3_per_ton | m³/t | 171.613 / 171.613 / 0.000 | 月 | 比例 | 月天然气用量除以月累计产量得到月吨气耗。 | 鑫泰每日产量5月.xls | 综合报表 |
| 气耗指标 | qi_hao_zhi_biao | m³/t | 95 / 95 / 20 | 日/月 | 目标值 | 车间或工序吨气耗考核指标。 | 鑫泰每日产量5月.xls | 综合报表 |
| 气耗对比 | qi_hao_dui_bi | m³/t | 76.613 / 76.613 / -95.000 | 日/月 | 差分 | 实际吨气耗与气耗指标的差值。 | 鑫泰每日产量5月.xls | 综合报表 |
| 铸锭电耗 | zhu_ding_dian_hao_kwh | kWh | 7950 / 7950 / 7650 | 日 | 求和 | 各车间能耗统计表中铸锭当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 铸二电耗 | zhu_er_dian_hao_kwh | kWh | 1920 / 2220 / 1200 | 日 | 求和 | 各车间能耗统计表中铸二当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 铸三电耗 | zhu_san_dian_hao_kwh | kWh | 3430 / 3446 / 3296 | 日 | 求和 | 各车间能耗统计表中铸三当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 铸五制水房电耗 | zhu_wu_zhi_shui_fang_dian_hao_kwh | kWh | 300 / 420 / 130 | 日 | 求和 | 铸五制水房当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 2050电耗 | er_ling_wu_ling_dian_hao_kwh | kWh | 24180 / 25580 / 19740 | 日 | 求和 | 2050 车间当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 1850电耗 | yi_ba_wu_ling_dian_hao_kwh | kWh | 6760 / 7880 / 6760 | 日 | 求和 | 1850 车间当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 1650电耗 | yi_liu_wu_ling_dian_hao_kwh | kWh | 10576 / 14864 / 10576 | 日 | 求和 | 1650 车间当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 热轧电耗 | re_zha_dian_hao_kwh | kWh | 10314 / 53526 / 10314 | 日 | 求和 | 热轧车间当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 空压机电耗 | kong_ya_ji_dian_hao_kwh | kWh | 1060 / 8900 / 1060 | 日 | 求和 | 空压机当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 水泵电耗 | shui_beng_dian_hao_kwh | kWh | 7850 / 9290 / 7520 | 日 | 求和 | 水泵当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 拉矫电耗 | la_jiao_dian_hao_kwh | kWh | 11640 / 11640 / 7560 | 日 | 求和 | 拉矫当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 拉退火炉电耗 | la_tui_huo_lu_dian_hao_kwh | kWh | 3837 / 6680 / 2269 | 日 | 求和 | 拉退火炉当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 精整电耗 | jing_zheng_dian_hao_kwh | kWh | 1760 / 1980 / 680 | 日 | 求和 | 精整当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 铝灰回收电耗 | lv_hui_hui_shou_dian_hao_kwh | kWh | 5500 / 5500 / 4880 | 日 | 求和 | 铝灰回收当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 北线电耗 | bei_xian_dian_hao_kwh | kWh | 14320 / 14880 / 600 | 日 | 求和 | 北线当日用电量。 | 5月份各车间能耗统计表.xls | 用量 |
| 南线电耗 | nan_xian_dian_hao_kwh | kWh | 7.5 / 7.5 / 5.0 | 日 | 求和 | 南线当日用电量，量级异常偏小，待后续确认是否单位或录入口径不同。 | 5月份各车间能耗统计表.xls | 用量 |
| 天然气-铸锭 | tian_ran_qi_zhu_ding_m3 | 立方米 | 25673 / 27906 / 24080 | 日 | 求和 | 天然气用量表中铸锭当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气-回收 | tian_ran_qi_hui_shou_m3 | 立方米 | 1446 / 1446 / 923 | 日 | 求和 | 天然气用量表中回收当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气-铸二 | tian_ran_qi_zhu_er_m3 | 立方米 | 3004 / 3979 / 2296 | 日 | 求和 | 天然气用量表中铸二当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气-铸三 | tian_ran_qi_zhu_san_m3 | 立方米 | 3993 / 4239 / 3761 | 日 | 求和 | 天然气用量表中铸三当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气-热轧 | tian_ran_qi_re_zha_m3 | 立方米 | 0 / 5924 / 0 | 日 | 求和 | 天然气用量表中热轧当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气-拉矫 | tian_ran_qi_la_jiao_m3 | 立方米 | 880 / 2204 / 880 | 日 | 求和 | 天然气用量表中拉矫当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气-北线 | tian_ran_qi_bei_xian_m3 | 立方米 | 7455 / 8165 / 0 | 日 | 求和 | 天然气用量表中北线当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气-彩涂 | tian_ran_qi_cai_tu_m3 | 立方米 | 1937 / 1946 / 0 | 日 | 求和 | 天然气用量表中彩涂当日用气量。 | 5月份各车间天然气用量统计表.xls | 用量 |
| 天然气抄表-铸锭 | tian_ran_qi_chao_biao_zhu_ding_m3 | 立方米 | 9980517 / 9980517 / 9873554 | 日 | 最大 | 铸锭天然气表累计读数。 | 5月份各车间天然气用量统计表.xls | 抄表 |
| 天然气抄表-铸二 | tian_ran_qi_chao_biao_zhu_er_m3 | 立方米 | 4132867 / 4132867 / 4121276 | 日 | 最大 | 铸二天然气表累计读数。 | 5月份各车间天然气用量统计表.xls | 抄表 |
| 园区电 | yuan_qu_dian_kwh | kWh | 8339 / 8642 / 1058 | 日 | 求和 | 园区+新厂表中园区侧当日用电量。 | 园区电+新厂电(1).xls | 园区+新厂 |
| 新厂电 | xin_chang_dian_kwh | kWh | 94519 / 128424 / 94519 | 日 | 求和 | 园区+新厂表中新厂侧当日用电量。 | 园区电+新厂电(1).xls | 园区+新厂 |
| 园区+新厂电合计 | yuan_qu_xin_chang_dian_he_ji_kwh | kWh | 102858 / 133577 / 102858 | 日 | 求和 | 园区电和新厂电的当日合计。 | 园区电+新厂电(1).xls | 园区+新厂 |
| 回收+大修+办公楼电 | hui_shou_da_xiu_ban_gong_lou_dian_kwh | kWh | 4450 / 4520 / 3984 | 日 | 求和 | 办公楼与辅助区域当日用电量合计。 | 园区电+新厂电(1).xls | 园区+新厂 |
| 园区气 | yuan_qu_qi_m3 | 立方米 | TODO | 日 | 求和 | 园区+新厂表中园区侧当日用气量，5.5 行有空值需确认。 | 园区电+新厂电(1).xls | 园区+新厂 |
| 新厂气 | xin_chang_qi_m3 | 立方米 | 46519 / 53436 / 46519 | 日 | 求和 | 园区+新厂表中新厂侧当日用气量。 | 园区电+新厂电(1).xls | 园区+新厂 |
| 园区+新厂气合计 | yuan_qu_xin_chang_qi_he_ji_m3 | 立方米 | 46519 / 59681 / 46519 | 日 | 求和 | 园区气和新厂气的当日合计。 | 园区电+新厂电(1).xls | 园区+新厂 |
| 办公楼-回收电 | ban_gong_lou_hui_shou_dian_kwh | kWh | 3330 / 3330 / 3000 | 日 | 求和 | 办公楼 sheet 中回收部门当日用电量。 | 园区电+新厂电(1).xls | 办公楼 |
| 大修+办公楼（西）电 | da_xiu_ban_gong_lou_xi_dian_kwh | kWh | 400 / 760 / 400 | 日 | 求和 | 办公楼 sheet 中西侧大修及办公楼用电。 | 园区电+新厂电(1).xls | 办公楼 |
| 办公楼+宿舍+餐厅+东门岗电 | ban_gong_lou_su_she_can_ting_dong_men_gang_dian_kwh | kWh | 720 / 720 / 640 | 日 | 求和 | 办公楼、宿舍、餐厅和东门岗当日用电。 | 园区电+新厂电(1).xls | 办公楼 |
| 公司总用电量 | gong_si_zong_yong_dian_liang_kwh | kWh | 125320 / 171580 / 125320 | 日 | 求和 | 办公楼 sheet 中公司级总用电量。 | 园区电+新厂电(1).xls | 办公楼 |
| 机列吨气耗-当日 | ji_lie_dun_qi_hao_dang_ri_m3_per_ton | m³/t | 91.75 / 164.30 / 76.25 | 班 | 比例 | 机列能耗表中对应班次的当日吨气耗。 | 铸二5月5日能耗表.xls | Sheet2 |
| 机列吨气耗-昨日 | ji_lie_dun_qi_hao_zuo_ri_m3_per_ton | m³/t | 148.30 / 148.30 / 89.77 | 班 | 比例 | 机列能耗表中对应班次昨日吨气耗。 | 铸二5月5日能耗表.xls | Sheet2 |
| 机列吨气耗-对比 | ji_lie_dun_qi_hao_dui_bi_m3_per_ton | m³/t | 100.30 / 100.30 / 85.60 | 班 | 差分 | 当日吨气耗与昨日或指标的对比值，源表未完全说明对比基准。 | 铸二5月5日能耗表.xls | Sheet2 |

## 质量

| 字段原名 | English slug | 单位 | 数值量级（典型 / 最大 / 最小） | 统计周期 | 聚合方式 | 业务口径 | 来源文件 | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1450车间-M日合计 | yi_si_wu_ling_m_ri_he_ji_rate | 比例 | TODO | 日 | 比例 | 1450 车间 M 类日成品率，5 天归档为 `/`，待真实生产值补齐。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 1450车间-M月累计 | yi_si_wu_ling_m_yue_lei_ji_rate | 比例 | TODO | 月 | 比例 | 1450 车间 M 类月累计成品率，5 天归档为 `/`。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 1450车间-P日合计 | yi_si_wu_ling_p_ri_he_ji_rate | 比例 | TODO | 日 | 比例 | 1450 车间 P 类日成品率，5 天归档为 `/`。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 1650+2050车间-M日合计 | yi_liu_wu_ling_er_ling_wu_ling_m_ri_he_ji_rate | 比例 | TODO | 日 | 比例 | 1650+2050 车间 M 类日成品率，5 天归档为 `/`。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 1650+2050车间-P铸轧日合计 | yi_liu_wu_ling_er_ling_wu_ling_p_zhu_zha_ri_he_ji_rate | 比例 | 0.9383 / 0.9590 / 0.8913 | 日 | 比例 | 1650+2050 车间 P 铸轧日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 1650+2050车间-P铸轧月累计 | yi_liu_wu_ling_er_ling_wu_ling_p_zhu_zha_yue_lei_ji_rate | 比例 | 0.9426 / 0.9590 / 0.9426 | 月 | 比例 | 1650+2050 车间 P 铸轧月累计成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 1650+2050车间-P热轧日合计 | yi_liu_wu_ling_er_ling_wu_ling_p_re_zha_ri_he_ji_rate | 比例 | 0.8471 / 0.8495 / 0.8295 | 日 | 比例 | 1650+2050 车间 P 热轧日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 1650+2050车间-P热轧月累计 | yi_liu_wu_ling_er_ling_wu_ling_p_re_zha_yue_lei_ji_rate | 比例 | 0.8393 / 0.8395 / 0.8295 | 月 | 比例 | 1650+2050 车间 P 热轧月累计成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 拉矫日合计 | la_jiao_cheng_pin_lv_ri_he_ji_rate | 比例 | 0.9069 / 0.9195 / 0.8832 | 日 | 比例 | 拉矫日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 拉矫月累计 | la_jiao_cheng_pin_lv_yue_lei_ji_rate | 比例 | 0.9011 / 0.9235 / 0.8991 | 月 | 比例 | 拉矫月累计成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 精整车间-铸轧日合计 | jing_zheng_zhu_zha_ri_he_ji_rate | 比例 | TODO | 日 | 比例 | 精整车间铸轧类日成品率，5 天归档多为空。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 精整车间-热轧日合计 | jing_zheng_re_zha_ri_he_ji_rate | 比例 | 0.8854 / 0.9056 / 0.8779 | 日 | 比例 | 精整车间热轧类日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 园区飞剪-热轧日合计 | yuan_qu_fei_jian_re_zha_ri_he_ji_rate | 比例 | 0.9516 / 0.9516 / 0.9126 | 日 | 比例 | 园区飞剪热轧类日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 重卷机日合计 | zhong_juan_ji_ri_he_ji_rate | 比例 | 0.9256 / 0.9752 / 0.9256 | 日 | 比例 | 重卷机日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 铸轧普卷板日合计 | zhu_zha_pu_juan_ban_ri_he_ji_rate | 比例 | 0.9383 / 0.9590 / 0.8913 | 日 | 比例 | 公司级铸轧普卷板日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 铸轧（幕墙卷+普卷板）月累计 | zhu_zha_mu_qiang_pu_juan_ban_yue_lei_ji_rate | 比例 | 0.9426 / 0.9590 / 0.9426 | 月 | 比例 | 铸轧幕墙卷和普卷板组合月累计成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 热轧普卷板日合计 | re_zha_pu_juan_ban_ri_he_ji_rate | 比例 | 0.8471 / 0.8495 / 0.8295 | 日 | 比例 | 公司级热轧普卷板日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 总成品率日合计 | zong_cheng_pin_lv_ri_he_ji_rate | 比例 | 0.8471 / 0.8819 / 0.8376 | 日 | 比例 | 公司级总日成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 总成品率月累计 | zong_cheng_pin_lv_yue_lei_ji_rate | 比例 | 0.8539 / 0.8661 / 0.8534 | 月 | 比例 | 公司级总月累计成品率。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 总成品率目标差 | zong_cheng_pin_lv_mu_biao_cha_rate | 百分点 | -6.61 / -5.39 / -6.66 | 日/月 | 差分 | 总成品率与 92% 目标的差值，源表以百分点展示。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 趋势方向 | qu_shi_fang_xiang | - | ↓ | 日 | 状态 | 成品率表最后一列的趋势方向标记。 | 5月份各车间成品率(38).xlsx | Sheet3 |
| 合金 | he_jin | - | 1050 / 1060 / 3003 | 日 | 维度 | 合同报表右侧质量卷列表的合金维度。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 生产规格 | sheng_chan_gui_ge | - | 4.0*1265 / 6.0*1570 | 日 | 维度 | 质量卷列表的生产规格。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 合计/个 | he_ji_ge_count | 个 | 4 / 5 / 2 | 日 | 求和 | 对应合金规格下的卷数合计。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 不合格卷 | bu_he_ge_juan_count | 卷 | 1 / 3 / 1 | 日 | 求和 | 右侧质量列表中不合格卷数及缺陷括注。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 缺陷类型 | que_xian_lei_xing | - | 孔洞 / 粘板缺铝小卷 / 窄尺 | 日 | 分类 | 不合格卷括号内的缺陷文字，用于 Pareto。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |

## 考勤

5.1-5.5 真实报表归档未发现考勤、打卡、排班、应到、实到、加班、补卡字段；以下字段来自项目现有模型与导入模板，业务口径列入 domain 层，但真实 Excel 来源标为 `TODO`。

| 字段原名 | English slug | 单位 | 数值量级（典型 / 最大 / 最小） | 统计周期 | 聚合方式 | 业务口径 | 来源文件 | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 员工工号 | yuan_gong_gong_hao | - | TODO | 日 | 维度 | 员工主数据匹配键。 | clock_sample.csv / schedule_sample.csv | CSV |
| 排班业务日期 | pai_ban_ye_wu_ri_qi | 日期 | TODO | 日 | 维度 | 员工排班所属业务日期。 | schedule_sample.csv | CSV |
| 班次编码 | ban_ci_bian_ma | - | TODO | 班 | 维度 | 排班与打卡归属班次。 | schedule_sample.csv | CSV |
| 班组编码 | ban_zu_bian_ma | - | TODO | 班 | 维度 | 员工当日归属班组。 | schedule_sample.csv | CSV |
| 车间编码 | che_jian_bian_ma | - | TODO | 班 | 维度 | 员工当日归属车间。 | schedule_sample.csv | CSV |
| 打卡时间 | da_ka_shi_jian | 日期时间 | TODO | 日 | 明细 | 员工上班或下班打卡时间。 | clock_sample.csv | CSV |
| 打卡类型 | da_ka_lei_xing | - | TODO | 日 | 分类 | 上班或下班打卡类型。 | clock_sample.csv | CSV |
| 钉钉打卡记录ID | ding_talk_da_ka_ji_lu_id | - | TODO | 日 | 唯一键 | 钉钉侧打卡记录唯一标识，用于去重。 | clock_sample.csv | CSV |
| 设备标识 | she_bei_biao_shi | - | TODO | 日 | 维度 | 打卡设备标识，参与去重。 | clock_sample.csv | CSV |
| 打卡地点 | da_ka_di_dian | - | TODO | 日 | 维度 | 打卡地点名称。 | clock_sample.csv | CSV |
| 应到人数 | ying_dao_ren_shu_count | 人 | TODO | 班/日 | 求和 | 排班中非休息日员工数。 | backend/app/models/attendance.py | AttendanceSchedule |
| 实到人数 | shi_dao_ren_shu_count | 人 | TODO | 班/日 | 求和 | 有有效出勤结果或班组确认到岗的人数。 | backend/app/models/attendance.py | AttendanceResult |
| 出勤率 | chu_qin_lv | 比例 | TODO | 班/日 | 比例 | 实到人数除以应到人数。 | backend/app/models/attendance.py | AttendanceResult |
| 迟到分钟 | chi_dao_fen_zhong_minute | 分钟 | TODO | 日 | 求和 | 员工迟到分钟数。 | backend/app/models/attendance.py | AttendanceResult |
| 早退分钟 | zao_tui_fen_zhong_minute | 分钟 | TODO | 日 | 求和 | 员工早退分钟数。 | backend/app/models/attendance.py | AttendanceResult |
| 加班分钟 | jia_ban_fen_zhong_minute | 分钟 | TODO | 日 | 求和 | 员工当日加班分钟数。 | backend/app/models/attendance.py | AttendanceResult |
| 加班小时 | jia_ban_xiao_shi_hour | 小时 | TODO | 日 | 比例 | 加班分钟除以 60。 | backend/app/models/attendance.py | AttendanceResult |
| 补卡次数 | bu_ka_ci_shu_count | 次 | TODO | 日/月 | 求和 | 人工覆盖或补卡动作次数，真实归档未提供。 | backend/app/models/attendance.py | AttendanceResult |
| 打卡次数 | da_ka_ci_shu_count | 次 | TODO | 日/月 | 求和 | 上下班打卡记录数。 | backend/app/models/attendance.py | ClockRecord |
| 补卡率 | bu_ka_lv | 比例 | TODO | 日/月 | 比例 | 补卡次数除以打卡次数。 | backend/app/models/attendance.py | AttendanceResult |

## 库存

| 字段原名 | English slug | 单位 | 数值量级（典型 / 最大 / 最小） | 统计周期 | 聚合方式 | 业务口径 | 来源文件 | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 入库园区备料-日合计 | ru_ku_yuan_qu_bei_liao_ri_he_ji_ton | 吨 | 0 / 0 / 0 | 日 | 求和 | 当日进入园区备料库存的重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 入库园区备料-月累计 | ru_ku_yuan_qu_bei_liao_yue_lei_ji_ton | 吨 | 0 / 0 / 0 | 月 | 求和 | 月内进入园区备料库存的累计重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 园区产量-日合计 | yuan_qu_chan_liang_ri_he_ji_ton | 吨 | 301.248 / 301.248 / 0 | 日 | 求和 | 园区侧当天产量合计。 | 鑫泰每日产量5月.xls | 综合报表 |
| 园区产量-月累计 | yuan_qu_chan_liang_yue_lei_ji_ton | 吨 | 1377.735 / 1377.735 / 0 | 月 | 求和 | 园区侧月累计产量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 入园区成品库-日合计 | ru_yuan_qu_cheng_pin_ku_ri_he_ji_ton | 吨 | 301.248 / 301.248 / 84.384 | 日 | 求和 | 当日进入园区成品库的重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 入园区成品库-月累计 | ru_yuan_qu_cheng_pin_ku_yue_lei_ji_ton | 吨 | 1377.735 / 1377.735 / 427.772 | 月 | 求和 | 月内进入园区成品库的累计重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 工业园入库 | gong_ye_yuan_ru_ku_ton | 吨 | 84.384 / 84.384 / 84.384 | 日 | 求和 | 工业园来源的入园区成品库重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 车间转园区 | che_jian_zhuan_yuan_qu_ton | 吨 | 198.582 / 198.582 / 198.582 | 日 | 求和 | 车间转入园区的成品库重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 成品库转园区 | cheng_pin_ku_zhuan_yuan_qu_ton | 吨 | TODO | 日 | 求和 | 成品库转入园区的重量，5.5 行存在但无数值。 | 鑫泰每日产量5月.xls | 综合报表 |
| 客户名称 | ke_hu_ming_cheng | - | 上海德菲勒 / 河南熠晟 | 日 | 维度 | 园区剪切库存或转库明细的客户名称。 | 转 园区剪切_81800_9.xls | 0 |
| 批号 | pi_hao | - | 26RA03170 / 26A02829B | 日 | 维度 | 园区剪切明细的批号。 | 转 园区剪切_81800_9.xls | 0 |
| 合金状态 | he_jin_zhuang_tai | - | 5052 H32 / 3003 H24 | 日 | 维度 | 园区剪切明细的合金与状态。 | 转 园区剪切_81800_9.xls | 0 |
| 成品规格 | cheng_pin_gui_ge | - | 2.0*1000*卡 / 1.6*910*2200 | 日 | 维度 | 园区剪切明细的成品规格。 | 转 园区剪切_81800_9.xls | 0 |
| 卷重 | juan_zhong_kg | 千克 | 7340 / 7340 / 3714 | 日 | 求和 | 园区剪切明细的卷重，源表为 kg 量级。 | 转 园区剪切_81800_9.xls | 0 |
| 净重 | jing_zhong_kg | 千克 | 6784 / 7078 / 3714 | 日 | 求和 | 园区剪切明细的净重，源表为 kg 量级。 | 转 园区剪切_81800_9.xls | 0 |

## 合同

| 字段原名 | English slug | 单位 | 数值量级（典型 / 最大 / 最小） | 统计周期 | 聚合方式 | 业务口径 | 来源文件 | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 日投料量-2050投料 | ri_tou_liao_liang_2050_ton | 吨 | 451 / 451 / 167 | 日 | 求和 | 合同报表顶部 2050 当日投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 日投料量-1850投料 | ri_tou_liao_liang_1850_ton | 吨 | 135 / 291 / 135 | 日 | 求和 | 合同报表顶部 1850 当日投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 日投料量-1450投料 | ri_tou_liao_liang_1450_ton | 吨 | 139 / 170 / 113 | 日 | 求和 | 合同报表顶部 1450 当日投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 日投料量-1650投料 | ri_tou_liao_liang_1650_ton | 吨 | 185 / 283 / 185 | 日 | 求和 | 合同报表顶部 1650 当日投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 日投料量-中厚板 | ri_tou_liao_liang_zhong_hou_ban_ton | 吨 | 0 / 0 / 0 | 日 | 求和 | 合同报表顶部中厚板当日投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 日投料量-工业园 | ri_tou_liao_liang_gong_ye_yuan_ton | 吨 | 154 / 226 / 73 | 日 | 求和 | 合同报表顶部工业园当日投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 当天合同 | dang_tian_he_tong_ton | 吨 | 635 / 1768 / 0 | 日 | 求和 | 当天新增或接收的合同吨位。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 当天合同-热轧 | dang_tian_he_tong_re_zha_ton | 吨 | 147 / 147 / 0 | 日 | 求和 | 当天合同中热轧部分吨位。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 总余合同量 | zong_yu_he_tong_liang_ton | 吨 | 30810 / 32376 / 30788 | 日 | 最大 | 截至报表日尚未完成的合同余量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 月投料量-2050投料 | yue_tou_liao_liang_2050_ton | 吨 | 1657 / 1657 / 440 | 月 | 求和 | 合同报表顶部 2050 月累计投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 月投料量-1850投料 | yue_tou_liao_liang_1850_ton | 吨 | 1158 / 1158 / 267 | 月 | 求和 | 合同报表顶部 1850 月累计投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 月投料量-1450投料 | yue_tou_liao_liang_1450_ton | 吨 | 694 / 694 / 170 | 月 | 求和 | 合同报表顶部 1450 月累计投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 月投料量-1650投料 | yue_tou_liao_liang_1650_ton | 吨 | 1075 / 1075 / 283 | 月 | 求和 | 合同报表顶部 1650 月累计投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 月投料量-工业园 | yue_tou_liao_liang_gong_ye_yuan_ton | 吨 | 773 / 773 / 218 | 月 | 求和 | 合同报表顶部工业园月累计投料量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 月总计合同 | yue_zong_ji_he_tong_ton | 吨 | 2918 / 2918 / 1768 | 月 | 求和 | 当月累计合同吨位。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 月总计合同-热轧 | yue_zong_ji_he_tong_re_zha_ton | 吨 | 188 / 188 / 0 | 月 | 求和 | 当月累计合同中热轧部分吨位。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 坯总量 | pi_zong_liang_ton | 吨 | 122 / 122 / 0 | 月 | 求和 | 合同报表顶部坯料总量。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 牌号 | pai_hao | - | 1060 / 1100 / 3003 / 5052 | 日/月 | 维度 | 合同报表中按牌号拆分的合同或投料维度。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 规格 | gui_ge | mm | 0.9 / 1.25 / 1.4 | 日/月 | 维度 | 合同报表中按厚度或规格拆分的维度。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 吨位 | dun_wei_ton | 吨 | 718 / 4587 / 10 | 日/月 | 求和 | 牌号与规格组合下的合同吨位或计划吨位。 | 河南鑫泰合同报表_64542_704.xlsx | 5-5 |
| 发货-日合计 | fa_huo_ri_he_ji_ton | 吨 | 0 / 150.986 / 0 | 日 | 求和 | 综合日报中当日发货重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 发货-月累计 | fa_huo_yue_lei_ji_ton | 吨 | 0 / 433.972 / 0 | 月 | 求和 | 综合日报中月累计发货重量。 | 鑫泰每日产量5月.xls | 综合报表 |
| 接合同量-日合计 | jie_he_tong_liang_ri_he_ji_ton | 吨 | 0 / TODO / 0 | 日 | 求和 | 综合日报中接合同量日合计，5.5 合计行缺月累计列。 | 鑫泰每日产量5月.xls | 综合报表 |
| 接合同量-月累计 | jie_he_tong_liang_yue_lei_ji_ton | 吨 | TODO | 月 | 求和 | 综合日报中接合同量月累计，5.5 合计行为空，待确认。 | 鑫泰每日产量5月.xls | 综合报表 |

## 成本

| 字段原名 | English slug | 单位 | 数值量级（典型 / 最大 / 最小） | 统计周期 | 聚合方式 | 业务口径 | 来源文件 | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 车间 | che_jian | - | 铸轧 / 冷轧 / 精整 | 日 | 维度 | 耗材表的一级车间维度。 | 耗材表.xls | 能耗 |
| 机台 | ji_tai | - | 铸二 / 2050 / 新19辊 | 日 | 维度 | 耗材表的机台或产线维度。 | 耗材表.xls | 能耗 |
| 日产量 | ri_chan_liang_ton | 吨 | 85.13 / 302.84 / 24.18 | 日 | 求和 | 耗材表中用于计算单位耗材的当日产量。 | 耗材表.xls | 能耗 |
| 月产量 | yue_chan_liang_ton | 吨 | 669.59 / 1100.21 / 61.86 | 月 | 求和 | 耗材表中用于月累计单位耗材的月产量。 | 耗材表.xls | 能耗 |
| 电耗 | dian_hao_kwh_per_ton | kWh/t | 79.40 / 283.10 / 5.05 | 日 | 比例 | 耗材表中按产量折算的吨电耗。 | 耗材表.xls | 能耗 |
| 电指标 | dian_zhi_biao_kwh_per_ton | kWh/t | 75 / 170 / 7 | 日 | 目标值 | 吨电耗考核指标。 | 耗材表.xls | 能耗 |
| 电耗对比 | dian_hao_dui_bi_kwh_per_ton | kWh/t | 4.40 / 193.10 / -120.00 | 日 | 差分 | 实际电耗与电指标差值。 | 耗材表.xls | 能耗 |
| 天燃气/气耗 | tian_ran_qi_qi_hao_m3_per_ton | m³/t | 124.23 / 350.00 / 22.09 | 日 | 比例 | 耗材表中按产量折算的吨气耗。 | 耗材表.xls | 能耗 |
| 天燃气指标 | tian_ran_qi_zhi_biao_m3_per_ton | m³/t | 85 / 95 / 24 | 日 | 目标值 | 吨气耗考核指标。 | 耗材表.xls | 能耗 |
| 天燃气对比 | tian_ran_qi_dui_bi_m3_per_ton | m³/t | 39.23 / 60.18 / -84.00 | 日 | 差分 | 实际气耗与气耗指标差值。 | 耗材表.xls | 能耗 |
| 1系/气耗 | yi_xi_qi_hao_m3_per_ton | m³/t | 109.54 / 124.23 / 0.50 | 日 | 比例 | 1 系产品对应吨气耗或辅助消耗。 | 耗材表.xls | 能耗 |
| 3系/气耗 | san_xi_qi_hao_m3_per_ton | m³/t | 115.60 / 200.00 / 2.70 | 日 | 比例 | 3 系产品对应吨气耗或辅助消耗。 | 耗材表.xls | 能耗 |
| 5系/气耗 | wu_xi_qi_hao_m3_per_ton | m³/t | 124.23 / 124.23 / 0.37 | 日 | 比例 | 5 系产品对应吨气耗或辅助消耗。 | 耗材表.xls | 能耗 |
| 液化气吨耗/公斤 | ye_hua_qi_dun_hao_kg_per_ton | kg/t | 2.7 / 3.0 / 0.0 | 日 | 比例 | 每吨产品消耗液化气重量。 | 耗材表.xls | 能耗 |
| 钛丝吨耗/公斤 | tai_si_dun_hao_kg_per_ton | kg/t | 4.7 / 4.7 / 0.0 | 日 | 比例 | 每吨产品消耗钛丝重量。 | 耗材表.xls | 能耗 |
| 钢带吨耗/公斤 | gang_dai_dun_hao_kg_per_ton | kg/t | 0.37 / 0.37 / 0.0 | 日 | 比例 | 每吨产品消耗钢带重量。 | 耗材表.xls | 能耗 |
| 镁锭吨耗/公斤 | mei_ding_dun_hao_kg_per_ton | kg/t | 10.3 / 10.3 / 9.7 | 日 | 比例 | 每吨产品消耗镁锭重量。 | 耗材表.xls | 能耗 |
| 锰剂吨耗/公斤 | meng_ji_dun_hao_kg_per_ton | kg/t | 11.3 / 11.3 / 0.0 | 日 | 比例 | 每吨产品消耗锰剂重量。 | 耗材表.xls | 能耗 |
| 铁剂吨耗/公斤 | tie_ji_dun_hao_kg_per_ton | kg/t | TODO | 日 | 比例 | 每吨产品消耗铁剂重量，5.5 可见表头但有效值不足。 | 耗材表.xls | 能耗 |
| 铜剂吨耗/公斤 | tong_ji_dun_hao_kg_per_ton | kg/t | TODO | 日 | 比例 | 每吨产品消耗铜剂重量，5.5 可见表头但有效值不足。 | 耗材表.xls | 能耗 |
| 液压油日/桶 | ye_ya_you_ri_bucket | 桶 | 0 / 0 / 0 | 日 | 求和 | 当日液压油用量。 | 耗材表.xls | 能耗 |
| 液压油月/桶 | ye_ya_you_yue_bucket | 桶 | 0 / 0 / 0 | 月 | 求和 | 月累计液压油用量。 | 耗材表.xls | 能耗 |
| 液压油指标 | ye_ya_you_zhi_biao_bucket | 桶 | 1.5 / 15.0 / 0.5 | 日/月 | 目标值 | 液压油用量指标。 | 耗材表.xls | 能耗 |
| 液压油对比 | ye_ya_you_dui_bi_bucket | 桶 | -1.5 / 0.0 / -11.0 | 日/月 | 差分 | 液压油实际用量与指标差值。 | 耗材表.xls | 能耗 |
| 齿轮油日/桶 | chi_lun_you_ri_bucket | 桶 | 0 / 0 / 0 | 日 | 求和 | 当日齿轮油用量。 | 耗材表.xls | 能耗 |
| 齿轮油月/桶 | chi_lun_you_yue_bucket | 桶 | 0 / 0 / 0 | 月 | 求和 | 月累计齿轮油用量。 | 耗材表.xls | 能耗 |
| 齿轮油指标 | chi_lun_you_zhi_biao_bucket | 桶 | 3 / 20 / 3 | 日/月 | 目标值 | 齿轮油用量指标。 | 耗材表.xls | 能耗 |
| 齿轮油对比 | chi_lun_you_dui_bi_bucket | 桶 | -1 / 2 / -14 | 日/月 | 差分 | 齿轮油实际用量与指标差值。 | 耗材表.xls | 能耗 |
| 轧制油吨耗/公斤 | zha_zhi_you_dun_hao_kg_per_ton | kg/t | 0.089 / 10.000 / 0.071 | 日 | 比例 | 冷轧、精整等工序每吨产品轧制油消耗。 | 耗材表.xls | 能耗 |
| 飞滤剂吨耗/公斤 | fei_lv_ji_dun_hao_kg_per_ton | kg/t | 0.059 / 5.000 / 0.059 | 日 | 比例 | 每吨产品飞滤剂消耗。 | 耗材表.xls | 能耗 |
| 硅藻土吨耗/公斤 | gui_zao_tu_dun_hao_kg_per_ton | kg/t | 1.238 / 1.238 / 0.340 | 日 | 比例 | 每吨产品硅藻土消耗。 | 耗材表.xls | 能耗 |
| 白土吨耗/公斤 | bai_tu_dun_hao_kg_per_ton | kg/t | 0.082 / 0.101 / 0.020 | 日 | 比例 | 每吨产品白土消耗。 | 耗材表.xls | 能耗 |
| 滤布日用/米 | lv_bu_ri_yong_meter | 米 | 0.008 / 0.010 / 0.008 | 日 | 求和 | 当日滤布使用长度。 | 耗材表.xls | 能耗 |
| 高温胶带日用/卷 | gao_wen_jiao_dai_ri_yong_roll | 卷 | 1 / 6 / 1 | 日 | 求和 | 当日高温胶带使用卷数。 | 耗材表.xls | 能耗 |
| 再生油出/公斤 | zai_sheng_you_chu_kg | 千克 | TODO | 日 | 求和 | 再生油产出重量，5.5 有表头但有效值不足。 | 耗材表.xls | 能耗 |
| 再生油回/公斤 | zai_sheng_you_hui_kg | 千克 | TODO | 日 | 求和 | 再生油回收重量，5.5 有表头但有效值不足。 | 耗材表.xls | 能耗 |

## Unresolved

| 字段原名 | English slug | 待确认点 | 已知来源 | 处理 |
| --- | --- | --- | --- | --- |
| 考勤真实 Excel | attendance_real_excel | 5.1-5.5 归档未发现考勤类 Excel，无法确认真实字段名和单位。 | D:\鑫泰报表\5.1-5.5 | TODO：等待考勤归档或钉钉导出样例。 |
| 峰谷平尖电量 | peak_valley_real_fields | 5 天归档未出现峰/谷/平/尖字段，calculator 仅保留纯函数接口。 | D:\鑫泰报表\5.1-5.5 | TODO：等待分时电表报表。 |
| 园区气 | yuan_qu_qi_m3 | 5.5 园区+新厂表气区存在空值，无法判断是否为 0 或漏填。 | 园区电+新厂电(1).xls / 园区+新厂 | TODO：由业务确认。 |
| 南线电耗 | nan_xian_dian_hao_kwh | 南线电耗 5.1-5.5 为 5.0-7.5，明显小于其他车间，可能是倍率或单位问题。 | 5月份各车间能耗统计表.xls / 用量 | TODO：确认电表倍率。 |
| 日均 | ri_jun_ton | 综合日报有字段但多为空或混排，计算基准未确认。 | 鑫泰每日产量5月.xls / 综合报表 | TODO：确认按自然日还是生产日。 |
| 接合同量月累计 | jie_he_tong_liang_yue_lei_ji_ton | 5.5 合计行未见明确月累计值。 | 鑫泰每日产量5月.xls / 综合报表 | TODO：确认是否来自合同报表月总计合同。 |
| 成品库转园区 | cheng_pin_ku_zhuan_yuan_qu_ton | 5.5 行存在但无数值。 | 鑫泰每日产量5月.xls / 综合报表 | TODO：等待有值归档。 |
| 铁剂吨耗 | tie_ji_dun_hao_kg_per_ton | 耗材表有表头但 5.5 有效值不足。 | 耗材表.xls / 能耗 | TODO：等待有值归档。 |
| 铜剂吨耗 | tong_ji_dun_hao_kg_per_ton | 耗材表有表头但 5.5 有效值不足。 | 耗材表.xls / 能耗 | TODO：等待有值归档。 |
| 再生油出 | zai_sheng_you_chu_kg | 耗材表有表头但 5.5 有效值不足。 | 耗材表.xls / 能耗 | TODO：等待有值归档。 |
| 再生油回 | zai_sheng_you_hui_kg | 耗材表有表头但 5.5 有效值不足。 | 耗材表.xls / 能耗 | TODO：等待有值归档。 |
| 机列吨气耗对比基准 | ji_lie_dun_qi_hao_dui_bi_base | 机列能耗表”对比”未说明是对昨日还是指标。 | 铸二5月5日能耗表.xls / Sheet2 | TODO：业务确认。 |

## Calculator 口径映射 (A2 新增 2026-05-16)

| Calculator 函数 | 对应字段 slug | 公式 | 防护 |
| --- | --- | --- | --- |
| yield_rate | yue_cheng_pin_lv | chan_liang / tou_liao_liang | 分母=0 返回 0 |
| scrap_rate | chan_sheng_fei_liao_ri_he_ton / tou_liao_liang_ri_he_ton | fei_liao / tou_liao | 分母=0 返回 0 |
| shift_output | ri_chan_liang_ri_he_ton (多班次) | Σ ban_ci_chan_liang | None→0 |
| daily_cumulative_output | ri_chan_liang_ri_he_ton (多车间) | Σ ri_chan_liang | None→0 |
| monthly_cumulative_output | ri_chan_liang_lei_ji_ton | Σ yue_nei_ri_chan_liang | None→0 |
| unit_energy_consumption | dian_hao_kwh_per_ton | hao_dian_liang / chan_liang | 分母=0 返回 0 |
| peak_valley_split | 峰谷平尖各字段 | 尖+峰+平+谷→总量+各占比 | 总量=0 占比=0 |
| cross_workshop_aggregate | 各车间电量 | Σ che_jian_neng_hao → total+count+max | — |
| defect_rate | bu_he_ge_juan / he_ji_juan | 不合格/合计 | 分母=0 返回 0 |
| pareto_top_n | 缺陷类型计数 | 降序排列+累计占比 | 空 dict 返回 [] |
| disposition_breakdown | 处置类型计数 | 各类型/总数 | 总数=0 返回空 |
| attendance_rate | shi_dao / ying_dao | 实到/应到 | 分母=0 返回 0 |
| overtime_hours | jia_ban_fen_zhong | 分钟/60 | — |
| makeup_card_rate | bu_ka_ci_shu / da_ka_ci_shu | 补卡/打卡 | 分母=0 返回 0 |
| reporting_rate | 已报班次 / 应报班次 | reported/expected | 分母=0 返回 0 |
| day_over_day_change | 今日产量 vs 昨日产量 | (today-yesterday)/yesterday | 昨日=0 返回 0 |
| month_average_daily_output | 月累计 / 有效天数 | monthly_total/active_days | 天数=0 返回 0 |
| contract_fulfillment_rate | 已交付 / 合同量 | delivered/contract | 合同=0 返回 0 |
