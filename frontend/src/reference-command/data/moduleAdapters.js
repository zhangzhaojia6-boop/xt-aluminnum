const defaultKpis = [
  { label: '今日产量', value: '5,824', unit: '吨', trend: '+8.6%', icon: '产' },
  { label: '订单达成', value: '96.7', unit: '%', trend: '+2.1%', icon: '单' },
  { label: '综合良率', value: '98.2', unit: '%', trend: '+1.3%', icon: '质' }
]

const defaultRows = [
  { name: '铸造一线', value: '1,265', rate: '92.1%', state: '正常' },
  { name: '铸造二线', value: '1,132', rate: '94.6%', state: '正常' },
  { name: '精整区', value: '986', rate: '91.3%', state: '关注' }
]

const defaultTrend = [18, 24, 21, 33, 29, 36, 41, 35]

const defaultActions = [
  { key: 'primary', label: '进入处理', primary: true },
  { key: 'export', label: '导出' }
]

function compactViewModel(payload = {}, overrides = {}) {
  return {
    kpis: payload.kpis || overrides.kpis || defaultKpis,
    tableRows: payload.tableRows || payload.rows || overrides.tableRows || defaultRows,
    trend: payload.trend || overrides.trend || defaultTrend,
    risks: payload.risks || overrides.risks || [{ level: '中', text: '异常补卡待确认' }],
    statuses: payload.statuses || overrides.statuses || [{ label: '系统在线', state: 'normal' }],
    actions: payload.actions || overrides.actions || defaultActions,
    raw: payload
  }
}

export function adaptCommandOverview(payload = {}) {
  return compactViewModel(payload, {
    kpis: [
      { label: '今日产量', value: '5,824', unit: '吨', trend: '+8.6%', icon: '产' },
      { label: '订单达成率', value: '96.7', unit: '%', trend: '+2.1%', icon: '单' },
      { label: '综合良品率', value: '98.2', unit: '%', trend: '+1.3%', icon: '质' },
      { label: '异常数', value: '12', unit: '项', trend: '待处置', icon: '异' }
    ]
  })
}

export function adaptEntryHome(payload = {}) {
  return compactViewModel(payload, {
    kpis: [
      { label: '待填任务', value: '12', unit: '项', trend: '今日', icon: '填' },
      { label: '已提交', value: '18', unit: '单', trend: '已同步', icon: '交' },
      { label: '异常补卡', value: '3', unit: '条', trend: '待处理', icon: '补' }
    ]
  })
}

export function adaptEntryFlow(payload = {}) {
  return compactViewModel(payload, {
    kpis: [
      { label: '当前步骤', value: '2', unit: '/6', trend: '产量录入', icon: '步' },
      { label: '产量', value: '285.60', unit: '吨', trend: '班次', icon: '量' },
      { label: '良率', value: '98.5', unit: '%', trend: '自动估算', icon: '良' }
    ]
  })
}

export const adaptFactoryBoard = compactViewModel
export const adaptReviewTasks = compactViewModel
export const adaptReports = compactViewModel
export const adaptQuality = compactViewModel
export const adaptCost = compactViewModel
export const adaptBrain = compactViewModel
export const adaptIngestion = compactViewModel
export const adaptOps = compactViewModel
export const adaptGovernance = compactViewModel
export const adaptMaster = compactViewModel

export function adaptModuleView(moduleId, payload = {}) {
  const adapters = {
    '01': adaptCommandOverview,
    '03': adaptEntryHome,
    '04': adaptEntryFlow,
    '05': adaptFactoryBoard,
    '06': adaptIngestion,
    '07': adaptReviewTasks,
    '08': adaptReports,
    '09': adaptQuality,
    '10': adaptCost,
    '11': adaptBrain,
    '12': adaptOps,
    '13': adaptGovernance,
    '14': adaptMaster,
    '15': adaptEntryHome
  }
  return (adapters[moduleId] || compactViewModel)(payload)
}
