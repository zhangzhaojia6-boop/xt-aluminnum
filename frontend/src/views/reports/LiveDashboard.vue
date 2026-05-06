<template>
  <ReferencePageFrame
    module-number="12"
    title="工厂实时态势"
    :tags="['全厂', '机列填报', '实时状态']"
    class="live-dashboard"
    data-testid="live-dashboard"
  >
    <template #actions>
      <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
      <div class="live-dashboard__connection">
        <span :class="['live-dashboard__connection-dot', `is-${connectionTone}`]"></span>
        <span>{{ connectionLabel }}</span>
      </div>
      <div class="live-dashboard__progress-pill">
        {{ commandSummary.dataSourceLabel }}
      </div>
      <el-button :icon="RefreshRight" @click="loadDashboardSurface()">刷新</el-button>
    </template>

    <section class="management-overview-strip">
      <article class="management-overview-card management-overview-card--primary">
        <span>今日产量</span>
        <strong>{{ formatWeight(managementOverview.outputWeight) }}</strong>
        <em>吨</em>
      </article>
      <article class="management-overview-card">
        <span>损耗重量</span>
        <strong>{{ formatWeight(managementOverview.lossWeight) }}</strong>
        <em>{{ managementOverview.lossRate == null ? '损耗率 --' : `损耗率 ${formatPercent(managementOverview.lossRate)}` }}</em>
      </article>
      <article class="management-overview-card">
        <span>成材率</span>
        <strong :class="yieldToneClass(managementOverview.yieldRate)">{{ formatPercent(managementOverview.yieldRate) }}</strong>
        <em>{{ commandSummary.dataSourceLabel }}</em>
      </article>
      <article class="management-overview-card" :class="marginToneClass" aria-label="毛利估算">
        <span>{{ managementOverview.marginLabel }}</span>
        <strong>{{ managementOverview.estimatedMargin == null ? '--' : `¥ ${formatWeight(managementOverview.estimatedMargin)}` }}</strong>
        <em>经营估算</em>
      </article>
      <article class="management-overview-card" :class="{ 'is-danger': managementOverview.blockerCount > 0 }">
        <span>风险项</span>
        <strong>{{ managementOverview.blockerCount }}</strong>
        <em>缺报 {{ managementOverview.blockerBreakdown.missingCells }} · 异常 {{ managementOverview.blockerBreakdown.anomalyCount }} · 交付 {{ managementOverview.blockerBreakdown.deliveryBlocker }} · 发布 {{ managementOverview.blockerBreakdown.pendingPublish }} · 关注 {{ managementOverview.blockerBreakdown.attentionCells }}</em>
      </article>
      <article class="management-overview-card" :class="{ 'is-success': externalReadinessReady, 'is-danger': externalHardIssueCount > 0 }">
        <span>外部联通闸门</span>
        <strong>{{ externalReadinessLabel }}</strong>
        <em>{{ externalIssueLabel }}</em>
      </article>
    </section>

    <section class="mes-connection-strip" aria-label="外部 MES">
      <div class="mes-connection-strip__status">
        <span :class="['mes-connection-strip__dot', `is-${mesConnectionTone}`]"></span>
        <div>
          <span>外部 MES</span>
          <strong>{{ mesConnectionLabel }}</strong>
        </div>
      </div>
      <div class="mes-connection-strip__meta">
        <span>{{ mesSourceLabel }}</span>
        <span>{{ mesActionLabel }}</span>
        <span v-if="mesRequiredEnvLabel" class="mes-connection-strip__required">{{ mesRequiredEnvLabel }}</span>
        <span>{{ mesLastSyncLabel }}</span>
      </div>
    </section>

    <section class="fill-intake-strip" :class="`is-${fillIntakeSummary.tone}`" aria-label="填报接入">
      <div class="fill-intake-strip__head">
        <strong>填报接入</strong>
        <span>{{ fillIntakeSummary.totalEntryCount }} 卷</span>
      </div>
      <div class="fill-intake-strip__meter" aria-hidden="true">
        <i class="is-formal" :style="{ width: `${fillIntakeSummary.formalRate}%` }"></i>
        <i class="is-draft" :style="{ width: `${fillIntakeSummary.draftRate}%` }"></i>
      </div>
      <div class="fill-intake-strip__stats">
        <span>
          <strong>{{ fillIntakeSummary.formalEntryCount }}</strong>
          <em>已进入正式</em>
        </span>
        <span>
          <strong>{{ fillIntakeSummary.draftEntryCount }}</strong>
          <em>草稿待提交</em>
        </span>
        <span>
          <strong>{{ fillIntakeSummary.missingCellCount }}</strong>
          <em>缺报班次</em>
        </span>
      </div>
    </section>

    <section v-if="workshopFillIntakeRows.length" class="fill-workshop-flow" aria-label="车间填报接入">
      <div class="fill-workshop-flow__head">
        <strong>车间填报接入</strong>
        <span>{{ workshopFillIntakeRows.length }} 个车间</span>
      </div>
      <div class="fill-workshop-flow__rows">
        <div
          v-for="row in workshopFillIntakeRows"
          :key="row.workshopName"
          class="fill-workshop-flow__row"
          :class="`is-${row.tone}`"
        >
          <div class="fill-workshop-flow__name">
            <strong>{{ row.workshopName }}</strong>
            <span>{{ row.totalEntryCount }} 卷</span>
          </div>
          <div class="fill-workshop-flow__meter" aria-hidden="true">
            <i class="is-formal" :style="{ width: `${row.formalRate}%` }"></i>
            <i class="is-draft" :style="{ width: `${row.draftRate}%` }"></i>
            <i class="is-missing" :style="{ width: `${row.missingRate}%` }"></i>
          </div>
          <div class="fill-workshop-flow__stats">
            <span><strong>{{ row.formalEntryCount }}</strong><em>正式</em></span>
            <span><strong>{{ row.draftEntryCount }}</strong><em>草稿</em></span>
            <span><strong>{{ row.missingCellCount }}</strong><em>缺报</em></span>
          </div>
        </div>
      </div>
    </section>

    <section v-if="pendingAssignmentSummary.entryCount" class="live-pending-assignment" :class="`is-${pendingAssignmentSummary.tone}`" aria-label="草稿待归属">
      <div class="live-pending-assignment__metric">
        <span>草稿待归属</span>
        <strong>{{ pendingAssignmentSummary.entryCount }}</strong>
        <em>卷未进机列</em>
      </div>
      <div class="live-pending-assignment__meta">
        <span>{{ formatWeight(pendingAssignmentSummary.output) }} 吨暂不入产量</span>
        <span>{{ pendingAssignmentSummary.workshopCount }} 个车间</span>
        <span>{{ pendingAssignmentSummary.missingMachineCount }} 缺机列</span>
      </div>
      <div class="live-pending-assignment__rows">
        <span
          v-for="row in pendingAssignmentSummary.rows"
          :key="`${row.workshopName}-${row.shiftName}`"
        >
          <strong>{{ row.workshopName }}</strong>
          <em>{{ row.shiftName }}</em>
          <b>{{ row.entryCount }} 卷</b>
        </span>
      </div>
    </section>

    <section v-if="unboundFillSummary.rowCount" class="live-unbound-fill" aria-label="未绑定填报归属">
      <div class="live-unbound-fill__metric">
        <span>未绑定填报归属</span>
        <strong>{{ formatWeight(unboundFillSummary.output) }}</strong>
        <em>吨待归属</em>
      </div>
      <div class="live-unbound-fill__meta">
        <span>{{ unboundFillSummary.workshopCount }} 个车间</span>
        <span>{{ unboundFillSummary.shiftCount }} 个班次</span>
        <span>{{ unboundFillSummary.rowCount }} 条机列</span>
      </div>
      <div class="live-unbound-fill__rows">
        <span
          v-for="row in unboundFillSummary.rows"
          :key="`${row.workshopName}-${row.machineName}-${row.shiftLabel}`"
        >
          <strong>{{ row.workshopName }}</strong>
          <em>{{ row.shiftLabel }}</em>
          <b>{{ formatWeight(row.output) }} 吨</b>
        </span>
      </div>
      <RouterLink v-if="authStore.isAdmin" class="live-unbound-fill__action" :to="unboundAccountRoute">
        <el-icon><Setting /></el-icon>
        <span>绑定账号</span>
      </RouterLink>
    </section>

    <section
      class="live-machine-ownership"
      :class="{ 'is-warning': machineOwnershipSummary.needsBinding }"
      aria-label="机列归属率"
    >
      <div class="live-machine-ownership__head">
        <strong>机列归属率</strong>
        <span>{{ machineOwnershipSummary.boundMachineCount }} 已归属 · {{ machineOwnershipSummary.unboundMachineCount }} 待归属</span>
      </div>
      <div class="live-machine-ownership__body">
        <div class="live-machine-ownership__meter" aria-hidden="true">
          <i class="is-bound" :style="{ width: `${machineOwnershipSummary.ownershipRate}%` }"></i>
          <i class="is-unbound" :style="{ width: `${machineOwnershipSummary.unboundRate}%` }"></i>
        </div>
        <div class="live-machine-ownership__stats">
          <span>
            <strong>{{ formatPercent(machineOwnershipSummary.ownershipRate) }}</strong>
            <em>已归属</em>
          </span>
          <span>
            <strong>{{ formatWeight(machineOwnershipSummary.unboundOutput) }}</strong>
            <em>吨待归属</em>
          </span>
          <span>
            <strong>{{ machineOwnershipSummary.machineCount }}</strong>
            <em>产出机列</em>
          </span>
        </div>
      </div>
    </section>

    <section class="live-output-distribution" aria-label="卷级直录分布">
      <div class="live-output-distribution__head">
        <strong>卷级直录分布</strong>
        <span>{{ outputDistributionSummary }}</span>
      </div>
      <div v-if="outputDistributionRows.length" class="live-output-distribution__rows">
        <article
          v-for="row in outputDistributionRows"
          :key="`${row.workshopName}-${row.machineId}`"
          class="live-output-row"
          :class="{ 'is-unbound': row.bindingLabel === '未绑定' }"
        >
          <div class="live-output-row__main">
            <strong>{{ row.machineName }}</strong>
            <span>{{ row.workshopName }} · {{ row.shiftLabel }}</span>
          </div>
          <div class="live-output-row__metric">
            <strong>{{ formatWeight(row.output) }}</strong>
            <span>吨</span>
          </div>
          <div class="live-output-row__bar" aria-hidden="true">
            <i :style="{ width: `${row.share}%` }"></i>
          </div>
          <span class="live-output-row__tag">{{ row.bindingLabel }}</span>
        </article>
      </div>
      <div v-else class="live-output-distribution__empty">暂无卷级直录</div>
    </section>

    <section class="live-shift-rhythm" aria-label="班次产量节奏">
      <div class="live-shift-rhythm__head">
        <strong>班次产量节奏</strong>
        <span>{{ shiftOutputRhythmSummary }}</span>
      </div>
      <div v-if="shiftOutputRhythmRows.length" class="live-shift-rhythm__rows">
        <div
          v-for="row in shiftOutputRhythmRows"
          :key="row.shiftName"
          class="live-shift-row"
        >
          <div class="live-shift-row__label">
            <strong>{{ row.shiftName }}</strong>
            <span>{{ row.machineCount }} 个机列</span>
          </div>
          <div class="live-shift-row__bar" aria-hidden="true">
            <i :style="{ transform: `scaleX(${row.share / 100})` }"></i>
          </div>
          <div class="live-shift-row__metric">
            <strong>{{ formatWeight(row.output) }}</strong>
            <span>{{ row.share }}%</span>
          </div>
        </div>
      </div>
      <div v-else class="live-shift-rhythm__empty">暂无班次产量</div>
    </section>

    <section class="management-flow" aria-label="经营链路">
      <div class="management-flow__head">
        <strong>经营链路</strong>
        <span>{{ targetDate }}</span>
      </div>
      <div class="management-flow__nodes">
        <div class="management-flow__node">
          <span>投入</span>
          <strong>{{ formatWeight(managementOverview.inputWeight) }}</strong>
        </div>
        <div class="management-flow__node">
          <span>生产</span>
          <strong>{{ formatWeight(managementOverview.outputWeight) }}</strong>
        </div>
        <div class="management-flow__node">
          <span>损耗</span>
          <strong>{{ formatWeight(managementOverview.lossWeight) }}</strong>
        </div>
        <div class="management-flow__node">
          <span>入库/发货</span>
          <strong>成品 {{ formatWeight(managementOverview.storageFinishedWeight) }} / 发货 {{ formatWeight(managementOverview.shipmentWeight) }}</strong>
        </div>
        <div class="management-flow__node">
          <span>成本/毛利</span>
          <strong>{{ managementOverview.estimatedMargin == null ? '待配置' : managementOverview.marginLabel }}</strong>
        </div>
        <div class="management-flow__node">
          <span>日报交付</span>
          <strong>{{ managementOverview.deliveryReady ? '可交付' : '待补齐' }}</strong>
        </div>
      </div>
    </section>

    <div class="live-dashboard__section-title">
      <strong>机列填报明细</strong>
      <span>{{ commandSummary.submittedCells }}/{{ commandSummary.totalCells }} 班次</span>
    </div>

    <div class="live-dashboard__workshops" v-loading="loading">
      <el-empty
        v-if="!loading && !sortedWorkshops.length"
        description="当前日期暂无实时卷数据"
      />

      <el-collapse v-else v-model="activePanels" class="live-dashboard__collapse">
        <el-collapse-item
          v-for="workshop in sortedWorkshops"
          :key="workshop.workshop_id"
          :name="String(workshop.workshop_id)"
          class="live-dashboard__collapse-item"
        >
          <template #title>
            <div class="live-workshop__title">
              <div>
                <strong>{{ workshop.workshop_name }}</strong>
                <span>{{ workshop.machines.length }} 台机台</span>
              </div>
              <div class="live-workshop__title-meta">
                <span>投 {{ formatWeight(workshop.workshop_total?.input) }}</span>
                <span>产 {{ formatWeight(workshop.workshop_total?.output) }}</span>
                <span>正式率 {{ formatPercent(workshop.workshop_total?.yield_rate) }}</span>
              </div>
            </div>
          </template>

          <div class="live-workshop__board" v-if="workshop.machines.length">
            <div class="live-board__scroller">
              <div class="live-board__table" :style="boardGridStyle(workshop)">
                <div class="live-board__row live-board__row--head live-board__row--grid">
                  <div class="live-board__stub">机台</div>
                  <div
                    v-for="shift in getWorkshopShifts(workshop)"
                    :key="`head-${workshop.workshop_id}-${shift.shift_id}`"
                    class="live-board__head-cell"
                  >
                    {{ shift.shift_name }}
                  </div>
                  <div class="live-board__head-cell live-board__head-cell--total">日合计</div>
                </div>

                <div
                  v-for="machine in workshop.machines"
                  :key="machine.machine_id"
                  class="live-board__row live-board__row--grid"
                >
                  <div class="live-board__stub live-board__stub--machine">{{ machine.machine_name }}</div>
                  <button
                    v-for="shift in machine.shifts"
                    :key="cellKey(workshop.workshop_id, machine.machine_id, shift.shift_id)"
                    type="button"
                    :class="[
                      'live-cell',
                      `is-${shift.submission_status}`,
                      `tone-${statusToneForCell(shift)}`,
                      { 'is-disabled': !shift.is_applicable },
                      { 'is-updated': isUpdated(cellKey(workshop.workshop_id, machine.machine_id, shift.shift_id)) }
                    ]"
                    :disabled="!shift.is_applicable"
                    @click="openDrawer(workshop, machine, shift)"
                  >
                    <span class="live-cell__symbol">{{ submissionSymbol(shift.submission_status) }}</span>
                    <strong>{{ statusTextForCell(shift) }}</strong>
                    <span class="live-cell__count">{{ shift.is_applicable ? `${shift.submitted_count} 卷` : '—' }}</span>
                    <span :class="['live-cell__yield', yieldToneClass(shift.yield_rate)]">
                      {{ shift.is_applicable ? `兼容率 ${formatPercent(shift.yield_rate)}` : '—' }}
                    </span>
                  </button>
                  <div class="live-board__total-cell">
                    <strong>投 {{ formatWeight(machine.day_total?.input) }}</strong>
                    <span>产 {{ formatWeight(machine.day_total?.output) }}</span>
                    <span>废 {{ formatWeight(machine.day_total?.scrap) }}</span>
                    <span>兼容率 {{ formatPercent(machine.day_total?.yield_rate) }}</span>
                  </div>
                </div>

                <div class="live-board__row live-board__row--grid live-board__row--attendance">
                  <div class="live-board__stub">考勤</div>
                  <div
                    v-for="shift in getAttendanceShifts(workshop)"
                    :key="attendanceKey(workshop.workshop_id, shift.shift_id)"
                    :class="[
                      'live-attendance-cell',
                      { 'is-disabled': !shift.is_applicable },
                      {
                        'is-updated': isUpdated(attendanceKey(workshop.workshop_id, shift.shift_id))
                      }
                    ]"
                  >
                    {{ formatAttendance(shift) }}
                  </div>
                  <div class="live-board__total-cell live-board__total-cell--muted">
                    自动同步考勤确认状态
                  </div>
                </div>

                <div class="live-board__row live-board__row--grid live-board__row--summary">
                  <div class="live-board__stub">合计</div>
                  <div
                    v-for="shiftTotal in getWorkshopShiftTotals(workshop)"
                    :key="`summary-${workshop.workshop_id}-${shiftTotal.shift_id}`"
                    :class="['live-summary-cell', { 'is-disabled': !shiftTotal.is_applicable }]"
                  >
                    <strong>{{ shiftTotal.is_applicable ? formatWeight(shiftTotal.total_output) : '—' }}</strong>
                    <span>{{ shiftTotal.is_applicable ? `投 ${formatWeight(shiftTotal.total_input)}` : '不适用' }}</span>
                    <span>{{ shiftTotal.is_applicable ? `兼容率 ${formatPercent(shiftTotal.yield_rate)}` : '—' }}</span>
                  </div>
                  <div class="live-board__total-cell live-board__total-cell--accent">
                    <strong>投 {{ formatWeight(workshop.workshop_total?.input) }}</strong>
                    <span>产 {{ formatWeight(workshop.workshop_total?.output) }}</span>
                    <span>废 {{ formatWeight(workshop.workshop_total?.scrap) }}</span>
                    <span>正式率 {{ formatPercent(workshop.workshop_total?.yield_rate) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <el-card class="panel live-dashboard__bottom">
      <template #header>
        <div class="live-dashboard__table-header">
          <div>
            <strong>全厂日汇总</strong>
          </div>
          <el-button
            class="live-dashboard__export-button"
            type="primary"
            :icon="Download"
            circle
            aria-label="导出电子表格"
            title="导出电子表格"
            @click="exportSummary"
          />
        </div>
      </template>

      <el-table :data="factorySummaryRows" stripe>
        <el-table-column prop="workshop_name" label="车间" min-width="180" />
        <el-table-column prop="machine_count" label="机台数" width="100" />
        <el-table-column prop="submission_progress" label="提交进度" min-width="120" />
        <el-table-column label="投入" min-width="120">
          <template #default="{ row }">{{ formatWeight(row.input) }}</template>
        </el-table-column>
        <el-table-column label="产出" min-width="120">
          <template #default="{ row }">{{ formatWeight(row.output) }}</template>
        </el-table-column>
        <el-table-column label="废料" min-width="120">
          <template #default="{ row }">{{ formatWeight(row.scrap) }}</template>
        </el-table-column>
        <el-table-column label="正式成材率" min-width="120">
          <template #default="{ row }">
            <span :class="yieldToneClass(row.yield_rate)">{{ formatPercent(row.yield_rate) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" size="560px" :title="drawerTitle">
      <div class="live-drawer__meta" v-if="activeCell">
        <span>{{ activeCell.workshop_name }}</span>
        <span>{{ activeCell.machine_name }}</span>
        <span>{{ activeCell.shift_name }}</span>
        <span>{{ targetDate }}</span>
      </div>

      <el-skeleton v-if="drawerLoading" :rows="8" animated />
      <el-empty v-else-if="!drawerData.items.length" description="当前机台班次暂无卷数据" />
      <el-table v-else :data="drawerData.items" stripe>
        <el-table-column prop="tracking_card_no" label="随行卡号" min-width="150" />
        <el-table-column prop="entry_status" label="状态" width="100">
          <template #default="{ row }">{{ formatEntryStatus(row.entry_status) }}</template>
        </el-table-column>
        <el-table-column prop="entry_type" label="节奏" width="110">
          <template #default="{ row }">{{ formatEntryType(row.entry_type) }}</template>
        </el-table-column>
        <el-table-column label="投入" min-width="110">
          <template #default="{ row }">{{ formatWeight(row.input_weight) }}</template>
        </el-table-column>
        <el-table-column label="产出" min-width="110">
          <template #default="{ row }">{{ formatWeight(row.output_weight) }}</template>
        </el-table-column>
        <el-table-column label="废料" min-width="110">
          <template #default="{ row }">{{ formatWeight(row.scrap_weight) }}</template>
        </el-table-column>
        <el-table-column label="兼容成材率" min-width="110">
          <template #default="{ row }">
            <span :class="yieldToneClass(row.yield_rate)">{{ formatPercent(row.yield_rate) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </ReferencePageFrame>
</template>

<script setup>
import { Download, RefreshRight, Setting } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { fetchDeliveryStatus, fetchExternalReadiness, fetchFactoryDashboard } from '../../api/dashboard'
import { fetchMesSyncStatus } from '../../api/mes'
import { fetchLiveAggregation, fetchLiveCellDetail } from '../../api/realtime'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { useRealtimeStream } from '../../composables/useRealtimeStream'
import { useAuthStore } from '../../stores/auth'
import {
  numberValue, formatWeight, formatPercent, yieldToneClass,
  submissionSymbol, formatAttendance, formatEntryStatus, formatEntryType
} from '../../utils/liveDashboardFormatters'
import {
  buildMachineOwnershipSummary,
  buildOutputDistribution,
  buildFillIntakeSummary,
  buildPendingAssignmentSummary,
  buildShiftOutputRhythm,
  buildUnboundFillSummary,
  buildWorkshopFillIntakeRows,
  buildCommandCenterSummary,
  sortWorkshopsForCommandCenter,
  statusTextForCell,
  statusToneForCell
} from '../../utils/managementCommandCenter'
import { buildManagementOverview, marginTone } from '../../utils/managementOverview'

const authStore = useAuthStore()
const route = useRoute()

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const activePanels = ref([])
const activeCell = ref(null)
const aggregation = ref(createEmptyAggregation(targetDate.value))
const factorySnapshot = ref({})
const deliverySnapshot = ref({})
const mesSyncStatus = ref({})
const externalReadiness = ref({})
const drawerData = ref({ items: [] })
const updatedKeys = ref({})
const lastLoadedAt = ref('')

let reloadTimer = null
const handledEventIds = new Set()

function createEmptyAggregation(businessDate) {
  return {
    business_date: businessDate,
    overall_progress: {
      submitted_cells: 0,
      total_cells: 0
    },
    workshops: [],
    yield_matrix_lane: {},
    mes_sync_status: {},
    data_source: 'work_order_runtime',
    factory_total: {
      input: 0,
      output: 0,
      scrap: 0,
      yield_rate: null
    }
  }
}

function createSummaryRow(workshop) {
  return {
    workshop_name: workshop.workshop_name,
    machine_count: workshop.machines.length,
    submission_progress: buildWorkshopProgress(workshop),
    input: workshop.workshop_total?.input ?? 0,
    output: workshop.workshop_total?.output ?? 0,
    scrap: workshop.workshop_total?.scrap ?? 0,
    yield_rate: workshop.workshop_total?.yield_rate ?? null
  }
}

function buildWorkshopProgress(workshop) {
  let submitted = 0
  let total = 0
  workshop.machines.forEach((machine) => {
    machine.shifts.forEach((shift) => {
      if (!shift.is_applicable) return
      total += 1
      if (numberValue(shift.submitted_count) > 0) {
        submitted += 1
      }
    })
  })
  return `${submitted}/${total}`
}

const factorySummaryRows = computed(() => {
  const rows = sortedWorkshops.value.map(createSummaryRow)
  rows.push({
    workshop_name: '全厂汇总',
    machine_count: rows.reduce((sum, item) => sum + numberValue(item.machine_count), 0),
    submission_progress: overallProgressText.value,
    input: aggregation.value.factory_total?.input ?? 0,
    output: aggregation.value.factory_total?.output ?? 0,
    scrap: aggregation.value.factory_total?.scrap ?? 0,
    yield_rate: aggregation.value.factory_total?.yield_rate ?? null
  })
  return rows
})

const overallProgressText = computed(() => {
  const submitted = aggregation.value.overall_progress?.submitted_cells ?? 0
  const total = aggregation.value.overall_progress?.total_cells ?? 0
  return `${submitted}/${total} 班次`
})
const commandSummary = computed(() => buildCommandCenterSummary(aggregation.value))
const managementOverview = computed(() => buildManagementOverview({
  aggregation: aggregation.value,
  dashboard: factorySnapshot.value,
  delivery: deliverySnapshot.value
}))
const externalHardIssues = computed(() => {
  const hardIssues = externalReadiness.value.hard_issues || externalReadiness.value.hardIssues || []
  return Array.isArray(hardIssues) ? hardIssues : []
})
const externalHardIssueCount = computed(() => externalHardIssues.value.length)
const externalReadinessLoaded = computed(() => Object.keys(externalReadiness.value || {}).length > 0)
const externalReadinessReady = computed(() => (
  externalReadinessLoaded.value &&
  (externalReadiness.value.hard_gate_passed === true || externalReadiness.value.hardGatePassed === true)
))
const externalReadinessLabel = computed(() => {
  if (!externalReadinessLoaded.value) return '待核对'
  return externalReadinessReady.value ? '已通过' : `${externalHardIssueCount.value} 项阻塞`
})
const externalIssueLabel = computed(() => {
  if (!externalReadinessLoaded.value) return '接口待返回'
  if (!externalHardIssues.value.length) return '外部链路就绪'
  return externalHardIssues.value.slice(0, 3).map((item) => item.code).filter(Boolean).join(' / ')
})
const marginToneClass = computed(() => `is-${marginTone(managementOverview.value.estimatedMargin)}`)
const sortedWorkshops = computed(() => sortWorkshopsForCommandCenter(aggregation.value.workshops || []))
const outputDistributionRows = computed(() => buildOutputDistribution(sortedWorkshops.value, 5))
const fillIntakeSummary = computed(() => buildFillIntakeSummary(aggregation.value))
const pendingAssignmentSummary = computed(() => buildPendingAssignmentSummary(aggregation.value, 3))
const workshopFillIntakeRows = computed(() => buildWorkshopFillIntakeRows(sortedWorkshops.value, 6))
const outputDistributionSummary = computed(() => {
  if (!outputDistributionRows.value.length) return '暂无产量'
  const total = outputDistributionRows.value.reduce((sum, row) => sum + numberValue(row.output), 0)
  return `${outputDistributionRows.value.length} 个机列 · ${formatWeight(total)} 吨`
})
const unboundFillSummary = computed(() => buildUnboundFillSummary(sortedWorkshops.value, 3))
const machineOwnershipSummary = computed(() => buildMachineOwnershipSummary(sortedWorkshops.value))
const unboundAccountRoute = computed(() => {
  const query = { machine_binding: 'unbound' }
  if (route.query.desktop === '1') query.desktop = '1'
  return { path: '/manage/admin/users', query }
})
const shiftOutputRhythmRows = computed(() => buildShiftOutputRhythm(sortedWorkshops.value))
const shiftOutputRhythmSummary = computed(() => {
  if (!shiftOutputRhythmRows.value.length) return '暂无产量'
  const total = shiftOutputRhythmRows.value.reduce((sum, row) => sum + numberValue(row.output), 0)
  return `${shiftOutputRhythmRows.value.length} 个班次 · ${formatWeight(total)} 吨`
})
const lastRefreshLabel = computed(() => (lastLoadedAt.value ? dayjs(lastLoadedAt.value).format('HH:mm:ss') : '--'))
const mesConnectionTone = computed(() => {
  const status = String(mesSyncStatus.value.status || '').toLowerCase()
  if (status === 'fresh' || status === 'success') return 'good'
  if (status === 'unconfigured' || mesSyncStatus.value.action_required === 'configure_mes') return 'warn'
  if (status === 'idle' || status === 'migration_missing') return 'warn'
  if (status === 'stale' || status === 'failed') return 'danger'
  return 'muted'
})
const mesConnectionLabel = computed(() => {
  const status = String(mesSyncStatus.value.status || '').toLowerCase()
  if (status === 'fresh' || status === 'success') return '同步正常'
  if (status === 'unconfigured' || mesSyncStatus.value.action_required === 'configure_mes') return '未配置'
  if (status === 'migration_missing') return '待迁移'
  if (status === 'stale') return '同步滞后'
  if (status === 'failed') return '供应商异常'
  return '待同步'
})
const mesSourceLabel = computed(() => {
  const source = String(mesSyncStatus.value.source || '').toLowerCase()
  if (source === 'mes_projection') return 'MES 投影'
  if (source === 'local_entry') return '本地填报'
  return '数据源待确认'
})
const mesActionLabel = computed(() => {
  const action = String(mesSyncStatus.value.action_required || '').toLowerCase()
  if (action === 'configure_mes') return '需配置 MES_MVC_BASE_URL / MES_MVC_USERNAME / MES_MVC_PASSWORD'
  if (action === 'run_migration') return '需执行投影迁移'
  if (action === 'check_vendor') return '需核对供应商接口'
  if (action === 'check_credentials') return '需核对账号'
  return '无需处理'
})
const mesRequiredEnvList = computed(() => {
  const requiredEnv = mesSyncStatus.value.required_env || mesSyncStatus.value.requiredEnv || []
  if (!Array.isArray(requiredEnv)) return []
  return requiredEnv.filter(Boolean)
})
const mesRequiredEnvLabel = computed(() => {
  if (!mesRequiredEnvList.value.length) return ''
  const visibleFields = mesRequiredEnvList.value.slice(0, 4).join(' / ')
  return mesRequiredEnvList.value.length > 4 ? `缺少配置 ${visibleFields} 等` : `缺少配置 ${visibleFields}`
})
const mesLastSyncLabel = computed(() => {
  if (mesSyncStatus.value.last_synced_at) {
    return `同步 ${dayjs(mesSyncStatus.value.last_synced_at).format('MM-DD HH:mm')}`
  }
  return '尚无同步时间'
})

const streamScope = computed(() => {
  if (authStore.isAdmin || authStore.isManager || authStore.role === 'statistician' || authStore.role === 'stat') {
    return 'all'
  }
  return authStore.user?.workshop_id ? String(authStore.user.workshop_id) : 'all'
})

const { status: streamStatus } = useRealtimeStream(streamScope, {
  enabled: true,
  onEvent: handleRealtimeEvent
})

const connectionTone = computed(() => {
  if (streamStatus.value === 'open') return 'good'
  if (streamStatus.value === 'connecting' || streamStatus.value === 'reconnecting') return 'warn'
  if (streamStatus.value === 'closed') return 'muted'
  return 'danger'
})

const connectionLabel = computed(() => {
  if (streamStatus.value === 'open') return '实时连接正常'
  if (streamStatus.value === 'connecting') return '正在建立连接'
  if (streamStatus.value === 'reconnecting') return '正在重连'
  if (streamStatus.value === 'closed') return '连接已关闭'
  return '连接异常'
})

const drawerTitle = computed(() => {
  if (!activeCell.value) return '批次详情'
  return `${activeCell.value.machine_name} ${activeCell.value.shift_name} 批次详情`
})

function boardGridStyle(workshop) {
  const shiftCount = Math.max(getWorkshopShifts(workshop).length, 1)
  return {
    gridTemplateColumns: `116px repeat(${shiftCount}, minmax(150px, 1fr)) minmax(220px, 260px)`
  }
}

function getWorkshopShifts(workshop) {
  return workshop?.machines?.[0]?.shifts || []
}

function getAttendanceShifts(workshop) {
  return getWorkshopShifts(workshop)
}

function getWorkshopShiftTotals(workshop) {
  return workshop?.shift_totals || []
}

function cellKey(workshopId, machineId, shiftId) {
  return `${workshopId}-${machineId}-${shiftId}`
}

function attendanceKey(workshopId, shiftId) {
  return `attendance-${workshopId}-${shiftId}`
}

function isUpdated(key) {
  return Boolean(updatedKeys.value[key])
}

function markUpdated(key) {
  updatedKeys.value = {
    ...updatedKeys.value,
    [key]: Date.now()
  }
  window.setTimeout(() => {
    const next = { ...updatedKeys.value }
    delete next[key]
    updatedKeys.value = next
  }, 1800)
}

function clearHandledEvents() {
  if (handledEventIds.size < 500) return
  handledEventIds.clear()
}

async function loadAggregation({ silent = false } = {}) {
  if (!silent) {
    loading.value = true
  }

  try {
    const liveData = await fetchLiveAggregation({
      business_date: targetDate.value,
      workshop_id: streamScope.value === 'all' ? undefined : Number(streamScope.value)
    })
    const [factoryResult, deliveryResult, mesResult, externalResult] = await Promise.allSettled([
      fetchFactoryDashboard({ target_date: targetDate.value }),
      fetchDeliveryStatus({ target_date: targetDate.value }),
      fetchMesSyncStatus(),
      fetchExternalReadiness()
    ])
    aggregation.value = liveData
    factorySnapshot.value = factoryResult.status === 'fulfilled' ? factoryResult.value : {}
    deliverySnapshot.value = deliveryResult.status === 'fulfilled' ? deliveryResult.value : {}
    mesSyncStatus.value = mesResult.status === 'fulfilled' ? mesResult.value : {}
    externalReadiness.value = externalResult.status === 'fulfilled' ? externalResult.value : {}
    lastLoadedAt.value = new Date().toISOString()
    activePanels.value = sortWorkshopsForCommandCenter(liveData.workshops || []).map((item) => String(item.workshop_id))
    if (drawerVisible.value && activeCell.value) {
      await loadDrawer(activeCell.value, { preserveOpen: true })
    }
  } finally {
    loading.value = false
  }
}

async function loadDashboardSurface() {
  await loadAggregation()
}

function scheduleReload() {
  if (reloadTimer) return
  reloadTimer = window.setTimeout(async () => {
    reloadTimer = null
    await loadAggregation({ silent: true })
  }, 400)
}

function findCell(payload) {
  const workshop = aggregation.value.workshops.find((item) => item.workshop_id === payload.workshop_id)
  if (!workshop) return null
  const machine = workshop.machines.find((item) => item.machine_id === payload.machine_id)
  if (!machine) return null
  const shift = machine.shifts.find((item) => item.shift_id === payload.shift_id)
  if (!shift) return null
  return { workshop, machine, shift }
}

function syncDrawerWithSubmission(payload) {
  if (!drawerVisible.value || !activeCell.value) return
  if (
    activeCell.value.workshop_id !== payload.workshop_id ||
    activeCell.value.machine_id !== payload.machine_id ||
    activeCell.value.shift_id !== payload.shift_id
  ) {
    return
  }

  drawerData.value.items = [
    {
      tracking_card_no: payload.tracking_card_no,
      entry_id: payload.entry_id,
      work_order_id: payload.work_order_id,
      entry_status: payload.entry_status,
      entry_type: payload.entry_type,
      input_weight: payload.input_weight,
      output_weight: payload.output_weight,
      scrap_weight: payload.scrap_weight,
      yield_rate: payload.yield_rate,
      machine_id: payload.machine_id,
      shift_id: payload.shift_id
    },
    ...drawerData.value.items.filter((item) => item.entry_id !== payload.entry_id)
  ]
}

function syncDrawerWithVerification(payload) {
  if (!drawerVisible.value) return
  const match = drawerData.value.items.find((item) => item.entry_id === payload.entry_id)
  if (!match) return
  match.entry_status = payload.entry_status || match.entry_status
  match.input_weight = payload.input_weight ?? match.input_weight
  match.output_weight = payload.output_weight ?? match.output_weight
  match.scrap_weight = payload.scrap_weight ?? match.scrap_weight
  match.yield_rate = payload.yield_rate ?? match.yield_rate
}

function applyEntrySubmitted(payload) {
  if (payload.business_date && payload.business_date !== targetDate.value) return
  const match = findCell(payload)
  if (!match) {
    scheduleReload()
    return
  }

  syncDrawerWithSubmission(payload)
  markUpdated(cellKey(payload.workshop_id, payload.machine_id, payload.shift_id))
  scheduleReload()
}

function applyAttendanceConfirmed(payload) {
  if (payload.business_date && payload.business_date !== targetDate.value) return
  const workshop = aggregation.value.workshops.find((item) => item.workshop_id === payload.workshop_id)
  if (!workshop) {
    scheduleReload()
    return
  }

  workshop.machines.forEach((machine) => {
    const shift = machine.shifts.find((item) => item.shift_id === payload.shift_id)
    if (!shift) return
    shift.attendance_exception_count = numberValue(payload.exception_count)
    shift.attendance_status = numberValue(payload.exception_count) > 0 ? 'pending' : 'confirmed'
    delete shift.status_tone
    delete shift.status_text
    shift.status_tone = statusToneForCell(shift)
    shift.status_text = statusTextForCell(shift)
  })
  markUpdated(attendanceKey(payload.workshop_id, payload.shift_id))
}

function handleRealtimeEvent(type, payload, meta = {}) {
  if (meta.eventId && handledEventIds.has(meta.eventId)) {
    return
  }
  if (meta.eventId) {
    handledEventIds.add(meta.eventId)
    clearHandledEvents()
  }

  if (type === 'entry_submitted') {
    applyEntrySubmitted(payload)
    return
  }
  if (type === 'entry_verified') {
    syncDrawerWithVerification(payload)
    if (payload.workshop_id && payload.machine_id && payload.shift_id) {
      markUpdated(cellKey(payload.workshop_id, payload.machine_id, payload.shift_id))
    }
    scheduleReload()
    return
  }
  if (type === 'attendance_confirmed') {
    applyAttendanceConfirmed(payload)
  }
}

async function loadDrawer(cell, options = {}) {
  const preserveOpen = options.preserveOpen === true
  activeCell.value = cell
  drawerLoading.value = true
  if (!preserveOpen) {
    drawerVisible.value = true
  }

  try {
    drawerData.value = await fetchLiveCellDetail({
      business_date: targetDate.value,
      workshop_id: cell.workshop_id,
      machine_id: cell.machine_id,
      shift_id: cell.shift_id
    })
  } finally {
    drawerLoading.value = false
  }
}

async function openDrawer(workshop, machine, shift) {
  await loadDrawer({
    workshop_id: workshop.workshop_id,
    workshop_name: workshop.workshop_name,
    machine_id: machine.machine_id,
    machine_name: machine.machine_name,
    shift_id: shift.shift_id,
    shift_name: shift.shift_name
  })
}

function exportSummary() {
  const header = ['车间', '机台数', '提交进度', '投入', '产出', '废料', '成材率']
  const rows = factorySummaryRows.value.map((item) => [
    item.workshop_name,
    item.machine_count,
    item.submission_progress,
    formatWeight(item.input),
    formatWeight(item.output),
    formatWeight(item.scrap),
    formatPercent(item.yield_rate)
  ])

  const csv = [header, ...rows]
    .map((row) =>
      row
        .map((cell) => {
          const text = String(cell ?? '')
          return `"${text.replaceAll('"', '""')}"`
        })
        .join(',')
    )
    .join('\n')

  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `live-dashboard-${targetDate.value}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

watch(targetDate, async () => {
  drawerVisible.value = false
  activeCell.value = null
  drawerData.value = { items: [] }
  await loadDashboardSurface()
})

onMounted(async () => {
  await loadDashboardSurface()
})

onBeforeUnmount(() => {
  if (reloadTimer) {
    window.clearTimeout(reloadTimer)
    reloadTimer = null
  }
})
</script>

<style scoped>
.live-dashboard {
  --command-blue: oklch(56% 0.22 260);
  --command-blue-deep: oklch(42% 0.19 260);
  --command-blue-soft: oklch(96% 0.025 254);
  --command-cyan: oklch(66% 0.14 215);
  --command-ink: oklch(17% 0.025 252);
  --command-rail: oklch(23% 0.028 252);
  --command-panel: rgba(255, 255, 255, 0.92);
  --command-line: rgba(43, 93, 178, 0.13);
  --command-metal: oklch(98% 0.008 248);
  --command-green: oklch(53% 0.13 158);
  --command-amber: oklch(62% 0.12 75);
  --command-red: oklch(55% 0.15 28);
  --command-radius: 8px;
  --command-radius-sm: 6px;
}

.live-dashboard :deep(.reference-page) {
  border: 1px solid rgba(43, 93, 178, 0.08);
  background:
    linear-gradient(180deg, rgba(239, 246, 255, 0.78), rgba(255, 255, 255, 0.88) 34%, rgba(245, 248, 253, 0.98));
}

.live-dashboard :deep(.reference-page__header) {
  align-items: stretch;
  padding: 16px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: var(--command-panel);
  box-shadow: 0 18px 46px rgba(25, 62, 118, 0.08);
}

.live-dashboard :deep(.reference-page__title-group) {
  align-content: center;
}

.live-dashboard :deep(.reference-page__number) {
  border-color: transparent;
  background: var(--command-blue);
  color: #fff;
  box-shadow: 0 10px 24px rgba(11, 99, 246, 0.18);
}

.live-dashboard :deep(.reference-page__system) {
  color: var(--command-blue);
  font-weight: 850;
}

.live-dashboard :deep(.reference-page h1) {
  color: var(--command-ink);
  letter-spacing: 0;
}

.live-dashboard :deep(.reference-page__tags span) {
  border-color: rgba(11, 99, 246, 0.14);
  background: var(--command-blue-soft);
  color: var(--command-blue-deep);
}

.live-dashboard :deep(.reference-page__actions) {
  align-items: center;
  gap: 10px;
}

.live-dashboard :deep(.reference-page__body) {
  min-width: 0;
}

.live-dashboard :deep(.reference-page__actions .el-date-editor) {
  width: 146px;
}

.live-dashboard :deep(.reference-page__actions .el-input__wrapper) {
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: #fff;
  box-shadow: none;
}

.live-dashboard :deep(.reference-page__actions .el-button) {
  min-height: 36px;
  border-radius: var(--command-radius-sm);
  font-weight: 800;
}

.live-dashboard__connection,
.live-dashboard__progress-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: #fff;
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 800;
  box-shadow: none;
}

.live-dashboard__progress-pill {
  border-color: rgba(11, 99, 246, 0.18);
  background: var(--command-blue-soft);
  color: var(--command-blue-deep);
}

.live-dashboard__connection-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-text-muted);
  box-shadow: 0 0 0 4px rgba(148, 163, 184, 0.16);
}

.live-dashboard__connection-dot.is-good {
  background: var(--command-green);
  box-shadow: 0 0 0 4px rgba(22, 138, 85, 0.13);
}

.live-dashboard__connection-dot.is-warn {
  background: var(--command-amber);
  box-shadow: 0 0 0 4px rgba(183, 121, 31, 0.14);
}

.live-dashboard__connection-dot.is-danger {
  background: var(--command-red);
  box-shadow: 0 0 0 4px rgba(194, 65, 52, 0.13);
}

.management-overview-strip {
  display: grid;
  grid-template-columns: minmax(220px, 1.25fr) repeat(5, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.management-overview-card {
  display: grid;
  align-content: space-between;
  min-height: 112px;
  padding: 15px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: var(--command-panel);
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.07);
}

.management-overview-card--primary {
  border-color: transparent;
  background: linear-gradient(135deg, rgba(9, 96, 238, 0.98), rgba(15, 142, 234, 0.96));
  color: #fff;
}

.management-overview-card span,
.management-flow__node span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.management-overview-card strong {
  color: var(--command-ink);
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  line-height: 1;
}

.management-overview-card--primary span,
.management-overview-card--primary strong,
.management-overview-card--primary em {
  color: rgba(255, 255, 255, 0.92);
}

.management-overview-card em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.management-overview-card.is-success {
  border-color: rgba(22, 138, 85, 0.24);
}

.management-overview-card.is-danger {
  border-color: rgba(194, 65, 52, 0.24);
}

.management-overview-card.is-muted {
  background: var(--xt-bg-panel-muted);
}

.management-flow {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: #fff;
}

.mes-connection-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 13px 14px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: #fff;
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.06);
}

.mes-connection-strip__status,
.mes-connection-strip__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.mes-connection-strip__status > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.mes-connection-strip__status span,
.mes-connection-strip__meta span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.mes-connection-strip__status strong {
  color: var(--command-ink);
  font-size: 17px;
  font-weight: 900;
}

.mes-connection-strip__meta {
  justify-content: flex-end;
  flex-wrap: wrap;
}

.mes-connection-strip__meta span {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  padding: 0 9px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: var(--command-blue-soft);
  color: var(--command-blue-deep);
}

.mes-connection-strip__meta .mes-connection-strip__required {
  border-color: rgba(183, 121, 31, 0.28);
  background: var(--xt-warning-light);
  color: var(--command-amber);
}

.mes-connection-strip__dot {
  width: 10px;
  height: 10px;
  flex: 0 0 auto;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-text-muted);
  box-shadow: 0 0 0 5px rgba(148, 163, 184, 0.14);
}

.mes-connection-strip__dot.is-good {
  background: var(--command-green);
  box-shadow: 0 0 0 5px rgba(22, 138, 85, 0.12);
}

.mes-connection-strip__dot.is-warn {
  background: var(--command-amber);
  box-shadow: 0 0 0 5px rgba(183, 121, 31, 0.13);
}

.mes-connection-strip__dot.is-danger {
  background: var(--command-red);
  box-shadow: 0 0 0 5px rgba(194, 65, 52, 0.12);
}

.fill-intake-strip {
  display: grid;
  grid-template-columns: minmax(170px, 0.46fr) 1fr minmax(300px, 0.78fr);
  gap: 14px;
  align-items: center;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid rgba(39, 88, 146, 0.15);
  border-radius: var(--command-radius);
  background:
    linear-gradient(180deg, rgba(230, 244, 255, 0.72), rgba(255, 255, 255, 0.96)),
    #fff;
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.06);
}

.fill-intake-strip.is-warning {
  border-color: rgba(183, 121, 31, 0.26);
}

.fill-intake-strip.is-danger {
  border-color: rgba(194, 65, 52, 0.24);
}

.fill-intake-strip__head {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.fill-intake-strip__head strong {
  color: var(--command-ink);
  font-size: 14px;
  font-weight: 900;
}

.fill-intake-strip__head span {
  color: var(--xt-text-secondary);
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.fill-intake-strip__meter {
  display: flex;
  width: 100%;
  height: 12px;
  overflow: hidden;
  border-radius: var(--xt-radius-pill);
  background: rgba(39, 88, 146, 0.1);
}

.fill-intake-strip__meter i {
  display: block;
  width: 0;
  min-width: 0;
  height: 100%;
  transition: width 260ms ease;
}

.fill-intake-strip__meter .is-formal {
  background: linear-gradient(90deg, var(--command-green), var(--command-cyan));
}

.fill-intake-strip__meter .is-draft {
  background: linear-gradient(90deg, var(--command-amber), var(--command-red));
}

.fill-intake-strip__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.fill-intake-strip__stats span {
  min-width: 0;
  min-height: 50px;
  display: grid;
  align-content: center;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid rgba(39, 88, 146, 0.12);
  border-radius: var(--command-radius-sm);
  background: rgba(255, 255, 255, 0.74);
}

.fill-intake-strip__stats strong {
  overflow: hidden;
  color: var(--command-blue-deep);
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fill-intake-strip__stats em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.fill-intake-strip.is-warning .fill-intake-strip__stats span:nth-child(2) strong {
  color: var(--command-amber);
}

.fill-intake-strip.is-danger .fill-intake-strip__stats span:nth-child(3) strong {
  color: var(--command-red);
}

.fill-workshop-flow {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
  padding: 13px 14px;
  border: 1px solid rgba(39, 88, 146, 0.14);
  border-radius: var(--command-radius);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 14px 30px rgba(25, 62, 118, 0.05);
}

.fill-workshop-flow__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.fill-workshop-flow__head strong {
  color: var(--command-ink);
  font-size: 14px;
  font-weight: 900;
}

.fill-workshop-flow__head span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.fill-workshop-flow__rows {
  display: grid;
  gap: 8px;
}

.fill-workshop-flow__row {
  display: grid;
  grid-template-columns: minmax(140px, 0.34fr) 1fr minmax(190px, 0.44fr);
  gap: 10px;
  align-items: center;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid rgba(39, 88, 146, 0.1);
  border-radius: var(--command-radius-sm);
  background: rgba(248, 251, 255, 0.8);
}

.fill-workshop-flow__name {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.fill-workshop-flow__name strong {
  overflow: hidden;
  color: var(--command-ink);
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fill-workshop-flow__name span,
.fill-workshop-flow__stats em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.fill-workshop-flow__meter {
  display: flex;
  width: 100%;
  height: 10px;
  overflow: hidden;
  border-radius: var(--xt-radius-pill);
  background: rgba(39, 88, 146, 0.1);
}

.fill-workshop-flow__meter i {
  display: block;
  width: 0;
  min-width: 0;
  height: 100%;
  transition: width 260ms ease;
}

.fill-workshop-flow__meter .is-formal {
  background: var(--command-green);
}

.fill-workshop-flow__meter .is-draft {
  background: var(--command-amber);
}

.fill-workshop-flow__meter .is-missing {
  background: var(--command-red);
}

.fill-workshop-flow__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.fill-workshop-flow__stats span {
  min-width: 0;
  display: grid;
  gap: 1px;
}

.fill-workshop-flow__stats strong {
  overflow: hidden;
  color: var(--command-blue-deep);
  font-family: var(--xt-font-number);
  font-size: 15px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fill-workshop-flow__row.is-warning .fill-workshop-flow__stats span:nth-child(2) strong {
  color: var(--command-amber);
}

.fill-workshop-flow__row.is-danger .fill-workshop-flow__stats span:nth-child(3) strong {
  color: var(--command-red);
}

.live-pending-assignment,
.live-unbound-fill {
  display: grid;
  grid-template-columns: minmax(180px, 0.72fr) 1fr auto;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  padding: 13px 14px;
  border: 1px solid rgba(183, 121, 31, 0.24);
  border-radius: var(--command-radius);
  background:
    linear-gradient(180deg, rgba(251, 191, 36, 0.12), rgba(255, 255, 255, 0.92)),
    #fff;
  box-shadow: 0 14px 32px rgba(183, 121, 31, 0.08);
}

.live-pending-assignment {
  grid-template-columns: minmax(160px, 0.52fr) minmax(220px, 0.8fr) 1fr;
}

.live-pending-assignment__metric,
.live-unbound-fill__metric {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.live-pending-assignment__metric span,
.live-pending-assignment__metric em,
.live-pending-assignment__meta span,
.live-pending-assignment__rows em,
.live-unbound-fill__metric span,
.live-unbound-fill__metric em,
.live-unbound-fill__meta span,
.live-unbound-fill__rows em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.live-pending-assignment__metric strong,
.live-unbound-fill__metric strong {
  color: var(--command-amber);
  font-family: var(--xt-font-number);
  font-size: 25px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.live-pending-assignment__meta,
.live-pending-assignment__rows,
.live-unbound-fill__meta,
.live-unbound-fill__rows {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.live-pending-assignment__meta span,
.live-pending-assignment__rows span,
.live-unbound-fill__meta span,
.live-unbound-fill__rows span {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 9px;
  border: 1px solid rgba(183, 121, 31, 0.18);
  border-radius: var(--command-radius-sm);
  background: rgba(255, 255, 255, 0.72);
}

.live-pending-assignment__rows strong,
.live-pending-assignment__rows b,
.live-unbound-fill__rows strong,
.live-unbound-fill__rows b {
  color: var(--command-ink);
  font-size: 12px;
  font-weight: 900;
}

.live-pending-assignment__rows b,
.live-unbound-fill__rows b {
  color: var(--command-amber);
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.live-unbound-fill__action {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid rgba(183, 121, 31, 0.3);
  border-radius: var(--command-radius-sm);
  background: var(--command-amber);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
  text-decoration: none;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.live-unbound-fill__action:active {
  transform: scale(0.98);
}

.live-machine-ownership {
  display: grid;
  grid-template-columns: minmax(190px, 0.58fr) 1fr;
  gap: 14px;
  align-items: center;
  margin-bottom: 12px;
  padding: 14px;
  overflow: hidden;
  border: 1px solid rgba(39, 88, 146, 0.15);
  border-radius: var(--command-radius);
  background:
    linear-gradient(180deg, rgba(230, 244, 255, 0.78), rgba(255, 255, 255, 0.96)),
    #fff;
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.06);
}

.live-machine-ownership.is-warning {
  border-color: rgba(183, 121, 31, 0.24);
}

.live-machine-ownership__head {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.live-machine-ownership__head strong {
  color: var(--command-ink);
  font-size: 14px;
  font-weight: 900;
}

.live-machine-ownership__head span {
  overflow: hidden;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-machine-ownership__body {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.live-machine-ownership__meter {
  display: flex;
  width: 100%;
  height: 12px;
  overflow: hidden;
  border-radius: var(--xt-radius-pill);
  background: rgba(39, 88, 146, 0.1);
}

.live-machine-ownership__meter i {
  display: block;
  width: 0;
  min-width: 0;
  height: 100%;
  transition: width 260ms ease;
}

.live-machine-ownership__meter .is-bound {
  background: linear-gradient(90deg, var(--command-green), var(--command-cyan));
}

.live-machine-ownership__meter .is-unbound {
  background: linear-gradient(90deg, var(--command-amber), var(--command-red));
}

.live-machine-ownership__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.live-machine-ownership__stats span {
  min-width: 0;
  min-height: 50px;
  display: grid;
  align-content: center;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid rgba(39, 88, 146, 0.12);
  border-radius: var(--command-radius-sm);
  background: rgba(255, 255, 255, 0.74);
}

.live-machine-ownership__stats strong {
  overflow: hidden;
  color: var(--command-blue-deep);
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-machine-ownership__stats em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.live-machine-ownership.is-warning .live-machine-ownership__stats span:nth-child(2) strong {
  color: var(--command-amber);
}

.live-output-distribution {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: #fff;
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.06);
}

.live-output-distribution__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.live-output-distribution__head strong {
  color: var(--command-ink);
  font-weight: 900;
}

.live-output-distribution__head span,
.live-output-distribution__empty {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.live-output-distribution__rows {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.live-output-row {
  position: relative;
  display: grid;
  grid-template-rows: auto auto 8px;
  gap: 8px;
  min-width: 0;
  min-height: 126px;
  padding: 11px;
  overflow: hidden;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: var(--command-blue-soft);
}

.live-output-row.is-unbound {
  border-color: rgba(183, 121, 31, 0.28);
  background: linear-gradient(180deg, rgba(251, 191, 36, 0.14), rgba(230, 244, 255, 0.72));
}

.live-output-row__main {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding-right: 58px;
}

.live-output-row__main strong {
  overflow: hidden;
  color: var(--command-ink);
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-output-row__main span {
  min-height: 32px;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.35;
}

.live-output-row__metric {
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.live-output-row__metric strong {
  color: var(--command-blue-deep);
  font-family: var(--xt-font-number);
  font-size: 21px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.live-output-row__metric span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.live-output-row__bar {
  width: 100%;
  height: 8px;
  overflow: hidden;
  border-radius: var(--xt-radius-pill);
  background: rgba(39, 88, 146, 0.12);
}

.live-output-row__bar i {
  display: block;
  width: 0;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--command-blue), var(--command-cyan));
  transition: width 260ms ease;
}

.live-output-row.is-unbound .live-output-row__bar i {
  background: linear-gradient(90deg, var(--command-amber), var(--command-cyan));
}

.live-output-row__tag {
  position: absolute;
  right: 9px;
  top: 9px;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 7px;
  border: 1px solid rgba(39, 88, 146, 0.14);
  border-radius: var(--command-radius-sm);
  background: rgba(255, 255, 255, 0.72);
  color: var(--command-blue-deep);
  font-size: 11px;
  font-weight: 900;
}

.live-output-row.is-unbound .live-output-row__tag {
  color: var(--command-amber);
}

.live-shift-rhythm {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: #fff;
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.06);
}

.live-shift-rhythm__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.live-shift-rhythm__head strong {
  color: var(--command-ink);
  font-weight: 900;
}

.live-shift-rhythm__head span,
.live-shift-rhythm__empty {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.live-shift-rhythm__rows {
  display: grid;
  gap: 8px;
}

.live-shift-row {
  display: grid;
  grid-template-columns: minmax(92px, 128px) minmax(0, 1fr) minmax(92px, 116px);
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding: 9px 10px;
  border-radius: var(--command-radius-sm);
  background: var(--command-blue-soft);
}

.live-shift-row__label,
.live-shift-row__metric {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.live-shift-row__label strong {
  overflow: hidden;
  color: var(--command-ink);
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-shift-row__label span,
.live-shift-row__metric span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.live-shift-row__bar {
  height: 10px;
  overflow: hidden;
  border-radius: var(--xt-radius-pill);
  background: rgba(39, 88, 146, 0.12);
}

.live-shift-row__bar i {
  display: block;
  width: 100%;
  height: 100%;
  transform-origin: left center;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--command-blue), var(--command-cyan));
  transition: transform 260ms ease;
}

.live-shift-row__metric {
  text-align: right;
}

.live-shift-row__metric strong {
  color: var(--command-blue-deep);
  font-family: var(--xt-font-number);
  font-size: 16px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.management-flow__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.management-flow__head strong {
  color: var(--command-ink);
  font-weight: 900;
}

.management-flow__head span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.management-flow__nodes {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
}

.management-flow__node {
  position: relative;
  display: grid;
  gap: 4px;
  min-height: 64px;
  padding: 10px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: var(--command-blue-soft);
}

.management-flow__node strong {
  color: var(--command-blue-deep);
  font-size: 14px;
  font-weight: 900;
}

.live-dashboard__section-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 2px 0 10px;
  color: var(--command-ink);
  font-weight: 900;
}

.live-dashboard__section-title span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.command-status-strip {
  display: grid;
  grid-template-columns: minmax(260px, 1.45fr) repeat(5, minmax(148px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.command-status-card {
  --status-accent: var(--command-blue);
  position: relative;
  display: grid;
  align-content: space-between;
  gap: 7px;
  min-height: 108px;
  padding: 15px;
  overflow: hidden;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: var(--command-panel);
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.07);
}

.command-status-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: var(--status-accent);
}

.command-status-card::after {
  content: '';
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 28px;
  height: 18px;
  border-right: 2px solid color-mix(in srgb, var(--status-accent) 32%, transparent);
  border-bottom: 2px solid color-mix(in srgb, var(--status-accent) 32%, transparent);
  opacity: 0.86;
}

.command-status-card span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.command-status-card strong {
  position: relative;
  z-index: 1;
  color: var(--command-ink);
  font-family: var(--xt-font-number);
  font-size: 29px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  line-height: 1;
}

.command-status-card em {
  position: relative;
  z-index: 1;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.command-status-card--output {
  --status-accent: var(--command-cyan);
  border-color: transparent;
  background:
    linear-gradient(135deg, rgba(9, 96, 238, 0.98), rgba(15, 142, 234, 0.96) 58%, rgba(18, 172, 190, 0.9));
  box-shadow: 0 18px 42px rgba(11, 99, 246, 0.21);
}

.command-status-card--progress {
  --status-accent: var(--command-blue);
}

.command-status-card--missing {
  --status-accent: var(--xt-border-strong);
}

.command-status-card--attention {
  --status-accent: var(--command-cyan);
}

.command-status-card--yield {
  --status-accent: var(--command-green);
}

.command-status-card--refresh {
  --status-accent: var(--xt-text-muted);
}

.command-status-card--output span,
.command-status-card--output em {
  color: rgba(255, 255, 255, 0.66);
}

.command-status-card--output strong {
  color: rgba(255, 255, 255, 0.92);
}

.command-status-card--output::after {
  width: 34px;
  height: 22px;
  border-color: rgba(255, 255, 255, 0.32);
}

.command-status-card.is-danger {
  --status-accent: var(--command-red);
  border-color: rgba(194, 65, 52, 0.22);
}

.command-status-card.is-warning {
  --status-accent: var(--command-amber);
  border-color: rgba(183, 121, 31, 0.24);
}

.live-dashboard__workshops {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.live-dashboard__collapse {
  min-width: 0;
  border: 0;
}

.live-dashboard__collapse :deep(.el-collapse-item) {
  margin-bottom: 12px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: var(--command-panel);
  box-shadow: 0 14px 36px rgba(25, 62, 118, 0.07);
  overflow: hidden;
}

.live-dashboard__collapse :deep(.el-collapse-item__header) {
  min-height: 58px;
  padding: 0 16px;
  border-bottom: 1px solid var(--command-line);
  background: #fff;
}

.live-dashboard__collapse :deep(.el-collapse-item__wrap) {
  min-width: 0;
  border-bottom: 0;
}

.live-dashboard__collapse :deep(.el-collapse-item__content) {
  min-width: 0;
  padding-bottom: 0;
}

.live-workshop__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  gap: 16px;
}

.live-workshop__title strong {
  display: block;
  color: var(--command-ink);
  font-size: 16px;
  font-weight: 900;
}

.live-workshop__title span,
.live-workshop__title-meta span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.live-workshop__title-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  font-variant-numeric: tabular-nums;
}

.live-workshop__title-meta span {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  padding: 0 9px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: var(--command-blue-soft);
  color: var(--command-blue-deep);
}

.live-workshop__board {
  min-width: 0;
  overflow: hidden;
}

.live-board__scroller {
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  padding: 12px;
  background: linear-gradient(180deg, rgba(248, 251, 255, 0.96), rgba(255, 255, 255, 0.98));
}

.live-board__table {
  display: grid;
  min-width: 880px;
  gap: 1px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: var(--command-line);
  overflow: hidden;
}

.live-board__row--grid {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: subgrid;
}

.live-board__row--head {
  position: sticky;
  top: 0;
  z-index: 1;
}

.live-board__stub,
.live-board__head-cell,
.live-board__total-cell,
.live-summary-cell,
.live-attendance-cell,
.live-cell {
  min-height: 64px;
  padding: 10px 12px;
  background: #fff;
}

.live-board__stub,
.live-board__head-cell {
  display: flex;
  align-items: center;
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 900;
}

.live-board__row--head .live-board__stub,
.live-board__head-cell {
  min-height: 44px;
  background: var(--command-blue-soft);
  color: var(--command-blue-deep);
}

.live-board__stub--machine {
  color: var(--command-ink);
}

.live-cell {
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 3px 8px;
  width: 100%;
  border: 0;
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
  box-shadow: inset 3px 0 0 transparent;
  transition-property: transform, box-shadow, background-color;
  transition-duration: var(--xt-motion-fast);
  transition-timing-function: var(--xt-ease);
}

.live-cell:active {
  transform: scale(0.98);
}

.live-cell:focus-visible {
  outline: none;
  box-shadow: var(--app-focus-ring);
}

.live-cell__symbol {
  grid-row: 1 / span 3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--xt-radius-pill);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
}

.live-cell strong {
  color: var(--command-ink);
  font-size: 14px;
  font-weight: 900;
}

.live-cell__count,
.live-cell__yield {
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.live-cell.tone-success {
  background: color-mix(in srgb, var(--xt-success-light) 72%, #fff);
  box-shadow: inset 3px 0 0 var(--command-green);
}

.live-cell.tone-success .live-cell__symbol {
  background: var(--command-green);
}

.live-cell.tone-warning {
  background: color-mix(in srgb, var(--xt-warning-light) 72%, #fff);
  box-shadow: inset 3px 0 0 var(--command-amber);
}

.live-cell.tone-warning .live-cell__symbol {
  background: var(--command-amber);
}

.live-cell.tone-danger {
  background: color-mix(in srgb, var(--xt-danger-light) 72%, #fff);
  box-shadow: inset 3px 0 0 var(--command-red);
}

.live-cell.tone-danger .live-cell__symbol {
  background: var(--command-red);
}

.live-cell.tone-muted,
.live-cell.is-disabled {
  background: var(--xt-bg-panel-muted);
  color: var(--xt-text-muted);
  cursor: default;
}

.live-cell.tone-muted .live-cell__symbol,
.live-cell.is-disabled .live-cell__symbol {
  background: var(--xt-text-muted);
}

.live-cell.is-updated {
  box-shadow: inset 0 0 0 2px var(--command-blue);
}

.live-board__total-cell,
.live-summary-cell,
.live-attendance-cell {
  display: grid;
  gap: 3px;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.live-board__total-cell strong,
.live-summary-cell strong {
  color: var(--command-ink);
  font-size: 14px;
  font-weight: 900;
}

.live-board__total-cell--accent {
  background: var(--command-blue-soft);
  color: var(--command-blue-deep);
}

.live-board__total-cell--muted {
  color: var(--xt-text-muted);
}

.live-dashboard__bottom {
  min-width: 0;
  margin-top: 14px;
  border-color: var(--command-line);
  border-radius: var(--command-radius);
  background: var(--command-panel);
  box-shadow: 0 14px 36px rgba(25, 62, 118, 0.07);
}

.live-dashboard__bottom :deep(.el-card__header) {
  border-bottom-color: var(--command-line);
  background: #fff;
}

.live-dashboard__table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  gap: 16px;
}

.live-dashboard__table-header strong {
  color: var(--command-ink);
  font-size: 16px;
  font-weight: 900;
}

.live-dashboard__export-button {
  flex: 0 0 auto;
}

.live-drawer__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.live-drawer__meta span {
  padding: 6px 9px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: var(--command-blue-soft);
  color: var(--command-blue-deep);
  font-size: 12px;
  font-weight: 800;
}

@media (hover: hover) {
  .live-cell:not(.is-disabled):hover {
    transform: translateY(-1px);
    box-shadow: var(--xt-shadow-sm);
  }
}

@media (max-width: 1200px) {
  .management-overview-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .live-pending-assignment,
  .live-unbound-fill {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .fill-intake-strip {
    grid-template-columns: 1fr;
  }

  .live-machine-ownership {
    grid-template-columns: 1fr;
  }

  .fill-workshop-flow__row {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .management-flow__nodes {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .live-output-distribution__rows {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .command-status-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .live-dashboard :deep(.reference-page__header) {
    display: grid;
    padding: 12px;
  }

  .live-dashboard :deep(.reference-page__actions) {
    display: grid;
    grid-template-columns: 1fr;
    width: 100%;
  }

  .live-dashboard :deep(.reference-page__actions .el-date-editor) {
    width: 100%;
  }

  .live-dashboard__connection,
  .live-dashboard__progress-pill,
  .live-dashboard :deep(.reference-page__actions .el-button) {
    width: 100%;
    justify-content: center;
  }

  .management-overview-strip,
  .management-flow__nodes,
  .live-output-distribution__rows,
  .command-status-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .mes-connection-strip {
    align-items: flex-start;
    flex-direction: column;
  }

  .mes-connection-strip__meta {
    justify-content: flex-start;
  }

  .live-unbound-fill__action {
    width: 100%;
  }

  .live-output-distribution__head {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .live-machine-ownership__head span {
    white-space: normal;
  }

  .fill-workshop-flow__head {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .live-shift-rhythm__head {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .live-shift-row {
    grid-template-columns: 1fr;
    align-items: stretch;
    gap: 8px;
  }

  .live-shift-row__metric {
    align-items: baseline;
    grid-template-columns: max-content max-content;
    justify-content: space-between;
    text-align: left;
  }

  .management-overview-card,
  .command-status-card {
    min-height: 92px;
  }

  .management-overview-card strong,
  .command-status-card strong {
    font-size: 24px;
  }

  .live-workshop__title {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .live-dashboard__table-header {
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .fill-workshop-flow__meter i,
  .live-shift-row__bar i {
    transition: none;
  }
}

@media (max-width: 480px) {
  .management-overview-strip,
  .management-flow__nodes,
  .live-output-distribution__rows,
  .command-status-strip {
    grid-template-columns: 1fr;
  }

  .live-machine-ownership__stats {
    grid-template-columns: 1fr;
  }

  .fill-intake-strip__stats {
    grid-template-columns: 1fr;
  }

  .fill-workshop-flow__stats {
    grid-template-columns: 1fr;
  }
}
</style>
