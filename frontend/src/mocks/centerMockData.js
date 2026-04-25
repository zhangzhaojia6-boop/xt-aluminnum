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
  source: 'fallback',
  businessDate: '2024-05-21',
  updatedAt: '2024-05-21 10:30',
  kpis: [
    { label: '今日告警数', value: 10, unit: '项', trend: '含昨日延续', tone: 'warning' },
    { label: '高风险告警', value: 2, unit: '项', trend: '未关闭', tone: 'danger' },
    { label: '待处置', value: 2, unit: '项', trend: '需审阅确认', tone: 'warning' },
    { label: '处理中', value: 3, unit: '项', trend: '人工跟进', tone: 'processing' },
    { label: '已关闭', value: 4, unit: '项', trend: '今日闭环', tone: 'success' },
    { label: '影响日报交付项', value: 2, unit: '项', trend: '阻塞日报', tone: 'danger' }
  ],
  alerts: [
    {
      id: 'q-001',
      time: '10:12',
      source: '模具一线',
      sourceType: 'operator',
      type: '成品质量',
      detail: '成品毛刺偏高，需复核模具磨损与首检记录',
      severity: '高',
      status: '处理中',
      impactScope: '铸造一线 / 当班日报',
      owner: '质量负责人',
      deliveryImpact: '影响日报交付',
      reason: '高风险未关闭，日报需人工确认',
      tone: 'danger'
    },
    {
      id: 'q-002',
      time: '09:50',
      source: '热轧区',
      sourceType: 'system',
      type: '设备告警',
      detail: '轧机轴承温度异常，连续两次越过预警线',
      severity: '中',
      status: '处理中',
      impactScope: '热轧区 / 产线看板',
      owner: '热轧班长',
      deliveryImpact: '需跟踪',
      reason: '等待现场复核温度曲线',
      tone: 'warning'
    },
    {
      id: 'q-003',
      time: '09:40',
      source: '精整区',
      sourceType: 'operator',
      type: '质检补录',
      detail: '板面氧化斑点记录缺少批次照片，待补齐凭证',
      severity: '中',
      status: '待处置',
      impactScope: '精整区 / 审阅任务',
      owner: '审阅员',
      deliveryImpact: '影响日报交付',
      reason: '待补齐凭证后进入审阅',
      tone: 'warning'
    },
    {
      id: 'q-004',
      time: '09:30',
      source: '质检系统',
      sourceType: 'exception',
      type: '不合格品',
      detail: '不合格品率 2.35% 超出试跑阈值，需人工确认口径',
      severity: '高',
      status: '阻塞',
      impactScope: '质量异常日报',
      owner: '质量经理',
      deliveryImpact: '阻塞日报',
      reason: '异常未关闭，质量异常日报未执行真实发送',
      tone: 'danger'
    },
    {
      id: 'q-005',
      time: '08:50',
      source: '性能区',
      sourceType: 'system',
      type: '设备异常',
      detail: '焊机焊接电流波动，处置记录待复核',
      severity: '低',
      status: '已处置',
      impactScope: '性能区',
      owner: '设备员',
      deliveryImpact: '无阻塞',
      reason: '保留追溯，不作为最终质检结论',
      tone: 'success'
    },
    {
      id: 'q-006',
      time: '昨天 23:10',
      source: '包装区',
      sourceType: 'import',
      type: '物流异常',
      detail: '包装破损率上升，已记录复核线索',
      severity: '低',
      status: '已关闭',
      impactScope: '包装区',
      owner: '包装主管',
      deliveryImpact: '无阻塞',
      reason: '历史闭环样例，fallback 状态下需现场复核',
      tone: 'closed'
    },
    {
      id: 'q-007',
      time: '昨天 21:45',
      source: '公辅系统',
      sourceType: 'system',
      type: '能耗异常',
      detail: '压缩空气压力波动，已沉淀为追溯线索',
      severity: '低',
      status: '已关闭',
      impactScope: '公辅系统',
      owner: '公辅值班',
      deliveryImpact: '无阻塞',
      reason: '不作为 AI 自动关闭依据',
      tone: 'closed'
    }
  ],
  workflow: [
    { title: '发现 / 分诊', count: 3, status: '处理中', tone: 'processing', body: '系统校验与审阅任务聚合告警，人工确认来源与责任范围。', nextAction: '进入审阅任务' },
    { title: '建议方案', count: 2, status: '待确认', tone: 'warning', body: '辅助建议只用于排序与提示，不能替代质量处置结论。', nextAction: '查看告警详情' },
    { title: '执行跟踪', count: 3, status: '跟踪中', tone: 'processing', body: '跟踪现场复核、退回补齐与处置记录，不写入生产事实。', nextAction: '看工厂看板' },
    { title: '关闭沉淀', count: 4, status: '已关闭', tone: 'success', body: '关闭前需人工验证问题解决，沉淀追溯线索与日报影响。', nextAction: '查看历史' }
  ],
  aiTriage: [
    { label: '辅助建议', value: '优先核对质检系统不合格品率与模具一线毛刺偏高两项高风险。', tone: 'warning' },
    { label: '高风险来源', value: '质检系统、模具一线；均需人工确认后才能关闭。', tone: 'danger' },
    { label: '日报影响', value: '质量异常日报被 2 项未关闭告警阻塞，建议先进入审阅任务核对凭证。', tone: 'warning' },
    { label: '数据口径', value: '当前为 fallback 读面，不能视作最终质检结论。', tone: 'info' }
  ],
  blockers: [
    { label: '未关闭高风险', value: '2 项', status: '阻塞', tone: 'danger', routeName: 'review-task-center' },
    { label: '待审相关告警', value: '3 项', status: '待审', tone: 'warning', routeName: 'review-task-center' },
    { label: '影响日报交付', value: '2 项', status: '交付风险', tone: 'danger', routeName: 'review-report-center' },
    { label: '数据源 fallback / mixed', value: '当前 fallback', status: '需复核', tone: 'warning', routeName: 'factory-dashboard' },
    { label: '最近失败原因', value: '异常未关闭 2 项，质量异常日报未执行真实发送', status: '失败', tone: 'danger', routeName: 'review-report-center' }
  ],
  actions: {
    viewDetail: 'disabled',
    markProcessing: 'disabled',
    close: 'disabled',
    export: 'disabled',
    reviewTasks: 'enabled',
    reportImpact: 'enabled'
  },
  caliber:
    '本页用于查看质量告警、异常处置与日报交付影响。告警状态来自已接入数据源与系统校验结果，当前页面不承接生产事实写入。若数据源标记为 fallback/mixed，请以现场试跑口径复核。'
}

export const costCenterMock = {
  source: 'fallback',
  updatedAt: '2026-04-25 10:30',
  businessDate: '2026-04-25',
  scope: '经营估算 / 策略口径',
  activeWorkshop: 'zr2',
  activeBasis: 'output',
  workshops: [
    { key: 'zr2', label: '铸二', source: 'fallback', risk: '偏高' },
    { key: 'zr3', label: '铸三', source: 'fallback', risk: '正常' },
    { key: 'finishing', label: '精整', source: 'fallback', risk: '待核' },
    { key: 'hotRolling', label: '热轧', source: 'fallback', risk: '偏高' },
    { key: 'leveling', label: '拉矫', source: 'fallback', risk: '正常' },
    { key: 'line2050', label: '2050', source: 'fallback', risk: '待核' },
    { key: 'line1650', label: '1650', source: 'fallback', risk: '正常' },
    { key: 'line1850', label: '1850', source: 'fallback', risk: '正常' },
    { key: 'pattern', label: '花纹板', source: 'fallback', risk: '待接入' }
  ],
  basisOptions: [
    { key: 'output', label: '产量口径' },
    { key: 'throughput', label: '通货口径' }
  ],
  kpis: [
    { label: '吨铝成本', value: '8,560', unit: '元/吨', trend: '经营估算', tone: 'info' },
    { label: '人工', value: '1,245', unit: '元/吨', trend: '班组口径', tone: 'neutral' },
    { label: '电耗', value: '632', unit: '元/吨', trend: '折算 2,960 kWh', tone: 'warning' },
    { label: '天然气', value: '324', unit: '元/吨', trend: '折算 126 m³', tone: 'neutral' },
    { label: '辅材 / 损耗', value: '156', unit: '元/吨', trend: '策略价', tone: 'neutral' },
    { label: '成本偏差 / 风险项', value: '3', unit: '项', trend: '待人工复核', tone: 'warning' }
  ],
  composition: [
    { key: 'material', label: '原料', value: 5120, ratio: 59.8, color: '#1167f2', source: 'import' },
    { key: 'power', label: '电耗', value: 1260, ratio: 14.7, color: '#22a66f', source: 'owner' },
    { key: 'gas', label: '天然气', value: 820, ratio: 9.6, color: '#24aac0', source: 'owner' },
    { key: 'labor', label: '人工', value: 1245, ratio: 14.5, color: '#9061e8', source: 'system' },
    { key: 'loss', label: '辅材 / 损耗', value: 156, ratio: 1.8, color: '#ffab2d', source: 'fallback' },
    { key: 'other', label: '折旧 / 其他', value: 159, ratio: 1.9, color: '#b8c0cc', source: 'fallback' }
  ],
  trend: [
    { day: '05-15', parts: { material: 3820, power: 1090, gas: 860, labor: 1040, loss: 820, other: 880 }, outputTon: 230, throughputTon: 246, risk: '正常' },
    { day: '05-16', parts: { material: 3900, power: 1080, gas: 900, labor: 1030, loss: 780, other: 850 }, outputTon: 228, throughputTon: 244, risk: '正常' },
    { day: '05-17', parts: { material: 3660, power: 1020, gas: 870, labor: 990, loss: 720, other: 805 }, outputTon: 219, throughputTon: 235, risk: '待核' },
    { day: '05-18', parts: { material: 3520, power: 970, gas: 840, labor: 910, loss: 690, other: 770 }, outputTon: 212, throughputTon: 230, risk: '正常' },
    { day: '05-19', parts: { material: 3580, power: 1010, gas: 860, labor: 930, loss: 730, other: 790 }, outputTon: 216, throughputTon: 232, risk: '正常' },
    { day: '05-20', parts: { material: 3630, power: 1060, gas: 890, labor: 950, loss: 760, other: 820 }, outputTon: 221, throughputTon: 238, risk: '偏高' },
    { day: '05-21', parts: { material: 3700, power: 1090, gas: 900, labor: 970, loss: 790, other: 840 }, outputTon: 224, throughputTon: 241, risk: '偏高' }
  ],
  cumulative: {
    amount: '8,760',
    unit: '元/吨',
    monthEstimate: '183.6 万',
    monthOutput: '2,145 吨',
    monthThroughput: '2,312 吨'
  },
  detailRows: [
    { id: 'material', item: '原料', amount: '5,120', unit: '元/吨', price: '策略折算价', tonCost: '5,120', monthly: '109.8 万', status: 'fallback', tone: 'warning', source: 'import', basisText: '按当日投料与策略价估算，待价格主数据接入。' },
    { id: 'power', item: '电耗', amount: '2,960 kWh', unit: 'kWh', price: '0.426 元/kWh', tonCost: '632', monthly: '13.6 万', status: '偏高', tone: 'warning', source: 'owner', basisText: '能耗专项补录折算，05-20 后段略高。' },
    { id: 'gas', item: '天然气', amount: '126 m³', unit: 'm³', price: '2.57 元/m³', tonCost: '324', monthly: '7.0 万', status: '正常', tone: 'success', source: 'owner', basisText: '按班次能耗与通货量交叉查看。' },
    { id: 'labor', item: '人工', amount: '24 人班', unit: '人班', price: '51.9 元/人班', tonCost: '1,245', monthly: '26.7 万', status: '待核', tone: 'info', source: 'system', basisText: '按班组配置估算，非工资结算口径。' },
    { id: 'loss', item: '辅材 / 损耗', amount: '156', unit: '元/吨', price: '策略价', tonCost: '156', monthly: '3.3 万', status: 'fallback', tone: 'warning', source: 'system', basisText: '辅材与损耗合并估算，需现场试跑复核。' },
    { id: 'other', item: '折旧 / 其他', amount: '159', unit: '元/吨', price: '策略摊销', tonCost: '159', monthly: '3.4 万', status: '待接入', tone: 'neutral', source: 'system', basisText: '仅作经营观察，不代表入账摊销。' }
  ],
  risks: [
    { label: '成本偏高项', value: '电耗、原料策略价', status: '待复核', tone: 'warning', routeName: 'factory-dashboard' },
    { label: '单价待核', value: '原料 / 辅材使用 fallback', status: 'fallback', tone: 'warning', routeName: 'admin-ingestion-center' },
    { label: '能耗异常', value: '05-20 起电耗折算偏高', status: '观察', tone: 'info', routeName: 'review-quality-center' },
    { label: '数据源 fallback / mixed', value: '成本读面 fallback', status: '需复核', tone: 'warning', routeName: 'admin-ingestion-center' },
    { label: '日报解释风险', value: '经营解释需标注策略口径', status: '影响日报', tone: 'danger', routeName: 'review-report-center' }
  ],
  actions: {
    adjustPlan: 'disabled',
    viewBasis: 'enabled',
    export: 'disabled',
    reportImpact: 'enabled',
    qualityRisk: 'enabled',
    factoryBoard: 'enabled',
    ingestion: 'permission'
  },
  caliber:
    '本页为经营估算 / 策略口径，用于查看成本构成、能耗、人工、辅材与损耗趋势，不作为会计结算或月度入账依据。若数据源标记为 fallback/mixed，请以现场试跑口径复核。'
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
