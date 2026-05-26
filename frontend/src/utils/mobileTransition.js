const ROLE_ALIASES = {
  team_leader: 'shift_leader',
  deputy_leader: 'shift_leader',
  mobile_user: 'shift_leader'
}

const ROLE_BUCKET_META = {
  machine_operator: { title: '录产量', subtitle: '按卷记录投入、产出重量' },
  shift_leader: { title: '录产量', subtitle: '记录本班次生产数据' },
  qc: { title: '填质检', subtitle: '逐卷填写质检结论' },
  energy_stat: { title: '填能耗', subtitle: '记录本班用电、用气' },
  consumable_stat: { title: '报辅材', subtitle: '记录车间辅材消耗' },
  contracts: { title: '填合同', subtitle: '记录合同接单、投料进度' },
  inventory_keeper: { title: '填出入库', subtitle: '记录入库、发货、库存' },
  utility_manager: { title: '填水电气', subtitle: '记录全厂用电、天然气、用水' },
  quality_owner: { title: '全公司质检', subtitle: '日/月成品率 + 废料分类' },
  planning_owner: { title: '全公司合同', subtitle: '合同进度 + 排产偏差 + 牌号×规格' },
  energy_chief: { title: '能耗矩阵', subtitle: '跨车间电气合计 + 抄表累计' },
  storage_owner: { title: '储备四件', subtitle: '备料/入库/发货/合同承接' },
  shipment_outflow_owner: { title: '园区剪切', subtitle: '客户/批号/卷重/净重 流水' },
  recovery_owner: { title: '回收产量', subtitle: '当日回收车间产量' },
  overhaul_owner: { title: '大修能耗', subtitle: '磨辊子数量 + 能耗' },
}

const OWNER_ROLE_BUCKETS = new Set([
  'quality_owner',
  'planning_owner',
  'energy_chief',
  'storage_owner',
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
  if (normalizedRole === 'qc') return 'qc'
  if (normalizedRole === 'energy_stat') return 'energy_stat'
  if (normalizedRole === 'consumable_stat') return 'consumable_stat'
  if (normalizedRole === 'contracts') return 'contracts'
  if (normalizedRole === 'inventory_keeper') return 'inventory_keeper'
  if (normalizedRole === 'utility_manager') return 'utility_manager'
  return 'shift_leader'
}

export function describeTransitionRoleBucket(roleBucket) {
  return ROLE_BUCKET_META[roleBucket] || ROLE_BUCKET_META.shift_leader
}

const OWNER_BUCKET_CTA = {
  quality_owner: { evidence_label: '成品率', primary_cta: '填全公司质检', resume_cta: '继续填全公司质检' },
  planning_owner: { evidence_label: '合同进度', primary_cta: '填全公司合同', resume_cta: '继续填全公司合同' },
  energy_chief: { evidence_label: '能耗合计', primary_cta: '填能耗矩阵', resume_cta: '继续填能耗矩阵' },
  storage_owner: { evidence_label: '储备四件', primary_cta: '填储备四件', resume_cta: '继续填储备四件' },
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

  if (roleBucket === 'qc') {
    return {
      role_bucket: roleBucket,
      evidence_label: '质检结论',
      primary_cta: isResume ? '继续填质检' : '填质检'
    }
  }

  if (roleBucket === 'energy_stat') {
    return {
      role_bucket: roleBucket,
      evidence_label: '用电用气',
      primary_cta: isResume ? '继续填能耗' : '填能耗'
    }
  }

  if (roleBucket === 'consumable_stat') {
    return {
      role_bucket: roleBucket,
      evidence_label: '辅材消耗',
      primary_cta: isResume ? '继续报辅材' : '报辅材'
    }
  }

  if (roleBucket === 'contracts') {
    return {
      role_bucket: roleBucket,
      evidence_label: '合同进度',
      primary_cta: isResume ? '继续填合同' : '填合同'
    }
  }

  if (roleBucket === 'inventory_keeper') {
    return {
      role_bucket: roleBucket,
      evidence_label: '出入库',
      primary_cta: isResume ? '继续填出入库' : '填出入库'
    }
  }

  if (roleBucket === 'utility_manager') {
    return {
      role_bucket: roleBucket,
      evidence_label: '水电气',
      primary_cta: isResume ? '继续填水电气' : '填水电气'
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
  if (roleBucket === 'qc') {
    return ['自动更新质检状态', '自动保留质检留痕', '自动同步发布前口径']
  }
  if (roleBucket === 'energy_stat') {
    return ['自动并入班次汇总', '自动更新能耗看板', '自动保留处理留痕']
  }
  if (roleBucket === 'consumable_stat') {
    return ['自动汇总辅材吨耗', '自动接入耗材日报', '自动保留历史留痕']
  }
  if (roleBucket === 'contracts') {
    return ['自动汇总余合同', '自动刷新交付视图', '自动沉淀经营口径']
  }
  if (roleBucket === 'inventory_keeper') {
    return ['自动更新库存台账', '自动刷新出入库视图', '自动保留日月留存']
  }
  if (roleBucket === 'utility_manager') {
    return ['自动汇总水电气', '自动刷新趋势口径', '自动保留经营留痕']
  }
  return ocrSupported
    ? ['自动核对字段完整性', '自动生成催报与处理线索', '自动汇总到观察看板']
    : ['自动核对字段完整性', '自动生成处理线索', '自动汇总到观察看板']
}
