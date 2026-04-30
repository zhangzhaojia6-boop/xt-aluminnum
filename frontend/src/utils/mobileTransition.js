const ROLE_ALIASES = {
  team_leader: 'shift_leader',
  deputy_leader: 'shift_leader',
  mobile_user: 'shift_leader'
}

const ROLE_BUCKET_META = {
  machine_operator: {
    title: '机台直录',
    subtitle: '只录本机台原始值。'
  },
  shift_leader: {
    title: '班次直录',
    subtitle: '只录本班原始值。'
  },
  weigher: {
    title: '过磅补录',
    subtitle: '只录复核重量。'
  },
  qc: {
    title: '质检补录',
    subtitle: '只录质检结论。'
  },
  energy_stat: {
    title: '能耗补录',
    subtitle: '只录当班能耗。'
  },
  maintenance_lead: {
    title: '机修补录',
    subtitle: '只录停机与设备异常。'
  },
  hydraulic_lead: {
    title: '液压补录',
    subtitle: '只录液压耗用。'
  },
  consumable_stat: {
    title: '耗材统计补录',
    subtitle: '只录车间辅材耗用。'
  },
  contracts: {
    title: '计划科补录',
    subtitle: '只录合同与投料口径。'
  },
  inventory_keeper: {
    title: '成品库补录',
    subtitle: '只录入库、发货与结存。'
  },
  utility_manager: {
    title: '水电气补录',
    subtitle: '只录全厂水、电、气。'
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
  ocrSupported = false
}) {
  const roleBucket = resolveTransitionRoleBucket({ role, isMachineBound })
  const isResume = ['draft', 'returned'].includes(reportStatus)

  if (roleBucket === 'machine_operator') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去机台数据要先写纸卡，再层层转抄。',
      new_action: '现在只录本机台、本班次的原始值和随行卡信息。',
      system_auto_followup: '系统自动校验、留痕，并把后续汇总和提醒接住。',
      evidence_label: '机台原始值',
      primary_cta: isResume ? '继续本机填报' : '开始本机填报'
    }
  }

  if (roleBucket === 'weigher') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去复核重量要回传给统计再补表。',
      new_action: '现在只补录过磅复核值，系统自动关联当前随行卡和班次。',
      system_auto_followup: '系统自动回写状态、保留留痕，并接给后续环节。',
      evidence_label: '复核重量',
      primary_cta: isResume ? '继续复核填报' : '开始复核填报'
    }
  }

  if (roleBucket === 'qc') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去质检结论要单独传递，前后状态容易脱节。',
      new_action: '现在只补录质检结论和备注。',
      system_auto_followup: '系统自动更新质检状态、保留留痕，并同步到后续报表。',
      evidence_label: '质检结论',
      primary_cta: isResume ? '继续质检填报' : '开始质检填报'
    }
  }

  if (roleBucket === 'energy_stat') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去能耗数据要单独统计，再回填主表。',
      new_action: '现在只录入本班能耗原始值。',
      system_auto_followup: '系统自动汇总能耗口径、更新看板并保留留痕。',
      evidence_label: '能耗原始值',
      primary_cta: isResume ? '继续能耗填报' : '开始能耗填报'
    }
  }

  if (roleBucket === 'maintenance_lead') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去停机原因需要另找人补充说明。',
      new_action: '现在只补录停机时长和设备异常。',
      system_auto_followup: '系统自动挂接到班次记录，并带入异常看板。',
      evidence_label: '停机与设备状态',
      primary_cta: isResume ? '继续机修补录' : '开始机修补录'
    }
  }

  if (roleBucket === 'hydraulic_lead') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去液压耗材要单独记账，月底再并表。',
      new_action: '现在只补录液压油和辅材耗用。',
      system_auto_followup: '系统自动沉淀班次耗材口径，并保留历史记录。',
      evidence_label: '液压耗材',
      primary_cta: isResume ? '继续液压补录' : '开始液压补录'
    }
  }

  if (roleBucket === 'consumable_stat') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去辅材耗用分散在各车间表格里。',
      new_action: '现在只补录本车间辅材吨耗。',
      system_auto_followup: '系统自动汇总辅材口径，并接入耗材日报。',
      evidence_label: '辅材吨耗',
      primary_cta: isResume ? '继续耗材补录' : '开始耗材补录'
    }
  }

  if (roleBucket === 'contracts') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去合同口径独立维护，现场进度很难同屏看到。',
      new_action: '现在只补录当日合同、月累计、余合同和投料口径。',
      system_auto_followup: '系统自动汇总余合同变化、投料和交付视图。',
      evidence_label: '合同进度口径',
      primary_cta: isResume ? '继续计划科补录' : '开始计划科补录'
    }
  }

  if (roleBucket === 'inventory_keeper') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去入库、发货、寄存要分别报给统计。',
      new_action: '现在只补录成品库入库、发货、寄存和库存结存。',
      system_auto_followup: '系统自动更新库存看板，并沉淀日月留存。',
      evidence_label: '库存原始值',
      primary_cta: isResume ? '继续成品库补录' : '开始成品库补录'
    }
  }

  if (roleBucket === 'utility_manager') {
    return {
      role_bucket: roleBucket,
      legacy_responsibility: '过去公辅数据分散在不同表格里，月底再汇总。',
      new_action: '现在只补录全厂用电、天然气和水耗原始值。',
      system_auto_followup: '系统自动汇总公辅趋势，并接入经营分析。',
      evidence_label: '公辅原始值',
      primary_cta: isResume ? '继续水电气补录' : '开始水电气补录'
    }
  }

  return {
    role_bucket: roleBucket,
    legacy_responsibility: '过去班次原始值要先汇总，再往上层层传递。',
    new_action: ocrSupported
      ? '现在只需确认本班原始值，可手动填写，也可先拍照识别后再核对。'
      : '现在只需确认本班原始值并直接录入系统。',
    system_auto_followup: '系统自动催报、汇总、生成线索，并同步更新驾驶舱。',
    evidence_label: '班次原始值',
    primary_cta: isResume ? '继续本班填报' : '开始本班填报'
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
