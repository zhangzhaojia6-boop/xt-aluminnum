const ROLE_ALIASES = {
  team_leader: 'machine_operator',
  deputy_leader: 'machine_operator',
  mobile_user: 'machine_operator',
  shift_leader: 'machine_operator'
}

const ROLE_BUCKET_META = {
  machine_operator: { title: '录产量', subtitle: '按卷记录投入、产出重量' },
  energy_stat: { title: '填能耗', subtitle: '记录本班用电、用气' },
  quality_owner: { title: '全公司质检', subtitle: '日/月成品率 + 废料分类' },
  planning_owner: { title: '全公司合同', subtitle: '合同进度 + 排产偏差 + 牌号×规格' },
  energy_chief: { title: '能耗矩阵', subtitle: '跨车间电气合计 + 抄表累计' },
  storage_owner: { title: '储备四件', subtitle: '备料/入库/发货/合同承接' },
  consumable_stat: { title: '生产内勤', subtitle: '每日辅材与内勤数据' },
  shipment_outflow_owner: { title: '园区剪切', subtitle: '客户/批号/卷重/净重 流水' },
  recovery_owner: { title: '回收产量', subtitle: '当日回收车间产量' },
  overhaul_owner: { title: '大修能耗', subtitle: '磨辊子数量 + 能耗' },
}

const OWNER_ROLE_BUCKETS = new Set([
  'quality_owner',
  'planning_owner',
  'energy_chief',
  'storage_owner',
  'consumable_stat',
  'shipment_outflow_owner',
  'recovery_owner',
  'overhaul_owner',
])

function normalizeRole(role) {
  return ROLE_ALIASES[role] || role || ''
}

export function resolveTransitionRoleBucket({ role, isMachineBound }) {
  if (isMachineBound) return 'machine_operator'
  const normalizedRole = normalizeRole(role)
  if (OWNER_ROLE_BUCKETS.has(normalizedRole)) return normalizedRole
  if (normalizedRole === 'energy_stat') return 'energy_stat'
  return 'machine_operator'
}

export function describeTransitionRoleBucket(roleBucket) {
  return ROLE_BUCKET_META[roleBucket] || ROLE_BUCKET_META.machine_operator
}

const OWNER_BUCKET_CTA = {
  quality_owner: { evidence_label: '成品率', primary_cta: '填全公司质检', resume_cta: '继续填全公司质检' },
  planning_owner: { evidence_label: '合同进度', primary_cta: '填全公司合同', resume_cta: '继续填全公司合同' },
  energy_chief: { evidence_label: '能耗合计', primary_cta: '填能耗矩阵', resume_cta: '继续填能耗矩阵' },
  storage_owner: { evidence_label: '储备四件', primary_cta: '填储备四件', resume_cta: '继续填储备四件' },
  consumable_stat: { evidence_label: '辅材', primary_cta: '填生产内勤', resume_cta: '继续填生产内勤' },
  shipment_outflow_owner: { evidence_label: '剪切流水', primary_cta: '录园区剪切', resume_cta: '继续录园区剪切' },
  recovery_owner: { evidence_label: '回收产量', primary_cta: '填回收产量', resume_cta: '继续填回收产量' },
  overhaul_owner: { evidence_label: '大修', primary_cta: '填大修能耗', resume_cta: '继续填大修能耗' },
}

export function buildMobileTransitionMapping({
  role,
  isMachineBound,
  reportStatus,
}) {
  const roleBucket = resolveTransitionRoleBucket({ role, isMachineBound })
  const isResume = ['draft', 'returned'].includes(reportStatus)

  if (OWNER_BUCKET_CTA[roleBucket]) {
    const meta = OWNER_BUCKET_CTA[roleBucket]
    return {
      role_bucket: roleBucket,
      evidence_label: meta.evidence_label,
      primary_cta: isResume ? meta.resume_cta : meta.primary_cta,
    }
  }

  if (roleBucket === 'machine_operator') {
    return {
      role_bucket: roleBucket,
      evidence_label: '产量',
      primary_cta: isResume ? '继续录产量' : '录产量'
    }
  }

  if (roleBucket === 'energy_stat') {
    return {
      role_bucket: roleBucket,
      evidence_label: '用电用气',
      primary_cta: isResume ? '继续填能耗' : '填能耗'
    }
  }

  return {
    role_bucket: roleBucket,
    evidence_label: '班次数据',
    primary_cta: isResume ? '继续填报' : '开始填报'
  }
}

const OWNER_FOLLOWUP = {
  quality_owner: ['自动汇总公司日/月成品率', '自动核对 M/P 双指标', '自动联通钉钉日报'],
  planning_owner: ['自动核对牌号×规格×吨位', '自动汇总余合同', '自动同步生产日报'],
  energy_chief: ['自动比对班次能耗与累计读数', '自动生成跨车间合计', '自动落入经营快照'],
  storage_owner: ['自动汇总备料/入库/发货', '自动核对合同承接', '自动衔接钉钉日报'],
  shipment_outflow_owner: ['自动落入剪切流水台账', '自动联动客户/批号', '自动核对净重'],
  recovery_owner: ['自动落入当日回收产量', '自动核对能耗对比', '自动汇总至公司日报'],
  overhaul_owner: ['自动登记磨辊子数量', '自动并入大修能耗', '自动联通经营留痕'],
}

export function buildTransitionFollowupSteps(roleBucket, { ocrSupported = false } = {}) {
  if (OWNER_FOLLOWUP[roleBucket]) return OWNER_FOLLOWUP[roleBucket]
  if (roleBucket === 'machine_operator') {
    return ['自动校验字段是否完整', '自动留存班次与机台记录', '自动衔接后续处理与汇总']
  }
  if (roleBucket === 'energy_stat') {
    return ['自动并入班次汇总', '自动更新能耗看板', '自动保留处理留痕']
  }
  return ocrSupported
    ? ['自动核对字段完整性', '自动生成催报与处理线索', '自动汇总到观察看板']
    : ['自动核对字段完整性', '自动生成处理线索', '自动汇总到观察看板']
}
