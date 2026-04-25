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
  source: 'fallback',
  updatedAt: '2026-04-25 10:30',
  businessDate: '2026-04-25',
  environment: '管理端 / 配置治理面',
  kpis: [
    { label: '数据源数量', value: 6, unit: '个', trend: '含手工录入', tone: 'info' },
    { label: '已接入', value: 0, unit: '个', trend: '无正式 live', tone: 'neutral' },
    { label: 'fallback / 待接入', value: '4 / 2', unit: '项', trend: '需治理', tone: 'warning' },
    { label: '今日导入批次', value: 5, unit: '批', trend: '试跑样例', tone: 'processing' },
    { label: '成功率', value: '88.54', unit: '%', trend: 'fallback 口径', tone: 'warning' },
    { label: '失败记录', value: '4,321', unit: '条', trend: '待人工确认', tone: 'danger' }
  ],
  dataSources: [
    {
      id: 'mes',
      name: 'MES',
      type: '生产订单 / 卷级数据',
      source: 'mixed',
      status: 'mixed',
      statusLabel: '试跑映射',
      tone: 'warning',
      lastSync: '10:15',
      successRate: '88.54%',
      failed: 544,
      owner: '数据治理',
      note: '仅展示映射样例，未标记正式联通'
    },
    {
      id: 'plc',
      name: 'PLC',
      type: '设备采集',
      source: 'fallback',
      status: 'fallback',
      statusLabel: 'fallback',
      tone: 'warning',
      lastSync: '09:30',
      successRate: '99.77%',
      failed: 20,
      owner: '设备工程',
      note: '时间戳格式需治理'
    },
    {
      id: 'quality',
      name: '质检系统',
      type: '质量记录',
      source: 'fallback',
      status: 'fallback',
      statusLabel: 'fallback',
      tone: 'warning',
      lastSync: '08:50',
      successRate: '99.68%',
      failed: 20,
      owner: '质量负责人',
      note: '缺陷原因字段待统一'
    },
    {
      id: 'energy',
      name: '能耗系统',
      type: '电耗 / 气耗',
      source: 'mixed',
      status: 'mixed',
      statusLabel: 'mixed',
      tone: 'info',
      lastSync: '07:50',
      successRate: '100.00%',
      failed: 0,
      owner: '能源管理员',
      note: '成本读面仍按策略口径复核'
    },
    {
      id: 'erp',
      name: 'ERP',
      type: '经营主数据',
      source: 'fallback',
      status: '待接入',
      statusLabel: '待接入',
      tone: 'neutral',
      lastSync: '待接入',
      successRate: '-',
      failed: '-',
      owner: '财务 / IT',
      note: '仅保留字段治理占位，不表示同步'
    },
    {
      id: 'manual',
      name: '手工录入',
      type: '现场一手录入',
      source: 'manual',
      status: 'mixed',
      statusLabel: '部分字段',
      tone: 'warning',
      lastSync: '08:20',
      successRate: '98.02%',
      failed: 22,
      owner: '总统计',
      note: '字段口径待人工确认'
    }
  ],
  fieldMappings: [
    { id: 'business-date', name: 'business_date', type: 'Date', source: 'MES / 手工录入', sourceKey: 'mixed', sourceField: 'biz_date', mapping: '字段转换', check: '待核', tone: 'warning', caliber: '业务日期按日报口径统一，不回写现场事实', updatedAt: '10:15' },
    { id: 'shift-id', name: 'shift_id', type: 'String', source: 'MES / PLC', sourceKey: 'mixed', sourceField: 'shift_code', mapping: '字典映射', check: '通过', tone: 'success', caliber: '班次字典与审阅任务保持一致', updatedAt: '10:12' },
    { id: 'workshop-code', name: 'workshop_code', type: 'String', source: '手工录入', sourceKey: 'manual', sourceField: 'workshop_name', mapping: '字典映射', check: '待核', tone: 'warning', caliber: '车间名称需映射到标准编码', updatedAt: '09:58' },
    { id: 'line-code', name: 'line_code', type: 'String', source: 'PLC', sourceKey: 'fallback', sourceField: 'line_no', mapping: '字段转换', check: 'fallback', tone: 'warning', caliber: '产线编码仍按试跑映射复核', updatedAt: '09:30' },
    { id: 'output-ton', name: 'output_ton', type: 'Decimal', source: 'MES', sourceKey: 'mixed', sourceField: 'actual_weight', mapping: '单位转换', check: '冲突', tone: 'danger', caliber: 'kg -> t 转换需与日报产量口径核对', updatedAt: '10:15' },
    { id: 'finished-rate', name: 'finished_rate', type: 'Percent', source: '质检系统', sourceKey: 'fallback', sourceField: 'finished_rate', mapping: '直接映射', check: '待核', tone: 'warning', caliber: '成品率字段待确认统计口径', updatedAt: '08:50' },
    { id: 'defect-reason', name: 'defect_reason', type: 'String', source: '质检系统', sourceKey: 'fallback', sourceField: 'defect_code', mapping: '字典映射', check: '缺失', tone: 'danger', caliber: '缺陷原因字典未完全覆盖', updatedAt: '08:50' },
    { id: 'energy-kwh', name: 'energy_kwh', type: 'Decimal', source: '能耗系统', sourceKey: 'mixed', sourceField: 'power_kwh', mapping: '直接映射', check: '通过', tone: 'success', caliber: '仅用于读面核对与成本估算', updatedAt: '07:50' },
    { id: 'gas-m3', name: 'gas_m3', type: 'Decimal', source: '能耗系统', sourceKey: 'mixed', sourceField: 'gas_flow', mapping: '字段转换', check: '通过', tone: 'success', caliber: 'm³ 口径按班次汇总', updatedAt: '07:50' },
    { id: 'material-loss', name: 'material_loss', type: 'Decimal', source: 'ERP / 手工录入', sourceKey: 'fallback', sourceField: 'loss_amount', mapping: '人工确认', check: '待配置', tone: 'neutral', caliber: '辅材损耗暂不代表入账结果', updatedAt: '待接入' }
  ],
  importOverview: {
    totalRows: '96,327',
    acceptedRows: '84,542',
    successRate: '88.54%',
    failedRows: '4,321',
    pendingRows: '12',
    segments: [
      { key: 'accepted', label: '校验通过', value: 84.54, color: '#1167f2' },
      { key: 'failed', label: '失败', value: 4.5, color: '#ef4444' },
      { key: 'pending', label: '待处理', value: 0.01, color: '#f59e0b' },
      { key: 'other', label: '其他 / 未统计', value: 7.77, color: '#18a36a' }
    ]
  },
  importHistory: [
    { id: 'h-001', time: '05-21 10:15', source: 'MES', sourceKey: 'mixed', task: 'mes_20240521_1015.csv', total: '12,845', success: '12,301', failed: '544', status: '校验完成', tone: 'warning', reason: '544 行产品编码缺失，未写入生产事实' },
    { id: 'h-002', time: '05-21 09:30', source: 'PLC', sourceKey: 'fallback', task: 'plc_20240521_0930.csv', total: '8,542', success: '8,522', failed: '20', status: '部分失败', tone: 'warning', reason: '20 行时间戳格式异常' },
    { id: 'h-003', time: '05-21 08:50', source: '质检系统', sourceKey: 'fallback', task: 'qc_20240521_0850.xlsx', total: '6,321', success: '6,301', failed: '20', status: '部分失败', tone: 'warning', reason: '20 行缺少批次号' },
    { id: 'h-004', time: '05-21 08:20', source: '手工录入', sourceKey: 'manual', task: 'manual_input_20240521.xlsx', total: '1,111', success: '1,089', failed: '22', status: '待人工确认', tone: 'info', reason: '22 行字段口径待确认' },
    { id: 'h-005', time: '05-21 07:50', source: '能耗系统', sourceKey: 'mixed', task: 'energy_20240521_0750.csv', total: '5,210', success: '5,210', failed: '0', status: '校验完成', tone: 'success', reason: '能耗读面仍需与成本策略复核' }
  ],
  errors: [
    { label: '最近失败原因', value: '产品编码缺失、时间戳格式异常、批次号缺失', status: '待处理', tone: 'warning', routeName: 'review-task-center' },
    { label: '字段缺失', value: 'defect_reason / material_loss 覆盖不足', status: '缺失', tone: 'danger', routeName: 'admin-governance-center' },
    { label: '口径冲突', value: 'output_ton kg -> t 转换需与日报口径核对', status: '冲突', tone: 'danger', routeName: 'review-report-center' },
    { label: '数据源异常', value: 'PLC 时间戳与班次归属需治理', status: '异常', tone: 'warning', routeName: 'admin-ops-reliability' },
    { label: '待人工确认', value: '手工录入字段映射 22 行待复核', status: '待确认', tone: 'info', routeName: 'review-task-center' }
  ],
  actions: {
    upload: 'disabled',
    configureMapping: 'disabled',
    viewErrors: 'enabled',
    retry: 'disabled',
    exportErrors: 'disabled',
    viewCaliber: 'enabled'
  },
  caliber:
    '本页用于管理数据源接入、字段映射、导入批次与错误说明，属于管理端配置治理面，不承接现场生产事实写入。若数据源标记为 fallback/mixed，请以现场试跑口径复核。',
  sources: [
    { name: 'MES', source: 'mes', status: '试跑映射', tone: 'warning' },
    { name: 'PLC', source: 'system', status: 'fallback', tone: 'warning' },
    { name: '质检系统', source: 'system', status: 'fallback', tone: 'warning' },
    { name: '能耗系统', source: 'system', status: 'mixed', tone: 'info' },
    { name: 'ERP', source: 'import', status: '待接入', tone: 'neutral' },
    { name: '手工录入', source: 'operator', status: '部分字段', tone: 'warning' }
  ],
  fields: [
    { name: 'business_date', type: 'Date', sourceField: 'biz_date', mapping: '字段转换', check: '待核' },
    { name: 'shift_id', type: 'String', sourceField: 'shift_code', mapping: '字典映射', check: '通过' },
    { name: 'workshop_code', type: 'String', sourceField: 'workshop_name', mapping: '字典映射', check: '待核' },
    { name: 'line_code', type: 'String', sourceField: 'line_no', mapping: '字段转换', check: 'fallback' },
    { name: 'output_ton', type: 'Decimal', sourceField: 'actual_weight', mapping: '单位转换', check: '冲突' },
    { name: 'finished_rate', type: 'Percent', sourceField: 'finished_rate', mapping: '直接映射', check: '待核' },
    { name: 'defect_reason', type: 'String', sourceField: 'defect_code', mapping: '字典映射', check: '缺失' }
  ],
  overview: [
    { label: '总数据量', value: '96,327', unit: '条', tone: 'info' },
    { label: '校验通过', value: '84,542', unit: '条', tone: 'success' },
    { label: '成功率', value: '88.54', unit: '%', tone: 'success' },
    { label: '失败记录', value: '4,321', unit: '条', tone: 'danger' },
    { label: '待处理', value: '12', unit: '条', tone: 'warning' }
  ],
  history: [
    { id: 'h-001', time: '05-21 10:15', source: 'MES', task: 'mes_20240521_1015.csv', total: '12,845', success: '12,301', failed: '544', status: '校验完成', reason: '544 行产品编码缺失' },
    { id: 'h-002', time: '05-21 09:30', source: 'PLC', task: 'plc_20240521_0930.csv', total: '8,542', success: '8,522', failed: '20', status: '部分失败', reason: '20 行时间戳格式异常' },
    { id: 'h-003', time: '05-21 08:50', source: '质检系统', task: 'qc_20240521_0850.xlsx', total: '6,321', success: '6,301', failed: '20', status: '部分失败', reason: '20 行缺少批次号' },
    { id: 'h-004', time: '05-21 08:20', source: '手工录入', task: 'manual_input_20240521.xlsx', total: '1,111', success: '1,089', failed: '22', status: '待人工确认', reason: '22 行字段口径待确认' },
    { id: 'h-005', time: '05-21 07:50', source: '能耗系统', task: 'energy_20240521_0750.csv', total: '5,210', success: '5,210', failed: '0', status: '校验完成', reason: '能耗读面仍需与成本策略复核' }
  ]
}

export const brainCenterMock = {
  source: 'fallback',
  businessDate: '2026-04-25',
  updatedAt: '2026-04-25 10:30',
  scope: '辅助建议 / 证据驱动',
  kpis: [
    { label: '今日摘要', value: '可交付', unit: '', trend: '辅助建议：先复核 3 项风险', tone: 'info' },
    { label: '高风险事件', value: 2, unit: '项', trend: '质量 / 日报阻塞', tone: 'danger' },
    { label: '待审重点', value: 18, unit: '单', trend: '审阅端待确认', tone: 'warning' },
    { label: '日报阻塞', value: 1, unit: '项', trend: '未执行真实交付', tone: 'danger' },
    { label: '质量关注', value: 2, unit: '项', trend: '需人工关闭前复核', tone: 'warning' },
    { label: 'fallback / mixed', value: '3 / 2', unit: '源', trend: '系统提示：按试跑口径复核', tone: 'warning' }
  ],
  summary: {
    title: '今日辅助摘要',
    headline: '系统提示：今日产量与交付总体可继续推进，但质量异常、日报阻塞与数据接入口径仍需审阅端人工复核。',
    points: [
      '今日产量保持在 5,824 吨读面水平，订单达成率按 fallback 口径为 96.7%。',
      '质量异常日报受 2 项未关闭高风险告警影响，日报交付存在 1 项阻塞。',
      '成本侧电耗与原料策略价偏高，当前只作为经营估算解释，不作为会计结算。',
      'MES / 能耗为 mixed 试跑状态，质检与 ERP 仍含 fallback，建议复核字段口径。'
    ],
    confidence: 'mixed / fallback',
    nextStep: '辅助建议：先查看质量告警与日报阻塞，再回到数据接入中心确认 source 标识。'
  },
  risks: [
    {
      id: 'risk-quality-report',
      name: '质量异常日报阻塞',
      sourceCenter: '质量告警',
      sourceKey: 'quality',
      level: '高风险',
      tone: 'danger',
      impact: '质量异常日报 / 管理层交付',
      evidence: '2 项高风险未关闭，质量异常日报未执行真实发送',
      recommendation: '辅助建议：进入质量与告警中心复核凭证与责任范围',
      status: '待人工复核',
      statusTone: 'warning',
      routeName: 'review-quality-center',
      routeLabel: '查看质量告警'
    },
    {
      id: 'risk-delivery-blocked',
      name: '日报交付链路阻塞',
      sourceCenter: '日报交付',
      sourceKey: 'system',
      level: '高风险',
      tone: 'danger',
      impact: '厂级生产日报 / 接收对象',
      evidence: '交付失败 1 项，接收对象待确认',
      recommendation: '辅助建议：查看日报阻塞项并确认接收对象',
      status: '阻塞',
      statusTone: 'danger',
      routeName: 'review-report-center',
      routeLabel: '看日报阻塞'
    },
    {
      id: 'risk-cost-energy',
      name: '电耗与策略价偏高',
      sourceCenter: '成本效益',
      sourceKey: 'energy',
      level: '中风险',
      tone: 'warning',
      impact: '经营估算 / 成本解释',
      evidence: '05-20 起电耗折算偏高，原料策略价仍为 fallback',
      recommendation: '系统提示：按经营估算口径查看成本解释，不形成结算结果',
      status: '观察',
      statusTone: 'info',
      routeName: 'review-cost-accounting',
      routeLabel: '看成本解释'
    },
    {
      id: 'risk-ingestion-source',
      name: '数据源 fallback / mixed',
      sourceCenter: '数据接入',
      sourceKey: 'mixed',
      level: '中风险',
      tone: 'warning',
      impact: '日报口径 / 成本估算 / 质量告警',
      evidence: 'MES 与能耗为 mixed，质检与 ERP 仍含 fallback / 待接入',
      recommendation: '辅助建议：查看字段映射与 source 状态，不标记正式联通',
      status: '需治理',
      statusTone: 'warning',
      routeName: 'admin-ingestion-center',
      routeLabel: '看数据接入'
    },
    {
      id: 'risk-factory-output',
      name: '产线异常与待审累积',
      sourceCenter: '工厂看板',
      sourceKey: 'exception',
      level: '中风险',
      tone: 'warning',
      impact: '熔铸区 / 热轧区 / 审阅任务',
      evidence: '熔铸区成品率偏低，18 单待审核',
      recommendation: '辅助建议：先看工厂看板，再进入审阅任务确认异常原因',
      status: '待审',
      statusTone: 'processing',
      routeName: 'factory-dashboard',
      routeLabel: '看工厂看板'
    }
  ],
  topics: [
    {
      id: 'production',
      title: '生产摘要',
      status: '可继续推进',
      tone: 'success',
      evidence: '今日产量 5,824 吨，异常 4 项，待审 18 单',
      advice: '辅助建议：优先确认熔铸区与热轧区异常是否影响日报口径。',
      source: 'factory board',
      sourceKey: 'system',
      routeName: 'factory-dashboard',
      routeLabel: '看工厂看板'
    },
    {
      id: 'reports',
      title: '日报交付',
      status: '存在阻塞',
      tone: 'danger',
      evidence: '质量异常日报交付失败 1 项，接收对象待确认',
      advice: '系统提示：查看阻塞项，不自动发送或重新生成日报。',
      source: 'reports delivery',
      sourceKey: 'system',
      routeName: 'review-report-center',
      routeLabel: '看日报阻塞'
    },
    {
      id: 'quality',
      title: '质量关注',
      status: '需人工关闭前复核',
      tone: 'warning',
      evidence: '不合格品率与毛刺偏高两项高风险未关闭',
      advice: '辅助建议：核对凭证、批次和责任范围后再做人工处置。',
      source: 'quality alerts',
      sourceKey: 'quality',
      routeName: 'review-quality-center',
      routeLabel: '看质量告警'
    },
    {
      id: 'cost',
      title: '成本解释',
      status: '经营估算',
      tone: 'info',
      evidence: '电耗折算偏高，原料 / 辅材策略价仍需现场复核',
      advice: '辅助建议：只用于经营解释，不作为会计结算或月结依据。',
      source: 'cost benefit',
      sourceKey: 'energy',
      routeName: 'review-cost-accounting',
      routeLabel: '看成本解释'
    },
    {
      id: 'ingestion',
      title: '数据接入问题',
      status: 'fallback / mixed',
      tone: 'warning',
      evidence: 'output_ton 转换、defect_reason 字典、material_loss 字段仍待治理',
      advice: '系统提示：查看字段映射，不表示 MES / ERP 已正式联通。',
      source: 'ingestion mapping',
      sourceKey: 'mixed',
      routeName: 'admin-ingestion-center',
      routeLabel: '看数据接入'
    },
    {
      id: 'ops',
      title: '系统运行风险',
      status: '只读观察',
      tone: 'info',
      evidence: 'readiness / health 只作为页面提示，未接自动经营指挥',
      advice: '辅助建议：如需运维证据，进入系统运维中心查看健康状态。',
      source: 'readiness / health',
      sourceKey: 'system',
      routeName: 'admin-ops-reliability',
      routeLabel: '看运维状态'
    }
  ],
  evidence: [
    { id: 'factory', name: 'factory board', caliber: '厂级生产看板读面', updatedAt: '2026-04-25 10:30', sourceType: 'fallback', tone: 'warning', note: '用于产量、异常、待审数量解释' },
    { id: 'reports', name: 'reports delivery', caliber: 'auto_confirmed / 已自动确认数据口径', updatedAt: '2026-04-25 10:30', sourceType: 'fallback', tone: 'warning', note: '用于日报生成、阻塞和交付状态查看' },
    { id: 'quality', name: 'quality alerts', caliber: '质量告警与日报影响读面', updatedAt: '2026-04-25 10:30', sourceType: 'fallback', tone: 'warning', note: '用于质量风险解释，不自动关闭告警' },
    { id: 'cost', name: 'cost benefit', caliber: '经营估算 / 策略口径', updatedAt: '2026-04-25 10:30', sourceType: 'fallback', tone: 'warning', note: '用于成本解释，不作为会计结算' },
    { id: 'ingestion', name: 'ingestion mapping', caliber: '字段映射与导入试跑', updatedAt: '2026-04-25 10:15', sourceType: 'mixed', tone: 'info', note: '用于 source / fallback / mixed 风险说明' },
    { id: 'health', name: 'readiness / health', caliber: '前端只读健康提示', updatedAt: '2026-04-25 10:20', sourceType: 'mixed', tone: 'info', note: '不表示 live LLM 或自动决策已启用' }
  ],
  actions: [
    { key: 'generateSummary', label: '生成今日摘要', status: 'disabled', tone: 'neutral', title: '生成接口未接入，当前使用 fallback 辅助摘要' },
    { key: 'evidence', label: '查看证据', status: 'enabled', tone: 'info', routeName: '', title: '查看本页证据链与数据来源' },
    { key: 'reviewTasks', label: '去审阅任务', status: 'enabled', tone: 'processing', routeName: 'review-task-center', title: '进入审阅任务' },
    { key: 'reportBlockers', label: '看日报阻塞', status: 'enabled', tone: 'danger', routeName: 'review-report-center', title: '查看日报交付阻塞' },
    { key: 'qualityAlerts', label: '看质量告警', status: 'enabled', tone: 'warning', routeName: 'review-quality-center', title: '查看质量告警' },
    { key: 'costExplain', label: '看成本解释', status: 'enabled', tone: 'info', routeName: 'review-cost-accounting', title: '查看成本解释' },
    { key: 'ingestionIssues', label: '看数据接入问题', status: 'permission', tone: 'warning', routeName: 'admin-ingestion-center', title: '需要管理端权限' },
    { key: 'copySummary', label: '复制摘要', status: 'enabled', tone: 'success', routeName: '', title: '复制本页辅助摘要，不写入业务数据' }
  ],
  questions: [
    '有异常吗？',
    '外机比我多了啥？',
    '今日异常汇总？'
  ],
  ask: {
    status: 'disabled',
    placeholder: '追问接口未启用',
    notice: '当前没有真实 LLM 追问接口，本区仅展示 fallback 问法入口，不保存对话。'
  },
  caliber:
    '本页用于汇总生产、日报、质量、成本和数据接入的辅助解释与建议。AI 输出仅作为审阅辅助，不自动执行生产、质量、成本、排产或交付动作。若数据源标记为 fallback/mixed，请以现场试跑口径复核。'
}

export const opsCenterMock = {
  source: 'fallback',
  environment: 'trial / 管理端运维观测面',
  updatedAt: '2026-04-25 10:42',
  version: {
    current: 'v2.3.1',
    buildId: 'frontend-fallback-20260425',
    frontend: '0.2.0',
    backend: '0.4.0',
    buildTime: '2026-04-25 09:40',
    deployTime: '待复核',
    commit: 'fallback-snapshot',
    schema: '待人工复核',
    environment: 'trial'
  },
  kpis: [
    { label: 'healthz', value: '待复核', unit: '', trend: 'fallback：未声明真实健康通过', tone: 'warning' },
    { label: 'readyz', value: '阻塞', unit: '', trend: 'hard gate 未通过', tone: 'danger' },
    { label: 'hard gate', value: 'false', unit: '', trend: '上线闸门需人工复核', tone: 'danger' },
    { label: '服务数', value: 8, unit: '项', trend: '2 disabled / 3 warning', tone: 'warning' },
    { label: '错误率', value: '0.12', unit: '%', trend: '最近 24h fallback 趋势', tone: 'warning' },
    { label: '平均响应时间', value: 218, unit: 'ms', trend: 'healthz + readyz 探测口径', tone: 'info' }
  ],
  readiness: {
    status: 'blocked',
    statusLabel: 'readiness blocked',
    hardGatePassed: false,
    hardGateLabel: 'hard_gate_passed=false',
    lastCheckTime: '2026-04-25 10:42',
    source: 'fallback',
    blockingReasons: [
      'readyz 结果未接入当前页面真实读取，不能声明通过',
      '数据库 schema 状态为待复核',
      'AI probe 当前为 disabled / fallback，不参与上线通过判定'
    ],
    warnings: [
      '消息推送为 disabled，仅保留只读观察入口',
      'report pipeline 受质量日报阻塞影响，需结合 /review/reports 复核',
      'fallback 数据只用于页面收口，不替代服务器运维命令'
    ]
  },
  services: [
    { id: 'frontend', name: 'frontend', statusLabel: 'fallback', tone: 'warning', latency: '24ms', lastCheck: '10:42', source: 'fallback', note: '前端运行态来自页面兜底快照，需用浏览器与构建结果复核', actionLabel: '刷新探针', actionStatus: 'enabled', panel: 'probe' },
    { id: 'backend', name: 'backend', statusLabel: 'warning', tone: 'warning', latency: '218ms', lastCheck: '10:42', source: 'fallback', note: '后端健康需以 /healthz 与 /readyz 实测为准', actionLabel: '查看健康检查', actionStatus: 'enabled', panel: 'health' },
    { id: 'database', name: 'database', statusLabel: 'warning', tone: 'warning', latency: '12ms', lastCheck: '10:41', source: 'fallback', note: 'schema 状态未由真实版本 API 返回，不能声明最新', actionLabel: '只读', actionStatus: 'disabled' },
    { id: 'gateway', name: 'gateway / nginx', statusLabel: 'fallback', tone: 'warning', latency: '98ms', lastCheck: '10:41', source: 'fallback', note: '网关状态未接入真实代理探针', actionLabel: '只读', actionStatus: 'disabled' },
    { id: 'scheduler', name: 'scheduler / jobs', statusLabel: 'degraded', tone: 'warning', latency: '210ms', lastCheck: '10:40', source: 'mixed', note: '定时任务只展示观测状态，不重启任务', actionLabel: '查看上线闸门', actionStatus: 'enabled', panel: 'gate' },
    { id: 'message', name: 'message / push', statusLabel: 'disabled', tone: 'neutral', latency: '-', lastCheck: '10:40', source: 'fallback', note: '消息推送未启用，不伪造送达成功', actionLabel: '只读', actionStatus: 'disabled' },
    { id: 'ai-probe', name: 'AI probe', statusLabel: 'disabled', tone: 'neutral', latency: '-', lastCheck: '10:39', source: 'fallback', note: 'LLM probe 未启用，不显示 live 成功', actionLabel: '看 AI 总控', actionStatus: 'enabled', routeName: 'review-brain-center' },
    { id: 'report-pipeline', name: 'report pipeline', statusLabel: 'blocked', tone: 'danger', latency: '156ms', lastCheck: '10:39', source: 'mixed', note: '日报交付链路存在阻塞，需进入日报中心复核', actionLabel: '看日报', actionStatus: 'enabled', routeName: 'review-report-center' }
  ],
  trends: {
    errorRate: [
      { label: '00:00', value: 0.04 },
      { label: '04:00', value: 0.07 },
      { label: '08:00', value: 0.12 },
      { label: '12:00', value: 0.09 },
      { label: '16:00', value: 0.11 },
      { label: '20:00', value: 0.08 }
    ],
    latency: [
      { label: '00:00', value: 168 },
      { label: '04:00', value: 192 },
      { label: '08:00', value: 218 },
      { label: '12:00', value: 205 },
      { label: '16:00', value: 230 },
      { label: '20:00', value: 176 }
    ]
  },
  timeline: [
    { time: '10:00', title: '版本快照待复核', detail: 'v2.3.1 仅来自 fallback 版本信息', tone: 'info' },
    { time: '10:12', title: '配置检查完成', detail: '不代表真实重启或部署完成', tone: 'warning' },
    { time: '10:15', title: '告警解除待核', detail: 'warning issues 仍需人工确认', tone: 'warning' },
    { time: '10:18', title: '上线闸门阻塞', detail: 'hard_gate_passed=false', tone: 'danger' }
  ],
  actions: [
    { key: 'refreshProbe', label: '刷新探针', status: 'enabled', tone: 'info', panel: 'probe', title: '仅刷新本页查询状态，不重启服务' },
    { key: 'readiness', label: '查看 readiness', status: 'enabled', tone: 'warning', panel: 'readiness', title: '查看 readyz / hard gate 只读说明' },
    { key: 'health', label: '查看健康检查', status: 'enabled', tone: 'info', panel: 'health', title: '查看 healthz 只读说明' },
    { key: 'goLiveGate', label: '查看上线闸门', status: 'enabled', tone: 'danger', panel: 'gate', title: '查看 go-live gate 阻塞原因' },
    { key: 'rollbackCheck', label: '查看回滚预检', status: 'disabled', tone: 'neutral', title: '无回滚预检接口，当前不伪造通过' },
    { key: 'exportDiagnostics', label: '导出诊断', status: 'disabled', tone: 'neutral', title: '导出接口未接入，当前不伪造导出成功' },
    { key: 'logs', label: '查看日志', status: 'disabled', tone: 'neutral', title: '日志入口未接入，当前不打开服务器日志' }
  ],
  risks: [
    { label: '最近失败', value: '日报交付链路阻塞 1 项', status: '阻塞', tone: 'danger', routeName: 'review-report-center' },
    { label: '阻塞原因', value: 'readyz / hard gate 未由 live 数据确认', status: '待复核', tone: 'warning', routeName: '' },
    { label: 'warning issues', value: 'schema、消息推送、AI probe 需人工检查', status: 'warning', tone: 'warning', routeName: 'admin-governance-center' },
    { label: '错误摘要', value: '0.12% fallback 错误率，不替代真实日志', status: 'fallback', tone: 'warning', routeName: '' },
    { label: '可上线风险', value: '上线闸门未通过，不建议宣称 ready', status: 'hard gate', tone: 'danger', routeName: 'admin-ingestion-center' },
    { label: 'AI fallback', value: 'AI probe disabled，不显示 live LLM 成功', status: 'disabled', tone: 'neutral', routeName: 'review-brain-center' }
  ],
  caliber:
    '本页用于查看系统健康、就绪状态、服务探针、错误率、响应时间和上线闸门风险，属于管理端运维观测面。页面默认不执行部署、回滚、重启或自动修复操作。若数据源标记为 fallback/mixed，请以实际运维命令和服务器状态复核。'
}
