<template>
  <section class="live-process-flow" aria-label="生产流转总览">
    <header class="live-process-flow__head">
      <div>
        <span>生产流转总览</span>
        <strong>按实时聚合推进</strong>
      </div>
      <em>缺数据不计 0</em>
    </header>

    <div class="live-process-flow__rail">
      <article
        v-for="(item, index) in items"
        :key="item.key"
        class="live-process-flow__node"
        :class="`is-${item.tone}`"
      >
        <b>{{ index + 1 }}</b>
        <div class="live-process-flow__body">
          <span>{{ item.stage }}</span>
          <strong data-xt-numeric>
            <AnimatedMetricValue :value="item.valueText" />
          </strong>
          <small>{{ item.source }}</small>
        </div>
        <dl>
          <div>
            <dt>机列</dt>
            <dd>{{ item.machineCount }} 台</dd>
          </div>
          <div>
            <dt>待绑定</dt>
            <dd>{{ item.pendingMachineCount }} 台</dd>
          </div>
          <div>
            <dt>废料</dt>
            <dd>{{ item.scrapText }}</dd>
          </div>
        </dl>
      </article>
    </div>
  </section>
</template>

<script setup>
import AnimatedMetricValue from './AnimatedMetricValue.vue'

defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.live-process-flow {
  position: relative;
  z-index: 1;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 15px;
  background: transparent;

}

.live-process-flow__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 13px;
}

.live-process-flow__head span {
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
}

.live-process-flow__head strong {
  display: block;
  margin-top: 3px;
  color: var(--xt-text);
  font-size: 19px;
}

.live-process-flow__head em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 600;
}

.live-process-flow__rail {
  display: grid;
  grid-template-columns: repeat(6, minmax(150px, 1fr));
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: thin;
}

.live-process-flow__node {
  position: relative;
  min-width: 150px;
  display: grid;
  gap: 10px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 12px;
  background: transparent;
  transition: border-color 160ms ease, transform 160ms ease;
}

.live-process-flow__node::after {
  position: absolute;
  top: 50%;
  right: -11px;
  width: 12px;
  height: 1px;
  background: transparent;
  content: "";
}

.live-process-flow__node:last-child::after {
  display: none;
}

.live-process-flow__node:hover {
  border-color: var(--xt-border);
  transform: translateY(-1px);
}

.live-process-flow__node b {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: 12px;
}

.live-process-flow__body span,
.live-process-flow__body strong,
.live-process-flow__body small {
  display: block;
}

.live-process-flow__body span {
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.live-process-flow__body strong {
  margin-top: 7px;
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: clamp(20px, 2vw, 30px);
  line-height: 1;
}

.live-process-flow__body small {
  margin-top: 7px;
  color: var(--xt-text-secondary);
  font-size: 11px;
}

.live-process-flow dl {
  display: grid;
  gap: 5px;
  margin: 0;
}

.live-process-flow dl div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border-top: 1px solid var(--xt-border);
  padding-top: 5px;
}

.live-process-flow dt,
.live-process-flow dd {
  margin: 0;
  font-size: 11px;
}

.live-process-flow dt {
  color: var(--xt-text-secondary);
}

.live-process-flow dd {
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
}

.live-process-flow__node.is-warning {
  border-color: var(--xt-border);
}

.live-process-flow__node.is-warning b,
.live-process-flow__node.is-warning .live-process-flow__body strong {
  color: var(--xt-text);
}

.live-process-flow__node.is-muted {
  border-color: var(--xt-border);
}

.live-process-flow__node.is-muted b,
.live-process-flow__node.is-muted .live-process-flow__body strong {
  color: var(--xt-text-secondary);
}

@media (max-width: 1180px) {
  .live-process-flow__rail {
    grid-template-columns: repeat(3, minmax(150px, 1fr));
  }
}

@media (max-width: 720px) {
  .live-process-flow__head {
    align-items: flex-start;
    flex-direction: column;
  }

  .live-process-flow__rail {
    grid-template-columns: repeat(2, minmax(148px, 1fr));
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-process-flow__node {
    transition: none;
  }
}
</style>
