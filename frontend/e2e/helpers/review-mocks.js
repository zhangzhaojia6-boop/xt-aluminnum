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

  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem(
      'aluminum_bypass_user',
      JSON.stringify(user)
    )
    localStorage.removeItem('aluminum_bypass_machine')
  }, { token, user })

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
    business_date: '2026-04-23',
    overall_progress: {
      submitted_cells: 2,
      total_cells: 3
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
    data_source: 'work_order_runtime',
    factory_total: {
      input: 220,
      output: 214,
      scrap: 6,
      yield_rate: 97.27
    }
  }

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
          estimated_revenue: 0,
          estimated_cost: 0,
          estimated_margin: 0,
          active_contract_count: 3,
          stalled_contract_count: 1,
          active_coil_count: 10,
          yield_rate: 98.2,
          total_attendance: 33
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

  await page.route('**/api/v1/ai/conversations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 'conv-1',
            title: 'AI 工作台',
            created_at: '2026-04-23T08:00:00Z',
            updated_at: '2026-04-23T08:10:00Z'
          }
        ]
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
}
