<template>
  <section class="cmd-overview-board cmd-module-page" data-module="01" data-testid="overview-dashboard">
    <header class="cmd-module-page__head cmd-overview-board__head">
      <div class="cmd-module-page__title">
        <span class="cmd-module-page__number">01</span>
        <h1>系统总览主视图</h1>
      </div>
      <div class="cmd-overview-board__tools">
        <span>数据时间：2024-05-21 10:30</span>
        <button type="button">刷新</button>
      </div>
    </header>

    <div class="cmd-overview-kpis">
      <img class="cmd-overview-kpis__visual" :src="overviewKpisImage" alt="" />
      <div class="cmd-overview-kpis__functional" aria-label="今日关键指标">
        <article v-for="kpi in kpis" :key="kpi.label" class="cmd-overview-kpi" :class="{ 'is-risk': kpi.risk }">
          <span class="cmd-overview-kpi__icon">{{ kpi.icon }}</span>
          <span>{{ kpi.label }}</span>
          <strong>{{ kpi.value }}</strong>
          <em>{{ kpi.trend }}</em>
        </article>
      </div>
    </div>

    <div class="cmd-overview-board__main">
      <section class="cmd-overview-card cmd-overview-card--asset">
        <img class="cmd-overview-card__visual" :src="overviewShortcutsImage" alt="" />
        <div class="cmd-overview-shortcuts cmd-overview-card__functional" aria-label="快捷入口">
          <button v-for="item in shortcuts" :key="item.label" type="button">
            <span>{{ item.icon }}</span>
            {{ item.label }}
          </button>
        </div>
      </section>

      <section class="cmd-overview-card cmd-overview-card--asset cmd-overview-line">
        <img class="cmd-overview-card__visual" :src="overviewFactoryLineImage" alt="" />
        <div class="cmd-overview-card__functional" aria-label="生产全景">
          <header>
            <strong>生产全景</strong>
            <span>实时</span>
          </header>
          <div class="cmd-overview-status">
            <span v-for="item in statuses" :key="item.label">
              <i aria-hidden="true" />
              <span class="cmd-overview-status__label">{{ item.label }}</span>
              <b>{{ item.state }}</b>
            </span>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import overviewFactoryLineImage from '../assets/overview-factory-line.png'
import overviewKpisImage from '../assets/overview-kpis.png'
import overviewShortcutsImage from '../assets/overview-shortcuts.png'

const kpis = [
  { icon: '产', label: '今日产量（吨）', value: '5,824', trend: '+8.6%' },
  { icon: '单', label: '订单达成率', value: '96.7%', trend: '+2.1%' },
  { icon: '质', label: '综合良品率', value: '98.2%', trend: '+1.3%' },
  { icon: '线', label: '在制产线', value: '8', trend: '运行' },
  { icon: '异', label: '异常数', value: '12', trend: '待处置', risk: true },
  { icon: '审', label: '待审数', value: '18', trend: '待确认' },
  { icon: '交', label: '已交付', value: '23', trend: '车' }
]

const shortcuts = [
  { icon: '看', label: '看板中心' },
  { icon: '审', label: '审阅中心' },
  { icon: '数', label: '数据中心' },
  { icon: '质', label: '质量中心' },
  { icon: '成', label: '成本中心' },
  { icon: '运', label: '运维中心' },
  { icon: '治', label: '治理中心' },
  { icon: 'AI', label: 'AI 大脑' }
]

const statuses = [
  { label: '数据接入', state: '正常' },
  { label: '系统性能', state: '良好' },
  { label: '任务调度', state: '正常' },
  { label: '消息服务', state: '正常' }
]
</script>
