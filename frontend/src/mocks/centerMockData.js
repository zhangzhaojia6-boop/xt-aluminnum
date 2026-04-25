export const entryHomeMock = {
  kpis: [
    { label: '待填任务', value: 4, unit: '项', trend: '今日班次' },
    { label: '已提交', value: 18, unit: '单', trend: '已同步' },
    { label: '异常待补', value: 3, unit: '条', trend: '需补录' }
  ],
  tasks: [
    { id: 'cast-a', name: '铸造一线报数', shift: '白班', status: '待填' },
    { id: 'finish-b', name: '精整区补录', shift: '白班', status: '异常待补' },
    { id: 'stock', name: '成品库交付', shift: '白班', status: '已提交' }
  ]
}

export const reviewOverviewMock = {
  kpis: [
    { label: '今日产量', value: '5,824', unit: '吨', trend: '+8.6%' },
    { label: '订单达成率', value: '96.7', unit: '%', trend: '+2.1%' },
    { label: '综合成品率', value: '98.2', unit: '%', trend: '+1.3%' },
    { label: '在制产线', value: 8, unit: '条', trend: '运行' },
    { label: '异常数', value: 12, unit: '项', trend: '待处置' },
    { label: '待审核', value: 18, unit: '单', trend: '待确认' },
    { label: '已交付', value: 23, unit: '车', trend: '今日' }
  ],
  lines: [
    { id: 'cast-1', name: '铸造一线', status: '运行', source: 'operator' },
    { id: 'cast-2', name: '铸造二线', status: '运行', source: 'operator' },
    { id: 'finish', name: '精整区', status: '关注', source: 'owner' },
    { id: 'stock', name: '成品库', status: '正常', source: 'system' }
  ],
  system: [
    { label: '数据接入', status: '正常' },
    { label: '系统性能', status: '良好' },
    { label: '任务进度', status: '运行中' },
    { label: '消息服务', status: '正常' }
  ]
}

export const reviewTaskMock = {
  tabs: ['待审', '已审', '已驳回'],
  rows: [
    {
      id: 'r-001',
      workshop: '铸造一线',
      shift: '白班',
      submittedAt: '09:20',
      anomalyType: '产量波动',
      aiAdvice: '辅助建议：核对机台停机时长',
      risk: '中',
      status: '待审'
    },
    {
      id: 'r-002',
      workshop: '精整区',
      shift: '夜班',
      submittedAt: '08:45',
      anomalyType: '良率偏低',
      aiAdvice: '辅助建议：查看缺陷分类',
      risk: '高',
      status: '待审'
    },
    {
      id: 'r-003',
      workshop: '成品库',
      shift: '白班',
      submittedAt: '08:30',
      anomalyType: '交付差异',
      aiAdvice: '辅助建议：比对出库单',
      risk: '低',
      status: '已审'
    }
  ]
}

export const factoryBoardMock = {
  source: 'fallback',
  updatedAt: '2024-05-21 10:30',
  kpis: [
    { label: '今日产量', value: '5,824', unit: '吨', trend: '+8.6%', tone: 'success' },
    { label: '平均成品率', value: '92.3', unit: '%', trend: '厂级平均', tone: 'warning' },
    { label: '平均良率', value: '96.2', unit: '%', trend: '+1.3%', tone: 'success' },
    { label: '在制产线', value: 6, unit: '条', trend: '运行中', tone: 'processing' },
    { label: '异常数', value: 4, unit: '项', trend: '需关注', tone: 'warning' },
    { label: '待审数', value: 18, unit: '单', trend: '待确认', tone: 'processing' }
  ],
  rows: [
    { id: 'cast-1', name: '铸造一线', source: 'operator', output: '1,265', yieldRate: '92.1%', qualityRate: '96.3%', exceptionCount: 1, trend: [12, 18, 15, 22, 19, 28, 24], tone: 'warning' },
    { id: 'cast-2', name: '铸造二线', source: 'operator', output: '1,132', yieldRate: '94.6%', qualityRate: '97.1%', exceptionCount: 0, trend: [10, 12, 16, 14, 18, 20, 23], tone: 'success' },
    { id: 'smelt', name: '熔铸区', source: 'system', output: '986', yieldRate: '91.3%', qualityRate: '95.6%', exceptionCount: 2, trend: [9, 11, 10, 15, 13, 18, 16], tone: 'danger' },
    { id: 'hot-roll', name: '热轧区', source: 'mes', output: '1,432', yieldRate: '90.4%', qualityRate: '94.2%', exceptionCount: 1, trend: [18, 15, 19, 22, 20, 24, 27], tone: 'warning' },
    { id: 'straighten', name: '拉矫区', source: 'operator', output: '1,009', yieldRate: '93.0%', qualityRate: '96.0%', exceptionCount: 0, trend: [8, 12, 11, 14, 18, 17, 19], tone: 'success' },
    { id: 'stock', name: '成品库', source: 'import', output: '-', yieldRate: '-', qualityRate: '-', exceptionCount: 0, trend: [7, 8, 10, 9, 11, 10, 12], tone: 'success' }
  ],
  total: { name: '合计 / 平均', output: '5,824', yieldRate: '92.3%', qualityRate: '96.2%', exceptionCount: 4, trend: [64, 76, 81, 96, 99, 117, 121], source: 'system' },
  risks: [
    { label: '今日高风险产线', value: '熔铸区、热轧区', status: '高风险', tone: 'danger' },
    { label: '缺报 / 异常', value: '缺报 1 项 · 异常 4 项', status: '需跟进', tone: 'warning' },
    { label: '待审摘要', value: '18 单待审核', status: '待审', tone: 'processing' }
  ],
  events: [
    { time: '10:12', source: 'exception', text: '熔铸区成品率低于厂级均值' },
    { time: '09:50', source: 'system', text: '热轧区良率连续两小时波动' },
    { time: '09:20', source: 'operator', text: '铸造一线补录异常已进入审阅' }
  ],
  caliber: [
    '本页为厂级观察面',
    '数据来自主流程提交后的聚合 / dashboard 读模型',
    '本页不承接生产事实写入',
    'fallback 状态下仅用于前端验收'
  ]
}

export const reportsCenterMock = {
  source: 'fallback',
  updatedAt: '2024-05-21 10:30',
  businessDate: '2024-05-21',
  scope: 'auto_confirmed',
  kpis: [
    { label: '日产量', value: '5,824', unit: '吨', trend: '+8.6%', tone: 'success' },
    { label: '订单达成率', value: '96.7', unit: '%', trend: '+2.1%', tone: 'success' },
    { label: '综合成品率', value: '98.2', unit: '%', trend: '+1.3%', tone: 'success' },
    { label: '已生成日报数', value: 3, unit: '份', trend: 'auto_confirmed', tone: 'processing' },
    { label: '已交付 / 待分发', value: '20 / 3', unit: '车', trend: '今日交付', tone: 'warning' },
    { label: '阻塞项 / 待审项', value: '1 / 18', unit: '项', trend: '需复核', tone: 'danger' }
  ],
  trend: [
    { day: '05-15', output: 4920, delivered: 18, pending: 4 },
    { day: '05-16', output: 5180, delivered: 19, pending: 3 },
    { day: '05-17', output: 5060, delivered: 18, pending: 4 },
    { day: '05-18', output: 5360, delivered: 20, pending: 3 },
    { day: '05-19', output: 5520, delivered: 21, pending: 2 },
    { day: '05-20', output: 5710, delivered: 20, pending: 3 },
    { day: '05-21', output: 5824, delivered: 20, pending: 3 }
  ],
  deliverySummary: [
    { label: '计划交付', value: '23', unit: '车', tone: 'info' },
    { label: '已交付', value: '20', unit: '车', tone: 'success' },
    { label: '待分发', value: '3', unit: '车', tone: 'warning' },
    { label: '交付失败', value: '1', unit: '项', tone: 'danger' }
  ],
  deliveryRows: [
    {
      id: 'report-factory-day',
      name: '厂级生产日报',
      businessDate: '2024-05-21',
      scopeText: '全厂',
      caliber: 'auto_confirmed',
      generationStatus: '已生成',
      deliveryStatus: '待分发',
      exportStatus: 'PDF / Excel 待导出',
      receivers: '管理层、总统计',
      updatedAt: '10:30',
      source: 'system',
      reason: '等待人工确认接收对象'
    },
    {
      id: 'report-workshop-confirmed',
      name: '车间交付日报',
      businessDate: '2024-05-21',
      scopeText: '铸造 / 精整',
      caliber: '已自动确认数据口径',
      generationStatus: '已生成',
      deliveryStatus: '已交付',
      exportStatus: '已导出',
      receivers: '车间主任、生产主管',
      updatedAt: '10:12',
      source: 'system',
      reason: 'fallback 样例状态，仅用于读面验收'
    },
    {
      id: 'report-quality-blocked',
      name: '质量异常日报',
      businessDate: '2024-05-21',
      scopeText: '质量 / 告警',
      caliber: 'auto_confirmed',
      generationStatus: '阻塞',
      deliveryStatus: '交付失败',
      exportStatus: '未导出',
      receivers: '质量负责人',
      updatedAt: '09:50',
      source: 'exception',
      reason: '异常未关闭 2 项，未执行真实发送'
    },
    {
      id: 'report-shift-pending',
      name: '班次补齐日报',
      businessDate: '2024-05-21',
      scopeText: '夜班 / 热轧',
      caliber: 'auto_confirmed',
      generationStatus: '待生成',
      deliveryStatus: '待分发',
      exportStatus: '未导出',
      receivers: '总统计、热轧车间',
      updatedAt: '09:20',
      source: 'operator',
      reason: '缺报班次 1 项，待审记录 18 单'
    }
  ],
  blockers: [
    { label: '缺报班次', value: '1 项', status: '待补齐', tone: 'warning', routeName: 'review-task-center' },
    { label: '待审记录', value: '18 单', status: '待审', tone: 'processing', routeName: 'review-task-center' },
    { label: '异常未关闭', value: '2 项', status: '阻塞', tone: 'danger', routeName: 'review-quality-center' },
    { label: '数据源 fallback / mixed', value: '当前 fallback', status: '需复核', tone: 'warning', routeName: 'factory-dashboard' },
    { label: '交付失败原因', value: '接收对象待确认，未执行真实发送', status: '失败', tone: 'danger', routeName: 'review-report-center' }
  ],
  actions: {
    exportPdf: 'disabled',
    exportExcel: 'disabled',
    send: 'disabled',
    regenerate: 'disabled'
  }
}

export const reportDeliveryMock = reportsCenterMock

export const qualityCenterMock = {
  rows: [
    { id: 'q-001', time: '10:12', source: '模具一线', type: '成品质量', detail: '成品毛刺偏高', severity: '高', status: '处理中' },
    { id: 'q-002', time: '09:50', source: '热轧区', type: '设备告警', detail: '轧机轴承温度异常', severity: '中', status: '处理中' },
    { id: 'q-003', time: '09:40', source: '精整区', type: '质量异常', detail: '板面氧化斑点', severity: '中', status: '待处置' },
    { id: 'q-004', time: '09:30', source: '质检系统', type: '不合格品', detail: '不合格品率 2.35% 超标', severity: '高', status: '处理中' },
    { id: 'q-005', time: '08:50', source: '性能区', type: '设备异常', detail: '焊机焊接电流波动', severity: '低', status: '已处置' },
    { id: 'q-006', time: '昨天 23:10', source: '包装区', type: '物流异常', detail: '包装破损率上升', severity: '低', status: '已关闭' }
  ],
  flow: [
    { title: 'AI 辅助分诊', body: '识别告警类型、分析根因、评估影响范围。' },
    { title: '建议处理方案', body: '基于知识库与历史经验形成辅助建议。' },
    { title: '执行与跟踪', body: '记录处置过程与结果，保留追踪线索。' },
    { title: '关闭与沉淀', body: '验证问题解决后关闭，沉淀经验知识。' }
  ]
}

export const costCenterMock = {
  caliberTabs: ['铸二', '铸三', '精整', '热轧', '拉矫', '2050', '1650', '1850', '花纹板'],
  kpis: [
    { label: '吨铝成本', value: '8,560', unit: '元/吨', tone: 'info' },
    { label: '人工', value: '1,245', unit: '元/吨', tone: 'neutral' },
    { label: '电耗', value: '632', unit: '元/吨', tone: 'neutral' },
    { label: '天然气', value: '324', unit: '元/吨', tone: 'neutral' },
    { label: '辅材/损耗', value: '156', unit: '元/吨', tone: 'neutral' }
  ],
  trend: [
    { day: '05-15', parts: [3800, 1100, 900, 1000, 850, 900] },
    { day: '05-16', parts: [3900, 1060, 920, 980, 810, 880] },
    { day: '05-17', parts: [3650, 1030, 890, 960, 760, 820] },
    { day: '05-18', parts: [3500, 990, 860, 920, 720, 780] },
    { day: '05-19', parts: [3550, 1010, 880, 940, 760, 790] },
    { day: '05-20', parts: [3600, 1040, 900, 960, 790, 820] },
    { day: '05-21', parts: [3700, 1060, 910, 970, 810, 850] }
  ],
  cumulative: [
    { label: '原料', value: '5,120', ratio: '59.8%', color: 'primary' },
    { label: '电耗', value: '1,260', ratio: '14.7%', color: 'success' },
    { label: '天然气', value: '820', ratio: '9.6%', color: 'info' },
    { label: '人工', value: '1,245', ratio: '14.5%', color: 'accent' },
    { label: '辅材/损耗', value: '156', ratio: '1.8%', color: 'warning' },
    { label: '折旧', value: '159', ratio: '1.9%', color: 'neutral' },
    { label: '合计', value: '8,760', ratio: '100.0%', color: 'total' }
  ]
}

export const ingestionCenterMock = {
  updatedAt: '2024-05-21 10:30',
  sources: [
    { name: 'MES', source: 'mes', status: '已映射', tone: 'success' },
    { name: 'PLC', source: 'system', status: '已映射', tone: 'success' },
    { name: '质检系统', source: 'system', status: '已映射', tone: 'success' },
    { name: '能耗系统', source: 'system', status: '已映射', tone: 'success' },
    { name: 'ERP', source: 'import', status: '已映射', tone: 'success' },
    { name: '手工录入', source: 'operator', status: '部分字段', tone: 'warning' }
  ],
  fields: [
    { name: '订单编号', type: 'String', sourceField: 'order_id', mapping: '直接映射', check: '通过' },
    { name: '产品编码', type: 'String', sourceField: 'product_code', mapping: '直接映射', check: '通过' },
    { name: '实际重量', type: 'Float', sourceField: 'actual_weight', mapping: '单位转换(kg→t)', check: '通过' },
    { name: '生产数量', type: 'Int', sourceField: 'qty', mapping: '直接映射', check: '通过' },
    { name: '创建时间', type: 'DateTime', sourceField: 'create_time', mapping: '格式转换', check: '通过' },
    { name: '班次', type: 'String', sourceField: 'shift_code', mapping: '字典映射', check: '通过' },
    { name: '产线', type: 'String', sourceField: 'line_code', mapping: '直接映射', check: '通过' }
  ],
  overview: [
    { label: '总数据量', value: '96,327', unit: '条', tone: 'info' },
    { label: '成功导入', value: '84,542', unit: '条', tone: 'success' },
    { label: '成功率', value: '88.54', unit: '%', tone: 'success' },
    { label: '失败记录', value: '4,321', unit: '条', tone: 'danger' },
    { label: '待处理', value: '12', unit: '条', tone: 'warning' }
  ],
  history: [
    { id: 'h-001', time: '05-21 10:15', source: 'MES', task: 'mes_20240521_1015.csv', total: '12,845', success: '12,301', failed: '544', status: '已完成', reason: '544 行产品编码缺失' },
    { id: 'h-002', time: '05-21 09:30', source: 'PLC', task: 'plc_20240521_0930.csv', total: '8,542', success: '8,522', failed: '20', status: '已完成', reason: '20 行时间戳格式异常' },
    { id: 'h-003', time: '05-21 08:50', source: '质检系统', task: 'qc_20240521_0850.xlsx', total: '6,321', success: '6,301', failed: '20', status: '已完成', reason: '20 行缺少批次号' },
    { id: 'h-004', time: '05-21 08:20', source: '手工录入', task: 'manual_input_20240521.xlsx', total: '1,111', success: '1,089', failed: '22', status: '部分失败', reason: '22 行字段口径待确认' },
    { id: 'h-005', time: '05-21 07:50', source: '能耗系统', task: 'energy_20240521_0750.csv', total: '5,210', success: '5,210', failed: '0', status: '已完成', reason: '无失败记录' }
  ]
}
