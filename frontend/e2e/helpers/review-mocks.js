import { loginThroughMockedPassword } from './mock-login'

const defaultReviewUser = {
  id: 1,
  username: 'admin',
  name: 'Playwright Admin',
  role: 'admin',
  is_mobile_user: true,
  is_reviewer: true,
  is_manager: true,
  data_scope_type: 'all',
  assigned_shift_ids: []
}

export async function setupReviewSessionAndMocks(page, session = {}) {
  const token = session.token || 'playwright-review-token'
  const user = session.user || defaultReviewUser

  const fulfillJson = (route, body) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body)
  })

  await page.route('**/api/v1/auth/me', async (route) => {
    await fulfillJson(route, user)
  })

  const runtimeTrace = {
    source_lanes: [
      {
        key: 'algorithm_pipeline',
        label: '算法流水线',
        stage_label: '确定性规则',
        status: 'healthy',
        result_targets: ['今日产量', '今日上报状态', '单吨能耗']
      },
      {
        key: 'analysis_agent',
        label: '分析决策助手',
        stage_label: '解释与建议',
        status: 'warning',
        result_targets: ['今日摘要', '今日关注', '近 7 日留存趋势']
      },
      {
        key: 'execution_agent',
        label: '执行交付助手',
        stage_label: '闭环执行',
        status: 'alert',
        result_targets: ['交付与闭环', '数据留存与归档']
      }
    ],
    frontline: {
      reported_count: 31,
      expected_count: 33,
      reminder_count: 2,
      unreported_count: 1,
      late_count: 1
    },
    backline: {
      history_points: 7,
      status: 'healthy'
    },
    delivery: {
      reports_ready_count: 0,
      status: 'blocked'
    },
    orchestration: {
      reliability_score: 76.5,
      risk_level: 'medium',
      blocking_count: 2,
      bottlenecks: ['班次缺报', '交付链路未完成'],
      workers: [
        { key: 'algorithm_pipeline', label: '算法流水线', status: 'healthy', value: '覆盖 84.0' },
        { key: 'analysis_agent', label: '分析决策助手', status: 'warning', value: '质量 71.0' },
        { key: 'execution_agent', label: '执行交付助手', status: 'blocked', value: '交付 63.0' }
      ]
    }
  }

  const liveAggregation = {
    business_date: '2026-05-12',
    business_date_context: {
      requested_business_date: '2026-05-12',
      current_business_date: '2026-05-13',
      active_business_date: '2026-05-12',
      active_date_source: 'recent_upload',
      latest_fill_business_date: '2026-05-12',
      requested_entry_count: 36,
      current_date_entry_count: 0,
      active_date_entry_count: 36,
      has_current_date_entries: false,
      is_requested_current_date: false,
      is_showing_active_business_date: true
    },
    overall_progress: {
      submitted_cells: 2,
      total_cells: 3,
      formal_entry_count: 36,
      draft_entry_count: 0,
      total_entry_count: 36
    },
    workshops: [
      {
        workshop_id: 1,
        workshop_name: '挤压车间',
        workshop_total: {
          input: 220,
          output: 214,
          scrap: 6,
          yield_rate: 97.27
        },
        shift_totals: [
          {
            shift_id: 1,
            shift_name: '白班',
            is_applicable: true,
            total_input: 220,
            total_output: 214,
            yield_rate: 97.27
          }
        ],
        machines: [
          {
            machine_id: 101,
            machine_name: 'XT-ZD-1',
            day_total: {
              input: 220,
              output: 214,
              scrap: 6,
              yield_rate: 97.27
            },
            shifts: [
              {
                shift_id: 1,
                shift_name: '白班',
                submitted_count: 2,
                submission_status: 'all_submitted',
                is_applicable: true,
                attendance_status: 'confirmed',
                attendance_exception_count: 0,
                yield_rate: 97.27
              }
            ]
          }
        ]
      }
    ],
    yield_matrix_lane: {},
    mes_sync_status: {
      lag_seconds: 45
    },
    mes_machine_binding: {
      mes_row_count: 21,
      mes_rows_with_machine: 8,
      mes_rows_without_machine: 13,
      direct_machine_code_count: 0,
      route_inferred_machine_count: 8,
      unresolved_machine_count: 13,
      upstream_machine_code_missing_count: 21,
      fill_entry_count: 36,
      fill_entries_with_mes_match: 22,
      fill_entries_bound_to_machine: 22,
      fill_entries_pending_machine: 0,
      pending_assignment_entry_count: 0,
      pending_machine_assignment_count: 0
    },
    data_source: 'work_order_runtime',
    factory_total: {
      input: 220,
      output: 214,
      scrap: 6,
      yield_rate: 97.27
    }
  }

  const factoryCommandFreshness = {
    source: 'work_order_runtime',
    status: 'fresh',
    lag_seconds: 45,
    last_synced_at: '2026-04-23T08:00:00Z'
  }

  const factoryCommandOverview = {
    wip_tons: 80,
    today_output_tons: 1175,
    stock_tons: 52,
    abnormal_count: 1,
    freshness: factoryCommandFreshness
  }

  const factoryCommandMachineLines = [
    {
      line_code: 'XT-ZD-1',
      line_name: 'XT-ZD-1',
      workshop_name: '挤压车间',
      active_coil_count: 10,
      active_tons: 80,
      finished_tons: 52,
      stalled_count: 1,
      cost_estimate: { estimated_cost: 210000, missing_data: [] },
      margin_estimate: { estimated_gross_margin: 70000, missing_data: [] }
    }
  ]

  const factoryCommandCoils = [
    {
      coil_key: 'TK-20260423-001',
      tracking_card_no: 'TK-20260423-001',
      batch_no: 'B20260423',
      material_code: '6061',
      previous_process: '熔铸',
      current_process: '挤压',
      next_process: '时效',
      destination: { kind: 'warehouse', label: '成品库' }
    }
  ]

  const executiveDashboard = {
    business_date: '2026-05-12',
    total_output_tons: 1175,
    total_revenue: 184000,
    total_cost: 23900,
    total_profit: 160100,
    profit_margin_pct: 87.01,
    vs_yesterday_profit_delta: 11200,
    vs_yesterday_profit_delta_pct: 7.52,
    mtd_revenue: 184000,
    mtd_cost: 23900,
    mtd_profit: 160100,
    workshops: [
      {
        workshop_id: 1,
        workshop_code: 'ZP1',
        workshop_name: '挤压车间',
        output_tons: 1175,
        revenue: 184000,
        cost: 23900,
        profit: 160100,
        has_missing_fee_rule: false
      }
    ],
    aluminum_price: {
      price_date: '2026-05-12',
      price_per_ton: 20240,
      delta_vs_prev: 120
    },
    is_estimated: true,
    has_missing_fee_rule: false,
    estimation_note: '阶段 1：按车间粒度估算。'
  }

  const executiveMachineRanking = [
    {
      workshop_id: 1,
      workshop_code: 'ZP1',
      workshop_name: '挤压车间',
      machine_line_id: 101,
      alloy_grade: '6061',
      process_type: '挤压',
      output_tons: 1175,
      processing_fee_per_ton: 180,
      revenue: 184000,
      cost: 23900,
      gross_profit: 160100,
      gross_margin_pct: 87.01,
      has_missing_fee_rule: false,
      is_estimated: true,
      note: '测试估算'
    }
  ]

  const executivePriceTrend = [
    { price_date: '2026-05-08', price_per_ton: 19960, source: 'mock' },
    { price_date: '2026-05-09', price_per_ton: 20080, source: 'mock' },
    { price_date: '2026-05-10', price_per_ton: 20120, source: 'mock' },
    { price_date: '2026-05-11', price_per_ton: 20120, source: 'mock' },
    { price_date: '2026-05-12', price_per_ton: 20240, source: 'mock' }
  ]

  await page.route('**/api/v1/factory-command/overview', async (route) => {
    await fulfillJson(route, factoryCommandOverview)
  })

  await page.route('**/api/v1/factory-command/workshops', async (route) => {
    await fulfillJson(route, [
      {
        workshop_name: '挤压车间',
        active_coil_count: 10,
        active_tons: 80,
        stalled_count: 1
      }
    ])
  })

  await page.route('**/api/v1/factory-command/machine-lines', async (route) => {
    await fulfillJson(route, factoryCommandMachineLines)
  })

  await page.route('**/api/v1/factory-command/coils', async (route) => {
    await fulfillJson(route, factoryCommandCoils)
  })

  await page.route('**/api/v1/factory-command/coils/*/flow', async (route) => {
    await fulfillJson(route, {
      ...factoryCommandCoils[0],
      freshness: factoryCommandFreshness
    })
  })

  await page.route('**/api/v1/factory-command/cost-benefit', async (route) => {
    await fulfillJson(route, {
      estimated_revenue: 280000,
      estimated_cost: 210000,
      estimated_margin: 70000,
      missing_data: [],
      freshness: factoryCommandFreshness
    })
  })

  await page.route('**/api/v1/factory-command/destinations', async (route) => {
    await fulfillJson(route, [
      { kind: 'warehouse', label: '成品库', tons: 52 },
      { kind: 'shipment', label: '发货', tons: 48 }
    ])
  })

  await page.route('**/api/v1/executive/dashboard**', async (route) => {
    await fulfillJson(route, executiveDashboard)
  })

  await page.route('**/api/v1/executive/machine-ranking**', async (route) => {
    await fulfillJson(route, executiveMachineRanking)
  })

  await page.route('**/api/v1/executive/aluminum-price-trend**', async (route) => {
    await fulfillJson(route, executivePriceTrend)
  })

  await page.route('**/api/v1/dashboard/factory-director**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        leader_summary: { summary_text: '今日主线稳定，关注交付缺口。' },
        leader_metrics: {
          today_total_output: 1175,
          energy_per_ton: 234.6,
          in_process_weight: 80,
          storage_finished_weight: 52,
          shipment_weight: 48,
          storage_inbound_area: 960,
          contract_weight: 120,
          estimated_revenue: 280000,
          estimated_cost: 210000,
          estimated_margin: 70000,
          active_contract_count: 3,
          stalled_contract_count: 1,
          active_coil_count: 10,
          yield_rate: 98.2,
          total_attendance: 33
        },
        management_estimate: {
          estimate_ready: true,
          estimated_revenue: 280000,
          estimated_cost: 210000,
          estimated_margin: 70000,
          energy_cost: 46000,
          labor_cost: 38000,
          active_contract_count: 3,
          stalled_contract_count: 1,
          active_coil_count: 10,
          reporting_rate: 94
        },
        month_to_date_output: 1175,
        exception_lane: {
          unreported_shift_count: 1,
          mobile_exception_count: 1,
          production_exception_count: 0,
          returned_shift_count: 1,
          pending_report_publish_count: 1,
          reminder_late_count: 1,
          reconciliation_open_count: 1
        },
        workshop_reporting_status: [
          {
            workshop_id: 1,
            workshop_name: '挤压车间',
            source_variant: 'mobile',
            source_label: '主操直录',
            report_status: 'submitted',
            status_hint: '主操已报',
            output_weight: 1175
          }
        ],
        history_digest: {
          daily_snapshots: [],
          month_archive: { reported_days: 1, total_output: 1175, average_daily_output: 1175 },
          year_archive: { active_months: 1, total_output: 1175, average_monthly_output: 1175 }
        },
        runtime_trace: runtimeTrace
      })
    })
  })

  await page.route('**/api/v1/dashboard/workshop-director**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_output: 1175,
        month_to_date_output: 1175,
        pending_shift_count: 1,
        mobile_reporting_summary: { reporting_rate: 94 },
        reminder_summary: { unreported_count: 1, late_report_count: 1 },
        exception_lane: {
          unreported_shift_count: 1,
          returned_shift_count: 1,
          reminder_late_count: 1,
          pending_report_publish_count: 1,
          mobile_exception_count: 1
        },
        energy_summary: { energy_per_ton: 234.6 },
        production_lane: [
          {
            workshop_name: '挤压车间',
            source_label: '主操直录',
            source_variant: 'mobile',
            total_output: 1175,
            compare_value: 1120,
            delta_vs_yesterday: 55
          }
        ],
        energy_lane: [
          {
            shift_code: 'A',
            source_label: '专项补录',
            source_variant: 'owner',
            electricity_value: 230,
            gas_value: 12,
            water_value: 8,
            energy_per_ton: 234.6
          }
        ],
        inventory_lane: [
          {
            team_name: '甲班',
            source_label: '系统导入',
            source_variant: 'import',
            storage_prepared: 12,
            storage_finished: 52,
            storage_inbound_area: 960,
            shipment_weight: 48,
            actual_inventory_weight: 36
          }
        ],
        runtime_trace: runtimeTrace
      })
    })
  })

  await page.route('**/api/v1/dashboard/delivery-status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        delivery_ready: false,
        missing_steps: ['日报未生成'],
        reports_reviewed_count: 0,
        reports_published_count: 0,
        reports_published: 0
      })
    })
  })

  await page.route('**/api/v1/aggregation/live/detail**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            tracking_card_no: 'TK-20260423-001',
            entry_id: 1001,
            work_order_id: 2001,
            entry_status: 'submitted',
            entry_type: 'completed',
            input_weight: 110,
            output_weight: 107,
            scrap_weight: 3,
            yield_rate: 97.27,
            machine_id: 101,
            shift_id: 1
          }
        ]
      })
    })
  })

  await page.route('**/api/v1/aggregation/live**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(liveAggregation)
    })
  })

  await page.route('**/api/v1/realtime/stream**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream'
      },
      body: ': keep-alive\n\n'
    })
  })

  await page.route('**/api/v1/master/workshops**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          { id: 1, code: 'ZP1', name: '总装车间', workshop_code: 'ZP1', workshop_name: '总装车间', is_active: true, sort_order: 1 },
          { id: 2, code: 'ZP2', name: '轧机一车间', workshop_code: 'ZP2', workshop_name: '轧机一车间', is_active: true, sort_order: 2 }
        ],
        total: 2
      })
    })
  })


  await page.route('**/api/v1/master/teams**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          { id: 1, name: '白班', workshop_id: 1, workshop_name: '总装车间' }
        ],
        total: 1
      })
    })
  })

  await page.route('**/api/v1/master/equipment**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 101,
            code: 'XT-ZD-1',
            name: 'XT-ZD-1',
            workshop_id: 1,
            workshop_name: '挤压车间',
            bound_user_id: null,
            bound_user_name: '',
            bound_username: ''
          }
        ],
        total: 1
      })
    })
  })
  await page.route('**/api/v1/imports/history**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 1,
            filename: 'mes-export.xlsx',
            import_type: 'mes',
            status: 'success',
            row_count: 128,
            success_count: 126,
            failed_count: 2,
            created_at: '2026-04-23T08:00:00Z'
          }
        ],
        total: 1
      })
    })
  })

  const fulfillUsers = async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 1,
            username: 'admin',
            name: '系统管理员',
            role: 'admin',
            is_mobile_user: true,
            is_reviewer: true,
            is_manager: true,
            data_scope_type: 'all'
          },
          {
            id: 2,
            username: 'operator',
            name: '班组操作员',
            role: 'operator',
            is_mobile_user: true,
            is_reviewer: false,
            is_manager: false,
            data_scope_type: 'self_team'
          }
        ],
        total: 2,
        skip: 0,
        limit: 300
      })
    })
  }

  await page.route('**/api/v1/users', fulfillUsers)
  await page.route('**/api/v1/users/', fulfillUsers)
  await page.route('**/api/v1/users/**', fulfillUsers)
  await page.route(/.*\/api\/v1\/users\/?(\?.*)?$/, fulfillUsers)

  await page.route('**/api/v1/reports**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
        skip: 0,
        limit: 20
      })
    })
  })

  await page.route('**/api/v1/quality/issues**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 1,
            issue_type: 'yield_rate',
            severity: 'warning',
            status: 'open',
            title: '成材率低于阈值',
            workshop_name: '挤压车间',
            machine_name: 'XT-ZD-1',
            business_date: '2026-04-23',
            detail: '白班成材率低于目标值'
          }
        ],
        total: 1,
        skip: 0,
        limit: 20
      })
    })
  })

  const aiConversations = [
    {
      id: 'conv-1',
      title: 'AI 工作台',
      created_at: '2026-04-23T08:00:00Z',
      updated_at: '2026-04-23T08:10:00Z'
    }
  ]

  const aiMessages = [
    {
      id: 'msg-1',
      role: 'assistant',
      content: '当前生产运行稳定。',
      created_at: '2026-04-23T08:10:00Z'
    }
  ]

  await page.route('**/api/v1/ai/assistant/conversations', async (route) => {
    await fulfillJson(route, aiConversations)
  })

  await page.route('**/api/v1/ai/assistant/conversations/*/messages', async (route) => {
    await fulfillJson(route, aiMessages)
  })

  await page.route('**/api/v1/ai/conversations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: aiConversations
      })
    })
  })

  await page.route('**/api/v1/ai/conversations/conv-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'conv-1',
        title: 'AI 工作台',
        messages: []
      })
    })
  })


  await page.route('**/api/v1/mobile/bootstrap', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entry_mode: 'web_debug',
        current_identity_source: 'account',
        current_scope_summary: { data_scope_type: 'all' },
        workshop_id: 1,
        workshop_name: '挤压车间',
        workshop_type: 'extrusion',
        is_machine_bound: false
      })
    })
  })

  await page.route('**/api/v1/mobile/current-shift', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-04-23',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 1,
        workshop_name: '挤压车间',
        workshop_type: 'extrusion',
        can_submit: true,
        is_machine_bound: false
      })
    })
  })

  await page.route('**/api/v1/templates/extrusion', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        supports_ocr: false,
        role_bucket: 'operator',
        entry_fields: [],
        shift_fields: [],
        extra_fields: [],
        qc_fields: [],
        readonly_fields: []
      })
    })
  })
  await page.route('**/api/v1/assistant/capabilities**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        connected: true,
        capabilities: [{ key: 'query' }, { key: 'generate_image' }],
        integrations: [{ key: 'dashboard', label: '审阅首页' }],
        groups: [
          { key: 'analysis', label: '分析决策', ready: true },
          { key: 'execution', label: '执行交付', ready: true },
          { key: 'generate_image', label: '图像输出', ready: true }
        ]
      })
    })
  })

  await page.route('**/api/v1/assistant/live-probe**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        summary: '探针在线',
        health: 'good',
        latency_ms: 96,
        risk_level: 'low',
        signals: []
      })
    })
  })

  await page.route('**/api/v1/dashboard/external-readiness', async (route) => {
    await fulfillJson(route, {
      hard_gate_passed: false,
      module_usable: false,
      external_connection_enabled: false,
      hard_issues: [
        {
          level: 'hard',
          code: 'MES_UNCONFIGURED',
          required_env: ['MES_ADAPTER', 'MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD']
        },
        {
          level: 'hard',
          code: 'WORKFLOW_DISABLED',
          required_env: ['WORKFLOW_ENABLED']
        },
        {
          level: 'hard',
          code: 'LLM_DISABLED',
          required_env: ['LLM_ENABLED', 'LLM_API_BASE', 'LLM_API_KEY', 'LLM_MODEL', 'LLM_ENDPOINT_ID']
        },
        {
          level: 'hard',
          code: 'DINGTALK_DISABLED',
          required_env: ['DINGTALK_ENABLED', 'DINGTALK_CORP_ID', 'DINGTALK_APP_KEY', 'DINGTALK_APP_SECRET', 'DINGTALK_AGENT_ID']
        },
        {
          level: 'hard',
          code: 'APP_CONNECTION_CONFIG_MISSING',
          required_env: ['APP_CONNECTION_ENABLED', 'APP_CONNECTION_PUSH_MODE', 'APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY']
        }
      ],
      warning_issues: [],
      missing_inputs: [
        {
          issue_code: 'MES_UNCONFIGURED',
          level: 'hard',
          purpose: '外部 MES 数据源',
          location: '服务器 backend/.env',
          missing_fields: ['MES_ADAPTER', 'MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD'],
          impact: '外部 MES 投影不可用，实时流转与机列绑定只能依赖本地填报。',
          suggested_value: 'MES_ADAPTER=mvc；其余字段填现场 MES 地址和账号密钥。'
        },
        {
          issue_code: 'WORKFLOW_DISABLED',
          level: 'hard',
          purpose: '自动日报 workflow',
          location: '服务器 backend/.env',
          missing_fields: ['WORKFLOW_ENABLED'],
          impact: '自动日报生成与后续触达链路不会运行。',
          suggested_value: 'WORKFLOW_ENABLED=true。'
        },
        {
          issue_code: 'LLM_DISABLED',
          level: 'hard',
          purpose: 'LLM/AI 摘要增强',
          location: '服务器 backend/.env',
          missing_fields: ['LLM_ENABLED', 'LLM_API_BASE', 'LLM_API_KEY', 'LLM_MODEL', 'LLM_ENDPOINT_ID'],
          impact: 'AI 摘要与分析增强不可用，不能宣称 AI 能力正式联通。',
          suggested_value: 'LLM_ENABLED=true；LLM_API_KEY=<redacted>'
        },
        {
          issue_code: 'DINGTALK_DISABLED',
          level: 'hard',
          purpose: '钉钉日报触达',
          location: '服务器 backend/.env',
          missing_fields: ['DINGTALK_ENABLED', 'DINGTALK_CORP_ID', 'DINGTALK_APP_KEY', 'DINGTALK_APP_SECRET', 'DINGTALK_AGENT_ID'],
          impact: '日报和提醒不能发送到钉钉。',
          suggested_value: 'DINGTALK_ENABLED=true；其余字段填钉钉开放平台真实应用配置。'
        },
        {
          issue_code: 'APP_CONNECTION_CONFIG_MISSING',
          level: 'hard',
          purpose: '应用连接外发',
          location: '服务器 backend/.env',
          missing_fields: ['APP_CONNECTION_ENABLED', 'APP_CONNECTION_PUSH_MODE', 'APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
          impact: '统计模块不能对外推送，正式外部连接面未启用。',
          suggested_value: 'APP_CONNECTION_ENABLED=true；APP_CONNECTION_API_KEY=<redacted>'
        }
      ]
    })
  })

  await page.route('**/api/v1/mes/sync-status', async (route) => {
    await fulfillJson(route, {
      status: 'unconfigured',
      source: 'local_entry',
      action_required: 'configure_mes',
      required_env: ['MES_ADAPTER', 'MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD'],
      last_synced_at: null
    })
  })

  await page.route('**/api/v1/mes/sync-runs**', async (route) => {
    await fulfillJson(route, {
      summary: {
        total_count: 0,
        success_count: 0,
        failed_count: 0
      },
      items: []
    })
  })

  if (!session.skipLogin) {
    await loginThroughMockedPassword(page, {
      token,
      user,
      username: session.username,
      password: session.password
    })
  }
}
