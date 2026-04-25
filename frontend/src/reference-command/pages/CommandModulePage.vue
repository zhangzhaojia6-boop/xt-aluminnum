<template>
  <div class="cmd-page">
    <CenterPageShell
      v-if="isFactoryModule"
      class="factory-center-page"
      center-no="05"
      title="工厂作业看板"
      data-testid="factory-dashboard"
    >
      <template #tools>
        <span class="factory-center-page__updated">更新时间：{{ factoryData.updatedAt }}</span>
        <button type="button" class="factory-center-page__refresh" @click="refreshFactoryView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="factoryData.source !== 'live'"
          :source="factoryData.source"
          message="工厂作业看板使用厂级聚合兜底数据，真实读模型接入后替换。"
        />
      </template>

      <KpiStrip :items="factoryData.kpis" />

      <div class="factory-center-page__layout">
        <DataTableShell
          data-testid="factory-line-table"
          title="产线运行明细"
          :columns="factoryColumns"
          :rows="factoryTableRows"
        >
          <template #cell-name="{ row }">
            <div class="factory-line-name" :class="{ 'is-total': row.isTotal }">
              <strong>{{ row.name }}</strong>
              <SourceBadge v-if="row.source" :source="row.source" />
            </div>
          </template>
          <template #cell-output="{ row }">
            <strong class="factory-number">{{ row.output }}</strong>
          </template>
          <template #cell-yieldRate="{ row }">
            <span class="factory-rate">{{ row.yieldRate }}</span>
          </template>
          <template #cell-qualityRate="{ row }">
            <span class="factory-rate">{{ row.qualityRate }}</span>
          </template>
          <template #cell-exceptionCount="{ row }">
            <StatusBadge
              :label="`${row.exceptionCount} 项`"
              :tone="row.exceptionCount > 1 ? 'danger' : row.exceptionCount === 1 ? 'warning' : 'success'"
            />
          </template>
          <template #cell-trend="{ row }">
            <CommandTrend class="factory-sparkline" :values="row.trend" />
          </template>
        </DataTableShell>

        <SectionCard title="风险摘要" class="factory-risk-card">
          <div v-if="factoryData.risks.length" class="factory-risk-list">
            <article v-for="risk in factoryData.risks" :key="risk.label" class="factory-risk-item">
              <div>
                <span>{{ risk.label }}</span>
                <strong>{{ risk.value }}</strong>
              </div>
              <StatusBadge :label="risk.status" :tone="risk.tone" />
            </article>
          </div>
          <div v-else class="factory-empty-state">暂无风险摘要</div>

          <div class="factory-risk-events">
            <strong>最近风险事件</strong>
            <span v-for="event in factoryData.events" :key="event.time">
              <SourceBadge :source="event.source" />
              <em>{{ event.time }}</em>
              {{ event.text }}
            </span>
          </div>

          <div class="factory-risk-actions" aria-label="风险处置入口">
            <button type="button" @click="goRoute('review-task-center')">去审阅</button>
            <button type="button" @click="goRoute('review-quality-center')">看质量告警</button>
            <button type="button" @click="goRoute('review-report-center')">查看日报</button>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="来源与口径" class="factory-caliber-card">
        <div class="factory-caliber-list">
          <span v-for="item in factoryData.caliber" :key="item">{{ item }}</span>
        </div>
      </SectionCard>
    </CenterPageShell>
    <CenterPageShell
      v-else-if="isIngestionModule"
      class="ingestion-center-page cmd-layout--mapping-center"
      center-no="06"
      title="数据接入与字段映射中心"
      data-testid="review-ingestion-center-v2"
    >
      <template #tools>
        <span class="ingestion-center-page__scope">{{ ingestionData.environment }}</span>
        <span class="ingestion-center-page__date">业务日期：{{ ingestionBusinessDate }}</span>
        <span class="ingestion-center-page__updated">更新时间：{{ ingestionData.updatedAt }}</span>
        <select v-model="ingestionSourceFilter" class="ingestion-control" aria-label="数据源筛选">
          <option value="">全部数据源</option>
          <option v-for="source in ingestionSourceOptions" :key="source" :value="source">{{ source }}</option>
        </select>
        <select v-model="ingestionStatusFilter" class="ingestion-control" aria-label="状态筛选">
          <option value="">全部状态</option>
          <option value="mixed">mixed</option>
          <option value="fallback">fallback</option>
          <option value="待接入">待接入</option>
          <option value="部分字段">部分字段</option>
          <option value="试跑映射">试跑映射</option>
        </select>
        <button type="button" class="ingestion-refresh" @click="refreshIngestionView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="ingestionData.source !== 'live'"
          :source="ingestionData.source"
          message="数据接入与字段映射中心使用 fallback 治理数据，仅用于查看数据源、映射、批次和错误；不承接现场生产事实写入。"
        />
      </template>

      <KpiStrip :items="ingestionData.kpis" />

      <div class="ingestion-center-page__top">
        <DataTableShell
          data-testid="ingestion-source-table"
          title="数据源状态"
          subtitle="管理端配置治理面：展示来源状态、最近同步、成功率和失败摘要"
          :columns="ingestionSourceColumns"
          :rows="filteredIngestionDataSources"
        >
          <template #actions>
            <SourceBadge :source="ingestionData.source" />
          </template>
          <template #cell-name="{ row }">
            <div class="ingestion-source-cell">
              <strong>{{ row.name }}</strong>
              <SourceBadge :source="row.source" />
            </div>
          </template>
          <template #cell-statusLabel="{ row }">
            <StatusBadge :label="row.statusLabel" :tone="row.tone" />
          </template>
          <template #cell-failed="{ row }">
            <strong class="ingestion-number" :class="{ 'is-danger': Number(row.failed) > 0 }">{{ row.failed }}</strong>
          </template>
          <template #cell-owner="{ row }">
            <div class="ingestion-note-cell">
              <strong>{{ row.owner }}</strong>
              <span>{{ row.note }}</span>
            </div>
          </template>
          <template #cell-action="{ row }">
            <div class="ingestion-row-actions">
              <button type="button" disabled :title="`详情接口待接入：${row.id}`">查看详情</button>
              <button type="button" disabled title="配置接口待接入，当前不伪造接入完成">配置</button>
            </div>
          </template>
        </DataTableShell>

        <SectionCard title="导入概览" :meta="ingestionData.source">
          <div class="ingestion-overview">
            <div class="ingestion-overview__metrics">
              <article>
                <span>总数据量</span>
                <strong>{{ ingestionData.importOverview.totalRows }}</strong>
                <em>条</em>
              </article>
              <article>
                <span>成功导入（试跑）</span>
                <strong>{{ ingestionData.importOverview.acceptedRows }}</strong>
                <em>条</em>
              </article>
              <article>
                <span>成功率</span>
                <strong>{{ ingestionData.importOverview.successRate }}</strong>
                <em>fallback</em>
              </article>
              <article>
                <span>失败记录</span>
                <strong class="is-danger">{{ ingestionData.importOverview.failedRows }}</strong>
                <em>条</em>
              </article>
              <article>
                <span>待处理</span>
                <strong class="is-warning">{{ ingestionData.importOverview.pendingRows }}</strong>
                <em>条</em>
              </article>
            </div>
            <div class="ingestion-ring" :style="{ background: ingestionOverviewGradient }" aria-label="导入概览环形图">
              <span></span>
            </div>
            <div class="ingestion-overview__legend">
              <span v-for="segment in ingestionData.importOverview.segments" :key="segment.key">
                <i :style="{ background: segment.color }"></i>
                {{ segment.label }}
              </span>
            </div>
          </div>
        </SectionCard>
      </div>

      <DataTableShell
        data-testid="ingestion-field-table"
        title="字段映射表"
        subtitle="字段名称、数据源字段、映射方式、校验状态与口径说明"
        :columns="ingestionFieldColumns"
        :rows="ingestionData.fieldMappings"
      >
        <template #cell-name="{ row }">
          <div class="ingestion-field-cell">
            <strong>{{ row.name }}</strong>
            <SourceBadge :source="row.sourceKey" />
          </div>
        </template>
        <template #cell-sourceField="{ row }">
          <div class="ingestion-note-cell">
            <strong>{{ row.sourceField }}</strong>
            <span>{{ row.source }}</span>
          </div>
        </template>
        <template #cell-mapping="{ row }">
          <StatusBadge :label="row.mapping" tone="info" />
        </template>
        <template #cell-check="{ row }">
          <StatusBadge :label="row.check" :tone="row.tone" />
        </template>
        <template #cell-caliber="{ row }">
          <span class="ingestion-caliber-copy">{{ row.caliber }}</span>
        </template>
        <template #cell-action="{ row }">
          <button type="button" class="ingestion-mini-button" disabled :title="`字段 ${row.name} 的编辑接口待接入`">配置</button>
        </template>
      </DataTableShell>

      <div class="ingestion-center-page__bottom">
        <DataTableShell
          data-testid="ingestion-history-table"
          title="导入历史"
          subtitle="最近导入批次、失败行数、状态和错误摘要"
          :columns="ingestionHistoryColumns"
          :rows="ingestionData.importHistory"
        >
          <template #cell-source="{ row }">
            <div class="ingestion-source-cell">
              <strong>{{ row.source }}</strong>
              <SourceBadge :source="row.sourceKey" />
            </div>
          </template>
          <template #cell-failed="{ row }">
            <strong class="ingestion-number" :class="{ 'is-danger': Number(row.failed) > 0 }">{{ row.failed }}</strong>
          </template>
          <template #cell-status="{ row }">
            <div class="ingestion-note-cell">
              <StatusBadge :label="row.status" :tone="row.tone" />
              <span>{{ row.reason }}</span>
            </div>
          </template>
          <template #cell-action="{ row }">
            <div class="ingestion-row-actions">
              <button type="button" disabled :title="`详情接口待接入：${row.id}`">查看详情</button>
              <button type="button" disabled title="错误明细接口待接入">查看错误</button>
              <button type="button" disabled title="重新处理接口待接入，当前不伪造处理成功">重新处理</button>
            </div>
          </template>
        </DataTableShell>

        <aside class="ingestion-center-page__side">
          <SectionCard title="错误 / 失败说明" :meta="ingestionData.source">
            <div class="ingestion-error-list">
              <article v-for="error in ingestionData.errors" :key="error.label">
                <div>
                  <span>{{ error.label }}</span>
                  <strong>{{ error.value }}</strong>
                </div>
                <StatusBadge :label="error.status" :tone="error.tone" />
              </article>
            </div>
            <div class="ingestion-risk-actions">
              <button type="button" @click="goRoute('admin-governance-center')">去治理</button>
              <button type="button" @click="goRoute('admin-ops-reliability')">看运维</button>
              <button type="button" @click="goRoute('review-task-center')">看审阅任务</button>
              <button type="button" @click="goRoute('review-report-center')">看日报影响</button>
            </div>
          </SectionCard>

          <SectionCard title="操作区" :meta="ingestionData.actions.upload">
            <div class="ingestion-action-grid">
              <button type="button" disabled title="上传接口待接入，当前不写生产事实">上传文件</button>
              <button type="button" disabled title="配置映射接口待接入">配置映射</button>
              <button type="button" @click="showIngestionPanel('errors')">查看错误</button>
              <button type="button" disabled title="重新处理接口待接入，当前不伪造成功">重新处理</button>
              <button type="button" disabled title="导出接口待接入">导出错误清单</button>
              <button type="button" @click="showIngestionPanel('caliber')">查看口径</button>
            </div>
            <p class="ingestion-caliber-copy">禁用动作没有真实接口，不上传、不重处理，也不展示生产库写入成功状态。</p>
          </SectionCard>
        </aside>
      </div>

      <SectionCard :title="ingestionInfoPanel === 'errors' ? '错误口径' : '口径说明'" :meta="ingestionData.environment">
        <p class="ingestion-caliber-copy">{{ ingestionData.caliber }}</p>
      </SectionCard>
    </CenterPageShell>
    <CenterPageShell
      v-else-if="isReportsModule"
      class="reports-center-page"
      center-no="08"
      title="日报与交付中心"
      data-testid="reports-delivery-center"
    >
      <template #tools>
        <span class="reports-center-page__date">业务日期：{{ reportsData.businessDate }}</span>
        <span class="reports-center-page__updated">更新时间：{{ reportsData.updatedAt }}</span>
        <input
          class="reports-center-page__date-input"
          type="date"
          :value="reportsData.businessDate"
          disabled
          aria-label="业务日期"
          title="日期查询接口待接入，当前只展示本读面数据"
        />
        <button type="button" class="reports-center-page__refresh" @click="refreshReportsView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="reportsData.source !== 'live'"
          :source="reportsData.source"
          message="日报与交付中心使用 fallback 数据，仅用于查看生成、导出与交付状态；不承接生产事实写入。"
        />
      </template>

      <KpiStrip :items="reportsData.kpis" />

      <div class="reports-center-page__overview">
        <SectionCard title="近 7 日日产 / 交付趋势" :meta="reportsData.scope">
          <div class="reports-trend" aria-label="近 7 日日产与交付趋势">
            <div v-for="point in reportsData.trend" :key="point.day" class="reports-trend__item">
              <div class="reports-trend__bars">
                <i
                  class="reports-trend__bar is-output"
                  :style="{ height: `${Math.max(16, Math.round((point.output / reportTrendMax) * 100))}%` }"
                ></i>
                <i
                  class="reports-trend__bar is-delivered"
                  :style="{ height: `${Math.max(10, point.delivered * 3)}%` }"
                ></i>
              </div>
              <strong>{{ point.output.toLocaleString() }}</strong>
              <span>{{ point.day }}</span>
            </div>
          </div>
          <div class="reports-trend__legend">
            <span><i class="is-output"></i>日产量（吨）</span>
            <span><i class="is-delivered"></i>已交付（车）</span>
          </div>
        </SectionCard>

        <SectionCard title="交付摘要" :meta="reportsData.source">
          <div class="reports-delivery-summary">
            <article v-for="item in reportsData.deliverySummary" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }} <small>{{ item.unit }}</small></strong>
              <StatusBadge :label="item.label" :tone="item.tone" />
            </article>
          </div>
        </SectionCard>
      </div>

      <DataTableShell
        data-testid="reports-delivery-table"
        title="交付清单"
        subtitle="日报范围基于 auto_confirmed / 已自动确认数据口径"
        :columns="reportDeliveryColumns"
        :rows="reportsData.deliveryRows"
      >
        <template #cell-name="{ row }">
          <div class="reports-report-name">
            <strong>{{ row.name }}</strong>
            <SourceBadge :source="row.source" />
          </div>
        </template>
        <template #cell-caliber="{ row }">
          <StatusBadge :label="row.caliber" tone="info" />
        </template>
        <template #cell-generationStatus="{ row }">
          <StatusBadge :label="row.generationStatus" :tone="reportStatusTone(row.generationStatus)" />
        </template>
        <template #cell-deliveryStatus="{ row }">
          <StatusBadge :label="row.deliveryStatus" :tone="reportStatusTone(row.deliveryStatus)" />
          <span v-if="row.deliveryStatus === '交付失败'" class="reports-failure-reason">{{ row.reason }}</span>
        </template>
        <template #cell-exportStatus="{ row }">
          <StatusBadge :label="row.exportStatus" :tone="reportStatusTone(row.exportStatus)" />
        </template>
        <template #cell-action="{ row }">
          <button type="button" class="reports-mini-button" disabled :title="row.reason">只读</button>
        </template>
      </DataTableShell>

      <div class="reports-center-page__bottom">
        <SectionCard title="交付操作区" :meta="reportsData.actions.send">
          <div class="reports-action-grid">
            <button type="button" disabled>导出 PDF</button>
            <button type="button" disabled>导出 Excel</button>
            <button type="button" disabled>发送 / 交付</button>
            <button type="button" disabled>重新生成</button>
            <button type="button" @click="showReportPanel('caliber')">查看口径</button>
            <button type="button" @click="showReportPanel('blockers')">查看阻塞项</button>
          </div>
          <p class="reports-action-copy">导出、发送与重新生成接口未接入当前中心读面，按钮保持禁用，不伪造成功状态。</p>
        </SectionCard>

        <SectionCard title="阻塞与风险摘要" :meta="reportsData.source">
          <div class="reports-risk-list">
            <article v-for="blocker in reportsData.blockers" :key="blocker.label">
              <div>
                <span>{{ blocker.label }}</span>
                <strong>{{ blocker.value }}</strong>
              </div>
              <StatusBadge :label="blocker.status" :tone="blocker.tone" />
            </article>
          </div>
          <div class="reports-risk-actions">
            <button type="button" @click="goRoute('review-task-center')">去审阅</button>
            <button type="button" @click="goRoute('review-quality-center')">看质量告警</button>
            <button type="button" @click="goRoute('factory-dashboard')">看工厂看板</button>
            <button
              type="button"
              :disabled="!canOpenAdminIngestion"
              :title="canOpenAdminIngestion ? '进入数据接入中心' : '当前账号无管理端权限'"
              @click="goAdminIngestion"
            >
              看数据接入
            </button>
          </div>
        </SectionCard>
      </div>

      <SectionCard :title="reportInfoPanel === 'blockers' ? '阻塞项说明' : '口径说明'">
        <p v-if="reportInfoPanel === 'blockers'" class="reports-caliber-copy">
          缺报班次、待审记录、异常未关闭与 fallback / mixed 数据源会阻塞日报交付；请优先回到审阅、质量或工厂看板复核。
        </p>
        <p v-else class="reports-caliber-copy">
          日报范围基于已自动确认数据口径（auto_confirmed）生成。当前页面用于查看日报生成、导出与交付状态，不承接生产事实写入。若数据源标记为 fallback/mixed，请以现场试跑口径复核。
        </p>
      </SectionCard>
    </CenterPageShell>
    <CenterPageShell
      v-else-if="isQualityModule"
      class="quality-center-page cmd-layout--quality-alerts"
      center-no="09"
      title="质量与告警中心"
      data-testid="quality-alerts-center"
    >
      <template #tools>
        <span class="quality-center-page__date">业务日期：{{ qualityData.businessDate }}</span>
        <span class="quality-center-page__updated">更新时间：{{ qualityData.updatedAt }}</span>
        <input
          v-model="qualityBusinessDate"
          class="quality-control"
          type="date"
          disabled
          aria-label="业务日期"
          title="日期查询接口待接入，当前只展示本读面数据"
        />
        <select v-model="qualitySeverityFilter" class="quality-control" aria-label="严重度筛选">
          <option value="">全部严重度</option>
          <option value="高">高</option>
          <option value="中">中</option>
          <option value="低">低</option>
        </select>
        <select v-model="qualityStatusFilter" class="quality-control" aria-label="状态筛选">
          <option value="">全部状态</option>
          <option value="待处置">待处置</option>
          <option value="处理中">处理中</option>
          <option value="已处置">已处置</option>
          <option value="已关闭">已关闭</option>
          <option value="阻塞">阻塞</option>
        </select>
        <select v-model="qualitySourceFilter" class="quality-control" aria-label="来源筛选">
          <option value="">全部来源</option>
          <option v-for="source in qualitySourceOptions" :key="source" :value="source">{{ source }}</option>
        </select>
        <button type="button" class="quality-refresh" @click="refreshQualityView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="qualityData.source !== 'live'"
          :source="qualityData.source"
          message="质量与告警中心使用 fallback 读面数据，仅用于查看告警、处置状态和日报影响；不承接生产事实写入。"
        />
      </template>

      <KpiStrip :items="qualityData.kpis" />

      <div class="quality-center-page__layout">
        <DataTableShell
          data-testid="quality-alert-table"
          title="告警列表"
          subtitle="质量告警来源、严重度、处理状态与日报交付影响"
          :columns="qualityAlertColumns"
          :rows="filteredQualityAlerts"
        >
          <template #actions>
            <StatusBadge label="辅助建议" tone="info" />
          </template>
          <template #cell-source="{ row }">
            <div class="quality-source-cell">
              <strong>{{ row.source }}</strong>
              <SourceBadge :source="row.sourceType" />
            </div>
          </template>
          <template #cell-detail="{ row }">
            <div class="quality-alert-detail">
              <strong>{{ row.detail }}</strong>
              <span>{{ row.reason }}</span>
            </div>
          </template>
          <template #cell-severity="{ row }">
            <StatusBadge :label="row.severity" :tone="qualitySeverityTone(row.severity)" />
          </template>
          <template #cell-status="{ row }">
            <StatusBadge :label="row.status" :tone="qualityStatusTone(row.status)" />
          </template>
          <template #cell-impactScope="{ row }">
            <div class="quality-impact-cell">
              <strong>{{ row.impactScope }}</strong>
              <span>{{ row.deliveryImpact }}</span>
            </div>
          </template>
          <template #cell-action="{ row }">
            <div class="quality-row-actions">
              <button type="button" disabled :title="`详情接口待接入：${row.id}`">查看详情</button>
              <button type="button" disabled title="处置接口待接入，当前不伪造成功状态">标记处理中</button>
              <button type="button" disabled title="关闭接口待接入，AI 不会自动关闭告警">关闭</button>
            </div>
          </template>
        </DataTableShell>

        <aside class="quality-center-page__side">
          <SectionCard title="质量处置流程" :meta="qualityData.source">
            <div class="quality-workflow">
              <article v-for="step in qualityData.workflow" :key="step.title" class="quality-workflow__item">
                <div class="quality-workflow__mark">
                  <strong>{{ step.count }}</strong>
                </div>
                <div>
                  <header>
                    <strong>{{ step.title }}</strong>
                    <StatusBadge :label="step.status" :tone="step.tone" />
                  </header>
                  <p>{{ step.body }}</p>
                  <span>{{ step.nextAction }}</span>
                </div>
              </article>
            </div>
          </SectionCard>

          <SectionCard title="AI 辅助分诊" meta="辅助建议">
            <div class="quality-ai-list">
              <article v-for="item in qualityData.aiTriage" :key="item.label">
                <StatusBadge :label="item.label" :tone="item.tone" />
                <p>{{ item.value }}</p>
              </article>
            </div>
            <p class="quality-helper-copy">AI 只提供辅助建议，不形成最终结论，不自动关闭质量问题。</p>
          </SectionCard>
        </aside>
      </div>

      <div class="quality-center-page__bottom">
        <SectionCard title="操作区" :meta="qualityData.actions.export">
          <div class="quality-action-grid">
            <button type="button" disabled title="详情接口待接入">查看详情</button>
            <button type="button" disabled title="处置接口待接入">标记处理中</button>
            <button type="button" disabled title="关闭接口待接入，AI 不会自动关闭">关闭</button>
            <button type="button" @click="goRoute('review-task-center')">进入审阅任务</button>
            <button type="button" @click="goRoute('review-report-center')">查看日报影响</button>
            <button type="button" disabled title="导出接口待接入">导出告警清单</button>
            <button type="button" disabled title="历史追溯接口待接入">查看历史</button>
          </div>
          <p class="quality-helper-copy">当前只读面不接处置写接口；禁用动作不会伪造“已自动处置成功”。</p>
        </SectionCard>

        <SectionCard title="阻塞与风险摘要" :meta="qualityData.source">
          <div class="quality-blocker-list">
            <article v-for="blocker in qualityData.blockers" :key="blocker.label">
              <div>
                <span>{{ blocker.label }}</span>
                <strong>{{ blocker.value }}</strong>
              </div>
              <StatusBadge :label="blocker.status" :tone="blocker.tone" />
            </article>
          </div>
          <div class="quality-risk-actions">
            <button type="button" @click="goRoute('review-task-center')">去审阅</button>
            <button type="button" @click="goRoute('review-report-center')">看日报</button>
            <button type="button" @click="goRoute('factory-dashboard')">看工厂看板</button>
            <button
              type="button"
              :disabled="!canOpenAdminIngestion"
              :title="canOpenAdminIngestion ? '进入数据接入中心' : '当前账号无管理端权限'"
              @click="goAdminIngestion"
            >
              看数据接入
            </button>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="口径说明" :meta="qualityData.source">
        <p class="quality-caliber-copy">{{ qualityData.caliber }}</p>
      </SectionCard>
    </CenterPageShell>
    <CenterPageShell
      v-else-if="isCostModule"
      class="cost-center-page cmd-layout--cost-stack"
      center-no="10"
      title="成本核算与效益中心"
      data-testid="cost-benefit-center"
    >
      <template #tools>
        <span class="cost-center-page__scope">{{ costData.scope }}</span>
        <span class="cost-center-page__date">业务日期：{{ costBusinessDate }}</span>
        <span class="cost-center-page__updated">更新时间：{{ costData.updatedAt }}</span>
        <input
          v-model="costBusinessDate"
          class="cost-control"
          type="date"
          disabled
          aria-label="业务日期"
          title="日期查询接口待接入，当前只展示本读面数据"
        />
        <select v-model="costWorkshop" class="cost-control" aria-label="车间选择">
          <option v-for="item in costData.workshops" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
        <button type="button" class="cost-refresh" @click="refreshCostView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="costData.source !== 'live'"
          :source="costData.source"
          message="成本核算与效益中心使用 fallback 经营估算数据，仅用于查看策略口径和成本构成；不承接生产事实或财务结果写入。"
        />
      </template>

      <div class="cost-center-page__basis" aria-label="口径切换">
        <div class="cost-workshop-tabs" aria-label="车间 / 方案 tab">
          <button
            v-for="item in costData.workshops"
            :key="item.key"
            type="button"
            :class="{ 'is-active': item.key === costWorkshop }"
            @click="costWorkshop = item.key"
          >
            {{ item.label }}
          </button>
        </div>
        <div class="cost-basis-tabs">
          <button
            v-for="item in costData.basisOptions"
            :key="item.key"
            type="button"
            :class="{ 'is-active': item.key === costBasis }"
            @click="costBasis = item.key"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <KpiStrip :items="costData.kpis" />

      <div class="cost-center-page__overview">
        <SectionCard title="成本构成趋势" :meta="activeCostBasisLabel">
          <div class="cost-stack-chart" aria-label="成本构成趋势">
            <div v-for="point in costData.trend" :key="point.day" class="cost-stack-chart__item">
              <div class="cost-stack-chart__bar">
                <i
                  v-for="segment in costData.composition"
                  :key="`${point.day}-${segment.key}`"
                  :style="{
                    height: `${costSegmentHeight(point, segment)}%`,
                    background: segment.color
                  }"
                ></i>
              </div>
              <strong>{{ costTrendTotal(point).toLocaleString() }}</strong>
              <span>{{ point.day }}</span>
            </div>
          </div>
          <div class="cost-stack-chart__legend">
            <span v-for="segment in costData.composition" :key="segment.key">
              <i :style="{ background: segment.color }"></i>
              {{ segment.label }}
            </span>
          </div>
        </SectionCard>

        <SectionCard title="累计构成" :meta="activeCostWorkshopLabel">
          <div class="cost-composition-list">
            <article v-for="item in costData.composition" :key="item.key">
              <div>
                <i :style="{ background: item.color }"></i>
                <span>{{ item.label }}</span>
              </div>
              <strong>{{ item.value.toLocaleString() }}</strong>
              <em>{{ item.ratio }}%</em>
            </article>
            <article class="is-total">
              <div>
                <i></i>
                <span>合计</span>
              </div>
              <strong>{{ costData.cumulative.amount }}</strong>
              <em>100.0%</em>
            </article>
          </div>
          <div class="cost-cumulative-summary">
            <span>月累计估算：{{ costData.cumulative.monthEstimate }}</span>
            <span>产量：{{ costData.cumulative.monthOutput }}</span>
            <span>通货量：{{ costData.cumulative.monthThroughput }}</span>
          </div>
          <button type="button" class="cost-primary-action" disabled title="策略保存接口待接入，当前不伪造方案已保存">
            调整方案
          </button>
        </SectionCard>
      </div>

      <div class="cost-center-page__middle">
        <DataTableShell
          data-testid="cost-detail-table"
          title="成本明细表"
          subtitle="经营估算口径下的用量、金额、吨耗、月累计与来源状态"
          :columns="costDetailColumns"
          :rows="costData.detailRows"
        >
          <template #cell-item="{ row }">
            <div class="cost-item-cell">
              <strong>{{ row.item }}</strong>
              <SourceBadge :source="row.source" />
            </div>
          </template>
          <template #cell-status="{ row }">
            <StatusBadge :label="row.status" :tone="row.tone" />
          </template>
          <template #cell-basisText="{ row }">
            <span class="cost-basis-copy">{{ row.basisText }}</span>
          </template>
        </DataTableShell>

        <SectionCard title="累计构成 / 趋势" :meta="costData.source">
          <div class="cost-trend-summary">
            <article>
              <span>成本趋势</span>
              <strong>{{ costTrendDirection }}</strong>
              <em>{{ activeCostBasisLabel }}</em>
            </article>
            <article>
              <span>产量 / 通货量对比</span>
              <strong>{{ activeTrendPoint.outputTon }} / {{ activeTrendPoint.throughputTon }}</strong>
              <em>吨</em>
            </article>
            <article>
              <span>偏差风险</span>
              <strong>{{ activeTrendPoint.risk }}</strong>
              <em>人工复核</em>
            </article>
          </div>
          <p class="cost-caliber-copy">管理者可从堆叠趋势和明细表查看哪项成本拉高，但当前结果只用于经营解释。</p>
        </SectionCard>
      </div>

      <div class="cost-center-page__bottom">
        <SectionCard title="操作区" :meta="costData.actions.adjustPlan">
          <div class="cost-action-grid">
            <button type="button" disabled title="方案保存接口待接入">调整方案</button>
            <button type="button" @click="showCostPanel('caliber')">查看口径</button>
            <button type="button" disabled title="导出接口待接入，当前不伪造导出成功">导出</button>
            <button type="button" @click="goRoute('review-report-center')">查看日报影响</button>
            <button type="button" @click="goRoute('review-quality-center')">查看质量风险</button>
            <button type="button" @click="goRoute('factory-dashboard')">看工厂看板</button>
            <button
              type="button"
              :disabled="!canOpenAdminIngestion"
              :title="canOpenAdminIngestion ? '进入数据接入中心' : '当前账号无管理端权限'"
              @click="goAdminIngestion"
            >
              看数据接入
            </button>
          </div>
          <p class="cost-caliber-copy">禁用动作没有真实接口，不保存策略方案，不伪造导出成功，也不写入财务结果。</p>
        </SectionCard>

        <SectionCard title="风险摘要" meta="经营估算提醒">
          <div class="cost-risk-list">
            <article v-for="risk in costData.risks" :key="risk.label">
              <div>
                <span>{{ risk.label }}</span>
                <strong>{{ risk.value }}</strong>
              </div>
              <StatusBadge :label="risk.status" :tone="risk.tone" />
            </article>
          </div>
        </SectionCard>
      </div>

      <SectionCard :title="costInfoPanel === 'risk' ? '风险口径' : '口径说明'" :meta="costData.scope">
        <p class="cost-caliber-copy">{{ costData.caliber }}</p>
      </SectionCard>
    </CenterPageShell>
    <CommandPage v-else :module="module" :view-model="viewModel" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CenterPageShell from '../../components/app/CenterPageShell.vue'
import DataTableShell from '../../components/app/DataTableShell.vue'
import KpiStrip from '../../components/app/KpiStrip.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SectionCard from '../../components/app/SectionCard.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'
import { costCenterMock, factoryBoardMock, ingestionCenterMock, qualityCenterMock, reportsCenterMock } from '../../mocks/centerMockData.js'
import { useAuthStore } from '../../stores/auth.js'
import CommandPage from '../components/CommandPage.vue'
import CommandTrend from '../components/CommandTrend.vue'
import { adaptModuleView } from '../data/moduleAdapters.js'
import { findModuleById, findModuleByRouteName, referenceModules } from '../data/moduleCatalog.js'

const props = defineProps({
  moduleId: {
    type: String,
    default: ''
  }
})

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const reportInfoPanel = ref('caliber')
const qualityBusinessDate = ref(qualityCenterMock.businessDate)
const qualitySeverityFilter = ref('')
const qualityStatusFilter = ref('')
const qualitySourceFilter = ref('')
const costBusinessDate = ref(costCenterMock.businessDate)
const costWorkshop = ref(costCenterMock.activeWorkshop)
const costBasis = ref(costCenterMock.activeBasis)
const costInfoPanel = ref('caliber')
const ingestionBusinessDate = ref(ingestionCenterMock.businessDate)
const ingestionSourceFilter = ref('')
const ingestionStatusFilter = ref('')
const ingestionInfoPanel = ref('caliber')

const module = computed(() => (
  findModuleById(props.moduleId || route.meta?.moduleId)
  || findModuleByRouteName(route.name)
  || referenceModules[0]
))

const viewModel = computed(() => adaptModuleView(module.value.moduleId))
const isFactoryModule = computed(() => module.value.moduleId === '05' && route.name !== 'workshop-dashboard')
const isReportsModule = computed(() => module.value.moduleId === '08')
const isQualityModule = computed(() => module.value.moduleId === '09')
const isCostModule = computed(() => module.value.moduleId === '10')
const isIngestionModule = computed(() => module.value.moduleId === '06')
const factoryData = factoryBoardMock
const reportsData = reportsCenterMock
const qualityData = qualityCenterMock
const costData = costCenterMock
const ingestionData = ingestionCenterMock
const reportTrendMax = computed(() => Math.max(...reportsData.trend.map((point) => point.output), 1))
const canOpenAdminIngestion = computed(() => authStore.adminSurface)

const factoryColumns = [
  { key: 'name', label: '车间 / 产线' },
  { key: 'output', label: '产量（吨）' },
  { key: 'yieldRate', label: '成品率' },
  { key: 'qualityRate', label: '良率 / 优品率' },
  { key: 'exceptionCount', label: '异常' },
  { key: 'trend', label: '趋势（24h）' }
]

const factoryTableRows = computed(() => [
  ...factoryData.rows,
  {
    ...factoryData.total,
    id: 'factory-total',
    isTotal: true
  }
])

const reportDeliveryColumns = [
  { key: 'name', label: '日报名称' },
  { key: 'businessDate', label: '业务日期' },
  { key: 'scopeText', label: '范围 / 车间' },
  { key: 'caliber', label: '生成口径' },
  { key: 'generationStatus', label: '生成状态' },
  { key: 'deliveryStatus', label: '交付状态' },
  { key: 'exportStatus', label: '导出状态' },
  { key: 'receivers', label: '接收对象' },
  { key: 'updatedAt', label: '最近更新时间' },
  { key: 'action', label: '操作' }
]

const qualityAlertColumns = [
  { key: 'time', label: '时间' },
  { key: 'source', label: '来源' },
  { key: 'type', label: '类型' },
  { key: 'detail', label: '描述' },
  { key: 'severity', label: '严重度' },
  { key: 'status', label: '状态' },
  { key: 'impactScope', label: '影响范围' },
  { key: 'owner', label: '责任 / 建议处理人' },
  { key: 'action', label: '操作' }
]

const costDetailColumns = [
  { key: 'item', label: '项目' },
  { key: 'amount', label: '当日用量 / 金额' },
  { key: 'unit', label: '单位' },
  { key: 'price', label: '单价 / 折算价' },
  { key: 'tonCost', label: '吨耗 / 吨成本' },
  { key: 'monthly', label: '月累计' },
  { key: 'status', label: '状态' },
  { key: 'basisText', label: '说明' }
]

const ingestionSourceColumns = [
  { key: 'name', label: '数据源名称' },
  { key: 'type', label: '类型' },
  { key: 'statusLabel', label: '状态' },
  { key: 'lastSync', label: '最近同步' },
  { key: 'successRate', label: '成功率' },
  { key: 'failed', label: '失败数' },
  { key: 'owner', label: '负责人 / 说明' },
  { key: 'action', label: '操作' }
]

const ingestionFieldColumns = [
  { key: 'name', label: '字段名称' },
  { key: 'type', label: '字段类型' },
  { key: 'sourceField', label: '数据源字段' },
  { key: 'mapping', label: '映射方式' },
  { key: 'check', label: '校验状态' },
  { key: 'caliber', label: '口径说明' },
  { key: 'updatedAt', label: '最近更新' },
  { key: 'action', label: '操作' }
]

const ingestionHistoryColumns = [
  { key: 'time', label: '时间' },
  { key: 'source', label: '数据源' },
  { key: 'task', label: '文件 / 任务名称' },
  { key: 'total', label: '总行数' },
  { key: 'success', label: '成功行数' },
  { key: 'failed', label: '失败行数' },
  { key: 'status', label: '状态' },
  { key: 'action', label: '操作' }
]

const qualitySourceOptions = computed(() => (
  [...new Set(qualityData.alerts.map((item) => item.source))]
))

const ingestionSourceOptions = computed(() => ingestionData.dataSources.map((item) => item.name))

const filteredIngestionDataSources = computed(() => ingestionData.dataSources.filter((item) => {
  if (ingestionSourceFilter.value && item.name !== ingestionSourceFilter.value) return false
  if (ingestionStatusFilter.value && item.statusLabel !== ingestionStatusFilter.value && item.status !== ingestionStatusFilter.value) return false
  return true
}))

const ingestionOverviewGradient = computed(() => {
  let cursor = 0
  const stops = ingestionData.importOverview.segments.map((segment) => {
    const start = cursor
    cursor += Number(segment.value || 0)
    return `${segment.color} ${start}% ${cursor}%`
  })
  return `conic-gradient(${stops.join(', ')})`
})

const activeCostWorkshop = computed(() => (
  costData.workshops.find((item) => item.key === costWorkshop.value) || costData.workshops[0]
))

const activeCostWorkshopLabel = computed(() => activeCostWorkshop.value?.label || costData.workshops[0]?.label || '')
const activeCostBasisLabel = computed(() => (
  costData.basisOptions.find((item) => item.key === costBasis.value)?.label || '产量口径'
))
const activeTrendPoint = computed(() => costData.trend[costData.trend.length - 1] || {})
const costTrendDirection = computed(() => {
  const first = costTrendTotal(costData.trend[0] || {})
  const last = costTrendTotal(activeTrendPoint.value)
  if (last > first) return '小幅抬升'
  if (last < first) return '小幅回落'
  return '基本持平'
})

const filteredQualityAlerts = computed(() => qualityData.alerts.filter((item) => {
  if (qualitySeverityFilter.value && item.severity !== qualitySeverityFilter.value) return false
  if (qualityStatusFilter.value && item.status !== qualityStatusFilter.value) return false
  if (qualitySourceFilter.value && item.source !== qualitySourceFilter.value) return false
  return true
}))

function goRoute(name) {
  if (route.name !== name) {
    router.push({ name })
  }
}

function refreshFactoryView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function refreshReportsView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function refreshQualityView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function refreshCostView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function refreshIngestionView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function costTrendTotal(point) {
  return Object.values(point?.parts || {}).reduce((sum, value) => sum + Number(value || 0), 0)
}

function costSegmentHeight(point, segment) {
  const total = costTrendTotal(point)
  if (!total) return 0
  return Math.max(1.5, (Number(point.parts?.[segment.key] || 0) / total) * 100)
}

function reportStatusTone(value) {
  if (String(value).includes('失败') || String(value).includes('阻塞')) return 'danger'
  if (String(value).includes('待') || String(value).includes('未')) return 'warning'
  if (String(value).includes('已')) return 'success'
  return 'info'
}

function qualitySeverityTone(value) {
  if (value === '高') return 'danger'
  if (value === '中') return 'warning'
  if (value === '低') return 'success'
  return 'info'
}

function qualityStatusTone(value) {
  if (String(value).includes('阻塞')) return 'danger'
  if (String(value).includes('待')) return 'warning'
  if (String(value).includes('处理')) return 'processing'
  if (String(value).includes('关闭')) return 'closed'
  if (String(value).includes('已')) return 'success'
  return 'info'
}

function ingestionStatusTone(value) {
  if (String(value).includes('冲突') || String(value).includes('缺失') || String(value).includes('异常')) return 'danger'
  if (String(value).includes('待') || String(value).includes('fallback') || String(value).includes('部分')) return 'warning'
  if (String(value).includes('mixed') || String(value).includes('试跑')) return 'info'
  if (String(value).includes('通过') || String(value).includes('完成')) return 'success'
  return 'neutral'
}

function showReportPanel(panel) {
  reportInfoPanel.value = panel
}

function showCostPanel(panel) {
  costInfoPanel.value = panel
}

function showIngestionPanel(panel) {
  ingestionInfoPanel.value = panel
}

function goAdminIngestion() {
  if (canOpenAdminIngestion.value) {
    goRoute('admin-ingestion-center')
  }
}
</script>

<style scoped>
.factory-center-page {
  padding: var(--space-page);
}

.factory-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.factory-center-page__refresh,
.factory-risk-actions button {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-control);
  color: var(--text-main);
  background: #fff;
  font-weight: 800;
  cursor: pointer;
}

.factory-center-page__refresh:hover,
.factory-risk-actions button:hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.factory-center-page__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
  gap: var(--space-card);
  align-items: start;
}

.factory-line-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.factory-line-name strong,
.factory-number,
.factory-rate {
  color: var(--text-main);
  font-weight: 900;
}

.factory-number,
.factory-rate {
  font-family: var(--font-number);
  font-size: 18px;
}

.factory-sparkline {
  width: 108px;
  height: 34px;
}

.factory-risk-card {
  min-height: 100%;
}

.factory-risk-list,
.factory-risk-events,
.factory-risk-actions,
.factory-caliber-list {
  display: grid;
  gap: 9px;
}

.factory-risk-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-control);
  background: var(--neutral-soft);
}

.factory-risk-item div {
  display: grid;
  gap: 3px;
}

.factory-risk-item span,
.factory-risk-events em,
.factory-caliber-list span,
.factory-empty-state {
  color: var(--text-muted);
  font-size: 12px;
  font-style: normal;
}

.factory-risk-item strong {
  color: var(--text-main);
  font-size: 14px;
}

.factory-risk-events {
  padding-top: 4px;
}

.factory-risk-events strong {
  color: var(--text-main);
  font-size: 13px;
}

.factory-risk-events span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 13px;
}

.factory-risk-actions {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.factory-risk-actions button {
  width: 100%;
}

.factory-caliber-list {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.factory-caliber-list span {
  padding: 9px 10px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-control);
  background: var(--neutral-soft);
}

:deep(.factory-center-page .data-table-shell table) {
  min-width: 760px;
}

:deep(.factory-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.factory-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: middle;
}

:deep(.factory-center-page .data-table-shell tbody tr:last-child td) {
  border-top: 1px solid var(--primary-soft);
  background: #f7faff;
}

.ingestion-center-page {
  padding: var(--space-page);
}

:global(.cmd-page:has(.ingestion-center-page)) {
  background: #f5f8fc;
}

.ingestion-center-page__scope,
.ingestion-center-page__date,
.ingestion-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.ingestion-center-page__scope {
  padding: 7px 10px;
  border: 1px solid var(--primary-soft);
  border-radius: 8px;
  color: var(--primary);
  background: #f2f7ff;
  font-weight: 900;
}

.ingestion-control,
.ingestion-refresh,
.ingestion-row-actions button,
.ingestion-action-grid button,
.ingestion-risk-actions button,
.ingestion-mini-button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--text-main);
  background: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}

.ingestion-control {
  max-width: 148px;
}

.ingestion-refresh,
.ingestion-action-grid button:not(:disabled),
.ingestion-risk-actions button:not(:disabled),
.ingestion-row-actions button:not(:disabled),
.ingestion-mini-button:not(:disabled) {
  cursor: pointer;
}

.ingestion-refresh:hover,
.ingestion-action-grid button:not(:disabled):hover,
.ingestion-risk-actions button:not(:disabled):hover,
.ingestion-row-actions button:not(:disabled):hover,
.ingestion-mini-button:not(:disabled):hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.ingestion-control:disabled,
.ingestion-action-grid button:disabled,
.ingestion-risk-actions button:disabled,
.ingestion-row-actions button:disabled,
.ingestion-mini-button:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
}

.ingestion-center-page__top,
.ingestion-center-page__bottom {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.42fr);
  gap: var(--space-card);
  align-items: start;
}

.ingestion-center-page__side,
.ingestion-error-list {
  display: grid;
  gap: 10px;
}

.ingestion-source-cell,
.ingestion-field-cell {
  display: inline-grid;
  gap: 5px;
  align-items: start;
}

.ingestion-source-cell strong,
.ingestion-field-cell strong,
.ingestion-note-cell strong,
.ingestion-error-list strong,
.ingestion-number {
  color: var(--text-main);
  font-weight: 900;
}

.ingestion-note-cell {
  display: grid;
  gap: 5px;
  white-space: normal;
}

.ingestion-note-cell span,
.ingestion-caliber-copy,
.ingestion-error-list span,
.ingestion-overview__metrics span,
.ingestion-overview__metrics em,
.ingestion-overview__legend {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.65;
}

.ingestion-number {
  font-family: var(--font-number);
}

.ingestion-number.is-danger,
.ingestion-overview__metrics strong.is-danger {
  color: var(--danger);
}

.ingestion-overview__metrics strong.is-warning {
  color: var(--warning);
}

.ingestion-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 190px;
}

.ingestion-row-actions button,
.ingestion-mini-button {
  min-height: 30px;
  padding: 0 9px;
  font-size: 12px;
}

.ingestion-overview {
  display: grid;
  grid-template-columns: minmax(0, 0.72fr) minmax(150px, 0.42fr);
  gap: 16px;
  align-items: center;
}

.ingestion-overview__metrics {
  display: grid;
  gap: 8px;
}

.ingestion-overview__metrics article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 10px;
  align-items: baseline;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--card-border);
}

.ingestion-overview__metrics strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-size: 24px;
}

.ingestion-overview__metrics em {
  grid-column: 1 / -1;
  font-style: normal;
}

.ingestion-ring {
  display: grid;
  place-items: center;
  width: 148px;
  aspect-ratio: 1;
  margin: 0 auto;
  border-radius: 50%;
}

.ingestion-ring span {
  width: 82px;
  aspect-ratio: 1;
  border-radius: 50%;
  background: #fff;
}

.ingestion-overview__legend {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

.ingestion-overview__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ingestion-overview__legend i {
  width: 9px;
  height: 9px;
  border-radius: 3px;
}

.ingestion-error-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--neutral-soft);
}

.ingestion-error-list article div {
  display: grid;
  gap: 4px;
}

.ingestion-action-grid,
.ingestion-risk-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.ingestion-action-grid button,
.ingestion-risk-actions button {
  width: 100%;
}

.ingestion-caliber-copy {
  margin: 0;
}

:deep(.ingestion-center-page .kpi-strip) {
  grid-template-columns: repeat(6, minmax(128px, 1fr));
}

:deep(.ingestion-center-page .kpi-card) {
  min-height: 96px;
  border-radius: 8px;
  box-shadow: none;
}

:deep(.ingestion-center-page .kpi-card__label) {
  font-size: 13px;
  font-weight: 800;
}

:deep(.ingestion-center-page .kpi-card__value) {
  font-size: 34px;
}

:deep(.ingestion-center-page .section-card),
:deep(.ingestion-center-page .data-table-shell),
:deep(.ingestion-center-page .center-page__head),
:deep(.ingestion-center-page .center-page__summary) {
  border-radius: 8px;
  box-shadow: none;
}

:deep(.ingestion-center-page .data-table-shell table) {
  min-width: 1080px;
}

:deep(.ingestion-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.ingestion-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}

:deep(.ingestion-center-page .data-table-shell tbody tr.is-danger td) {
  background: #fff8f9;
}

:deep(.ingestion-center-page .data-table-shell tbody tr.is-warning td) {
  background: #fffaf2;
}

.reports-center-page {
  padding: var(--space-page);
}

:global(.cmd-page:has(.reports-center-page)) {
  background: #f5f8fc;
}

.reports-center-page__date,
.reports-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.reports-center-page__date-input,
.reports-center-page__refresh,
.reports-action-grid button,
.reports-risk-actions button,
.reports-mini-button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--text-main);
  background: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}

.reports-center-page__date-input {
  width: 148px;
}

.reports-center-page__refresh,
.reports-action-grid button:not(:disabled),
.reports-risk-actions button:not(:disabled),
.reports-mini-button:not(:disabled) {
  cursor: pointer;
}

.reports-center-page__refresh:hover,
.reports-action-grid button:not(:disabled):hover,
.reports-risk-actions button:not(:disabled):hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.reports-action-grid button:disabled,
.reports-risk-actions button:disabled,
.reports-mini-button:disabled,
.reports-center-page__date-input:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
}

.reports-center-page__overview,
.reports-center-page__bottom {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.42fr);
  gap: var(--space-card);
  align-items: stretch;
}

.reports-center-page__bottom {
  align-items: start;
}

.reports-trend {
  display: grid;
  grid-template-columns: repeat(7, minmax(54px, 1fr));
  gap: 10px;
  min-height: 190px;
  padding: 12px 8px 2px;
  border-bottom: 1px solid var(--card-border);
}

.reports-trend__item {
  display: grid;
  grid-template-rows: 1fr auto auto;
  gap: 6px;
  min-width: 0;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.reports-trend__bars {
  display: flex;
  align-items: end;
  justify-content: center;
  gap: 5px;
  min-height: 126px;
  border-bottom: 1px dashed var(--card-border);
}

.reports-trend__bar {
  display: block;
  width: 14px;
  min-height: 8px;
  border-radius: 999px 999px 3px 3px;
}

.reports-trend__bar.is-output,
.reports-trend__legend i.is-output {
  background: var(--primary);
}

.reports-trend__bar.is-delivered,
.reports-trend__legend i.is-delivered {
  background: var(--success);
}

.reports-trend__item strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-size: 17px;
  line-height: 1;
}

.reports-trend__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.reports-trend__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.reports-trend__legend i {
  width: 9px;
  height: 9px;
  border-radius: 999px;
}

.reports-delivery-summary,
.reports-risk-list {
  display: grid;
  gap: 10px;
}

.reports-delivery-summary article,
.reports-risk-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  min-height: 52px;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--neutral-soft);
}

.reports-delivery-summary span,
.reports-risk-list span,
.reports-action-copy,
.reports-caliber-copy,
.reports-failure-reason {
  color: var(--text-muted);
  font-size: 12px;
}

.reports-delivery-summary strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-size: 24px;
  line-height: 1;
}

.reports-risk-list strong {
  color: var(--text-main);
  font-size: 15px;
  line-height: 1.35;
  word-break: break-word;
}

.reports-delivery-summary small {
  color: var(--text-muted);
  font-size: 12px;
}

.reports-report-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.reports-report-name strong {
  color: var(--text-main);
  font-weight: 900;
}

.reports-failure-reason {
  display: block;
  margin-top: 5px;
  white-space: normal;
}

.reports-action-grid,
.reports-risk-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.reports-action-grid button,
.reports-risk-actions button {
  width: 100%;
}

.reports-action-copy,
.reports-caliber-copy {
  margin: 0;
  line-height: 1.7;
}

:deep(.reports-center-page .kpi-strip) {
  grid-template-columns: repeat(6, minmax(128px, 1fr));
}

:deep(.reports-center-page .kpi-card) {
  min-height: 96px;
  border-radius: 8px;
  box-shadow: none;
}

:deep(.reports-center-page .kpi-card__label) {
  font-size: 13px;
  font-weight: 800;
}

:deep(.reports-center-page .kpi-card__value) {
  font-size: 34px;
}

:deep(.reports-center-page .section-card),
:deep(.reports-center-page .data-table-shell),
:deep(.reports-center-page .center-page__head),
:deep(.reports-center-page .center-page__summary) {
  border-radius: 8px;
  box-shadow: none;
}

:deep(.reports-center-page .data-table-shell table) {
  min-width: 1120px;
}

:deep(.reports-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.reports-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}

.quality-center-page {
  padding: var(--space-page);
}

:global(.cmd-page:has(.quality-center-page)) {
  background: #f5f8fc;
}

.quality-center-page__date,
.quality-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.quality-control,
.quality-refresh,
.quality-row-actions button,
.quality-action-grid button,
.quality-risk-actions button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--text-main);
  background: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}

.quality-control {
  max-width: 148px;
}

.quality-refresh,
.quality-action-grid button:not(:disabled),
.quality-risk-actions button:not(:disabled) {
  cursor: pointer;
}

.quality-refresh:hover,
.quality-action-grid button:not(:disabled):hover,
.quality-risk-actions button:not(:disabled):hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.quality-control:disabled,
.quality-row-actions button:disabled,
.quality-action-grid button:disabled,
.quality-risk-actions button:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
}

.quality-center-page__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.42fr);
  gap: var(--space-card);
  align-items: start;
}

.quality-center-page__side,
.quality-workflow,
.quality-ai-list,
.quality-blocker-list {
  display: grid;
  gap: 10px;
}

.quality-source-cell {
  display: grid;
  gap: 5px;
  align-items: start;
}

.quality-source-cell strong,
.quality-impact-cell strong,
.quality-alert-detail strong,
.quality-workflow__item strong,
.quality-blocker-list strong {
  color: var(--text-main);
  font-weight: 900;
}

.quality-alert-detail,
.quality-impact-cell {
  display: grid;
  gap: 5px;
  white-space: normal;
}

.quality-alert-detail span,
.quality-impact-cell span,
.quality-helper-copy,
.quality-caliber-copy,
.quality-workflow__item p,
.quality-workflow__item span,
.quality-ai-list p,
.quality-blocker-list span {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.65;
}

.quality-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 210px;
}

.quality-row-actions button {
  min-height: 30px;
  padding: 0 9px;
  font-size: 12px;
}

.quality-workflow__item {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 12px;
  position: relative;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: #fff;
}

.quality-workflow__item::before {
  content: "";
  position: absolute;
  left: 38px;
  top: 52px;
  bottom: -12px;
  width: 1px;
  border-left: 1px dashed #b8c7da;
}

.quality-workflow__item:last-child::before {
  display: none;
}

.quality-workflow__mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--primary);
  background: var(--primary-soft);
  font-family: var(--font-number);
}

.quality-workflow__mark strong {
  color: var(--primary);
  font-size: 25px;
  line-height: 1;
}

.quality-workflow__item header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.quality-workflow__item p,
.quality-ai-list p,
.quality-helper-copy,
.quality-caliber-copy {
  margin: 0;
}

.quality-ai-list article,
.quality-blocker-list article {
  display: grid;
  gap: 7px;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--neutral-soft);
}

.quality-blocker-list article {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.quality-blocker-list article div {
  display: grid;
  gap: 4px;
}

.quality-center-page__bottom {
  display: grid;
  grid-template-columns: minmax(0, 0.86fr) minmax(320px, 1fr);
  gap: var(--space-card);
  align-items: start;
}

.quality-action-grid,
.quality-risk-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.quality-action-grid button,
.quality-risk-actions button {
  width: 100%;
}

:deep(.quality-center-page .kpi-strip) {
  grid-template-columns: repeat(6, minmax(128px, 1fr));
}

:deep(.quality-center-page .kpi-card) {
  min-height: 96px;
  border-radius: 8px;
  box-shadow: none;
}

:deep(.quality-center-page .kpi-card__label) {
  font-size: 13px;
  font-weight: 800;
}

:deep(.quality-center-page .kpi-card__value) {
  font-size: 34px;
}

:deep(.quality-center-page .section-card),
:deep(.quality-center-page .data-table-shell),
:deep(.quality-center-page .center-page__head),
:deep(.quality-center-page .center-page__summary) {
  border-radius: 8px;
  box-shadow: none;
}

:deep(.quality-center-page .data-table-shell table) {
  min-width: 1180px;
}

:deep(.quality-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.quality-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}

:deep(.quality-center-page .data-table-shell tbody tr.is-danger td) {
  background: #fff8f9;
}

:deep(.quality-center-page .data-table-shell tbody tr.is-warning td) {
  background: #fffaf2;
}

:deep(.quality-center-page .data-table-shell tbody tr.is-danger td:first-child) {
  box-shadow: inset 3px 0 0 var(--danger);
}

:deep(.quality-center-page .data-table-shell tbody tr.is-warning td:first-child) {
  box-shadow: inset 3px 0 0 var(--warning);
}

.cost-center-page {
  padding: var(--space-page);
}

:global(.cmd-page:has(.cost-center-page)) {
  background: #f5f8fc;
}

.cost-center-page__scope,
.cost-center-page__date,
.cost-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.cost-center-page__scope {
  padding: 7px 10px;
  border: 1px solid var(--primary-soft);
  border-radius: 8px;
  color: var(--primary);
  background: #f2f7ff;
  font-weight: 900;
}

.cost-control,
.cost-refresh,
.cost-workshop-tabs button,
.cost-basis-tabs button,
.cost-action-grid button,
.cost-primary-action {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--text-main);
  background: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}

.cost-control {
  max-width: 156px;
}

.cost-refresh,
.cost-workshop-tabs button,
.cost-basis-tabs button,
.cost-action-grid button:not(:disabled),
.cost-primary-action:not(:disabled) {
  cursor: pointer;
}

.cost-refresh:hover,
.cost-workshop-tabs button:hover,
.cost-basis-tabs button:hover,
.cost-action-grid button:not(:disabled):hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.cost-workshop-tabs button.is-active,
.cost-basis-tabs button.is-active {
  color: #fff;
  border-color: var(--primary);
  background: var(--primary);
}

.cost-control:disabled,
.cost-action-grid button:disabled,
.cost-primary-action:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
}

.cost-center-page__basis {
  display: grid;
  gap: 12px;
}

.cost-workshop-tabs,
.cost-basis-tabs {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.cost-workshop-tabs button {
  min-width: 132px;
  min-height: 48px;
  flex: 0 0 auto;
  font-size: 16px;
}

.cost-basis-tabs {
  justify-content: flex-end;
}

.cost-basis-tabs button {
  min-width: 118px;
}

.cost-center-page__overview,
.cost-center-page__middle,
.cost-center-page__bottom {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.46fr);
  gap: var(--space-card);
  align-items: stretch;
}

.cost-center-page__middle,
.cost-center-page__bottom {
  align-items: start;
}

.cost-stack-chart {
  display: grid;
  grid-template-columns: repeat(7, minmax(58px, 1fr));
  gap: 14px;
  min-height: 294px;
  padding: 12px 8px 2px;
  border-bottom: 1px solid var(--card-border);
}

.cost-stack-chart__item {
  display: grid;
  grid-template-rows: 1fr auto auto;
  gap: 8px;
  min-width: 0;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.cost-stack-chart__bar {
  display: flex;
  flex-direction: column-reverse;
  justify-content: flex-start;
  align-self: end;
  width: 48px;
  height: 230px;
  margin: 0 auto;
  overflow: hidden;
  border-radius: 5px 5px 2px 2px;
  background: #edf2f7;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.05);
}

.cost-stack-chart__bar i {
  display: block;
  width: 100%;
}

.cost-stack-chart__item strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-size: 15px;
  line-height: 1;
}

.cost-stack-chart__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding-top: 12px;
  color: var(--text-muted);
  font-size: 12px;
}

.cost-stack-chart__legend span,
.cost-composition-list article div,
.cost-item-cell {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.cost-stack-chart__legend i,
.cost-composition-list i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.cost-composition-list,
.cost-cumulative-summary,
.cost-risk-list,
.cost-trend-summary {
  display: grid;
  gap: 10px;
}

.cost-composition-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--card-border);
  color: var(--text-secondary);
}

.cost-composition-list article.is-total {
  border-bottom: 0;
  color: var(--text-main);
  font-weight: 900;
}

.cost-composition-list article.is-total i {
  background: var(--primary);
}

.cost-composition-list strong,
.cost-composition-list em,
.cost-trend-summary strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-style: normal;
}

.cost-composition-list em {
  min-width: 58px;
  text-align: right;
}

.cost-cumulative-summary {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 8px;
}

.cost-cumulative-summary span,
.cost-basis-copy,
.cost-caliber-copy,
.cost-risk-list span,
.cost-trend-summary span,
.cost-trend-summary em {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.65;
}

.cost-cumulative-summary span {
  padding: 9px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--neutral-soft);
}

.cost-primary-action {
  width: 100%;
  min-height: 48px;
  margin-top: 12px;
  color: #fff;
  background: var(--primary);
}

.cost-item-cell strong,
.cost-risk-list strong {
  color: var(--text-main);
  font-weight: 900;
}

.cost-trend-summary article,
.cost-risk-list article {
  display: grid;
  gap: 5px;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--neutral-soft);
}

.cost-risk-list article {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.cost-risk-list article div {
  display: grid;
  gap: 4px;
}

.cost-action-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.cost-action-grid button {
  width: 100%;
}

.cost-caliber-copy {
  margin: 0;
}

:deep(.cost-center-page .kpi-strip) {
  grid-template-columns: repeat(6, minmax(128px, 1fr));
}

:deep(.cost-center-page .kpi-card) {
  min-height: 96px;
  border-radius: 8px;
  box-shadow: none;
}

:deep(.cost-center-page .kpi-card__label) {
  font-size: 13px;
  font-weight: 800;
}

:deep(.cost-center-page .kpi-card__value) {
  font-size: 34px;
}

:deep(.cost-center-page .section-card),
:deep(.cost-center-page .data-table-shell),
:deep(.cost-center-page .center-page__head),
:deep(.cost-center-page .center-page__summary) {
  border-radius: 8px;
  box-shadow: none;
}

:deep(.cost-center-page .data-table-shell table) {
  min-width: 1120px;
}

:deep(.cost-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.cost-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}

:deep(.cost-center-page .data-table-shell tbody tr.is-warning td) {
  background: #fffaf2;
}

@media (max-width: 1120px) {
  .factory-center-page__layout,
  .factory-caliber-list,
  .ingestion-center-page__top,
  .ingestion-center-page__bottom,
  .reports-center-page__overview,
  .reports-center-page__bottom,
  .quality-center-page__layout,
  .quality-center-page__bottom,
  .cost-center-page__overview,
  .cost-center-page__middle,
  .cost-center-page__bottom {
    grid-template-columns: 1fr;
  }

  :deep(.ingestion-center-page .kpi-strip),
  :deep(.reports-center-page .kpi-strip),
  :deep(.quality-center-page .kpi-strip),
  :deep(.cost-center-page .kpi-strip) {
    grid-template-columns: repeat(3, minmax(160px, 1fr));
  }
}

@media (max-width: 640px) {
  :global(.app-shell:has(.factory-center-page)),
  :global(.app-shell:has(.ingestion-center-page)),
  :global(.app-shell:has(.reports-center-page)),
  :global(.app-shell:has(.quality-center-page)),
  :global(.app-shell:has(.cost-center-page)) {
    display: block;
    overflow-x: hidden;
  }

  :global(.app-shell:has(.factory-center-page) > .app-shell__aside),
  :global(.app-shell:has(.factory-center-page) > .el-container),
  :global(.app-shell:has(.factory-center-page) .app-shell__topbar),
  :global(.app-shell:has(.factory-center-page) .app-shell__main),
  :global(.app-shell:has(.ingestion-center-page) > .app-shell__aside),
  :global(.app-shell:has(.ingestion-center-page) > .el-container),
  :global(.app-shell:has(.ingestion-center-page) .app-shell__topbar),
  :global(.app-shell:has(.ingestion-center-page) .app-shell__main),
  :global(.app-shell:has(.reports-center-page) > .app-shell__aside),
  :global(.app-shell:has(.reports-center-page) > .el-container),
  :global(.app-shell:has(.reports-center-page) .app-shell__topbar),
  :global(.app-shell:has(.reports-center-page) .app-shell__main),
  :global(.app-shell:has(.quality-center-page) > .app-shell__aside),
  :global(.app-shell:has(.quality-center-page) > .el-container),
  :global(.app-shell:has(.quality-center-page) .app-shell__topbar),
  :global(.app-shell:has(.quality-center-page) .app-shell__main),
  :global(.app-shell:has(.cost-center-page) > .app-shell__aside),
  :global(.app-shell:has(.cost-center-page) > .el-container),
  :global(.app-shell:has(.cost-center-page) .app-shell__topbar),
  :global(.app-shell:has(.cost-center-page) .app-shell__main) {
    width: 100% !important;
  }

  :global(.app-shell:has(.factory-center-page) > .el-container),
  :global(.app-shell:has(.ingestion-center-page) > .el-container),
  :global(.app-shell:has(.reports-center-page) > .el-container),
  :global(.app-shell:has(.quality-center-page) > .el-container),
  :global(.app-shell:has(.cost-center-page) > .el-container) {
    min-width: 0;
  }

  :global(.app-shell:has(.factory-center-page) .app-shell__topbar),
  :global(.app-shell:has(.ingestion-center-page) .app-shell__topbar),
  :global(.app-shell:has(.reports-center-page) .app-shell__topbar),
  :global(.app-shell:has(.quality-center-page) .app-shell__topbar),
  :global(.app-shell:has(.cost-center-page) .app-shell__topbar) {
    height: auto;
    flex-wrap: wrap;
    gap: 8px;
  }

  :global(.app-shell:has(.factory-center-page) .app-shell__main),
  :global(.app-shell:has(.ingestion-center-page) .app-shell__main),
  :global(.app-shell:has(.reports-center-page) .app-shell__main),
  :global(.app-shell:has(.quality-center-page) .app-shell__main),
  :global(.app-shell:has(.cost-center-page) .app-shell__main) {
    padding: 8px;
  }

  .factory-center-page,
  .ingestion-center-page,
  .reports-center-page,
  .quality-center-page,
  .cost-center-page {
    padding: 10px;
  }

  .factory-risk-actions,
  .ingestion-action-grid,
  .ingestion-risk-actions,
  .reports-action-grid,
  .reports-risk-actions,
  .quality-action-grid,
  .quality-risk-actions,
  .cost-action-grid,
  .cost-cumulative-summary,
  :deep(.ingestion-center-page .kpi-strip),
  :deep(.reports-center-page .kpi-strip),
  :deep(.quality-center-page .kpi-strip),
  :deep(.cost-center-page .kpi-strip) {
    grid-template-columns: 1fr;
  }

  .quality-control,
  .ingestion-control,
  .cost-control {
    max-width: none;
    width: 100%;
  }

  .quality-workflow__item {
    grid-template-columns: 48px minmax(0, 1fr);
  }

  .quality-row-actions {
    min-width: 180px;
  }

  .factory-risk-events span {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .reports-trend {
    grid-template-columns: repeat(7, minmax(48px, 1fr));
    overflow-x: auto;
  }

  .cost-stack-chart {
    grid-template-columns: repeat(7, minmax(52px, 1fr));
    overflow-x: auto;
  }

  .cost-stack-chart__bar {
    width: 38px;
    height: 190px;
  }

  .reports-delivery-summary article,
  .reports-risk-list article {
    grid-template-columns: 1fr;
  }
}
</style>
