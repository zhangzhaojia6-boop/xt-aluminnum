const ROLE_ALIASES = {
  team_leader: 'shift_leader',
  deputy_leader: 'shift_leader',
  mobile_user: 'shift_leader'
}

const ROLE_BUCKET_META = {
  machine_operator: {
    title: '录产量',
    subtitle: '按卷记录投入、产出重量'
  },
  shift_leader: {
    title: '录产量',
    subtitle: '记录本班次生产数据'
  },
  weigher: {
    title: '核重量',
    subtitle: '逐卷核实过磅重量'
  },
  qc: {
    title: '填质检',
    subtitle: '逐卷填写质检结论'
  },
  energy_stat: {
    title: '填能耗',
    subtitle: '记录本班用电、用气'
  },
  maintenance_lead: {
    title: '报停机',
    subtitle: '记录停机时长和原因'
  },
  hydraulic_lead: {
    title: '报油耗',
    subtitle: '记录液压油、齿轮油用量'
  },
  consumable_stat: {
    title: '报辅材',
    subtitle: '记录车间辅材消耗'
  },
  contracts: {
    title: '填合同',
    subtitle: '记录合同接单、投料进度'
  },
  inventory_keeper: {
    title: '填出入库',
    subtitle: '记录入库、发货、库存'
  },
  utility_manager: {
    title: '填水电气',
    subtitle: '记录全厂用电、天然气、用水'
  },
}

function normalizeRole(role) {
  return ROLE_ALIASES[role] || role || ''
}

export function resolveTransitionRoleBucket({ role, isMachineBound }) {
  if (isMachineBound) return 'machine_operator'
  const normalizedRole = normalizeRole(role)
  if (normalizedRole === 'weigher') return 'weigher'
  if (normalizedRole === 'qc') return 'qc'
  if (normalizedRole === 'energy_stat') return 'energy_stat'
  if (normalizedRole === 'maintenance_lead') return 'maintenance_lead'
  if (normalizedRole === 'hydraulic_lead') return 'hydraulic_lead'
  if (normalizedRole === 'consumable_stat') return 'consumable_stat'
  if (normalizedRole === 'contracts') return 'contracts'
  if (normalizedRole === 'inventory_keeper') return 'inventory_keeper'
  if (normalizedRole === 'utility_manager') return 'utility_manager'
  return 'shift_leader'
}

export function describeTransitionRoleBucket(roleBucket) {
  return ROLE_BUCKET_META[roleBucket] || ROLE_BUCKET_META.shift_leader
}

export function buildMobileTransitionMapping({
  role,
  isMachineBound,
  reportStatus,
}) {
  const roleBucket = resolveTransitionRoleBucket({ role, isMachineBound })
  const isResume = ['draft', 'returned'].includes(reportStatus)

  if (roleBucket === 'machine_operator') {
    return {
      role_bucket: roleBucket,
      evidence_label: '产量',
      primary_cta: isResume ? '继续录产量' : '录产量'
    }
  }

  if (roleBucket === 'weigher') {
    return {
      role_bucket: roleBucket,
      evidence_label: '过磅重量',
      primary_cta: isResume ? '继续核重量' : '核重量'
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

  if (roleBucket === 'maintenance_lead') {
    return {
      role_bucket: roleBucket,
      evidence_label: '停机记录',
      primary_cta: isResume ? '继续报停机' : '报停机'
    }
  }

  if (roleBucket === 'hydraulic_lead') {
    return {
      role_bucket: roleBucket,
      evidence_label: '油耗记录',
      primary_cta: isResume ? '继续报油耗' : '报油耗'
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

export function buildTransitionFollowupSteps(roleBucket, { ocrSupported = false } = {}) {
  if (roleBucket === 'machine_operator') {
    return ['自动校验字段是否完整', '自动留存班次与机台记录', '自动衔接后续处理与汇总']
  }
  if (roleBucket === 'weigher') {
    return ['自动回写复核状态', '自动锁定已复核字段', '自动通知后续质检环节']
  }
  if (roleBucket === 'qc') {
    return ['自动更新质检状态', '自动保留质检留痕', '自动同步发布前口径']
  }
  if (roleBucket === 'energy_stat') {
    return ['自动并入班次汇总', '自动更新能耗看板', '自动保留处理留痕']
  }
  if (roleBucket === 'maintenance_lead') {
    return ['自动挂接停机记录', '自动进入异常看板', '自动保留设备留痕']
  }
  if (roleBucket === 'hydraulic_lead') {
    return ['自动沉淀耗材记录', '自动汇总班次口径', '自动保留历史留痕']
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
