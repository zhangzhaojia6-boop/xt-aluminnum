# MES 导出样例说明

## 适用范围
- 第五轮最小版 MES 导出文件接入
- 支持 CSV / XLSX

## 文件字段
必填字段：
- business_date：业务日期，格式 `YYYY-MM-DD`
- workshop_code：车间编码
- shift_code：班次编码
- metric_code：指标编码（建议使用 `output_weight` 表示产量）
- metric_name：指标名称
- metric_value：指标值（数值）

可选字段：
- unit：单位（如 吨）
- source_row_no：来源行号

## 样例文件
请使用：
- `mes_export_sample.csv`

## 导入方式
1. 登录系统
2. 进入「数据导入」
3. 选择导入类型 `MES导出导入 (mes_export)`
4. 上传文件并导入

## 说明
- 导入后会生成 `import_batches` / `import_rows`
- 同步写入 `mes_import_records`
- 原始行数据会保存到 `raw_payload`
