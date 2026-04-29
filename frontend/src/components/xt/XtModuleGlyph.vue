<template>
  <div class="xt-module-glyph" :class="[`xt-module-glyph--${resolvedVariant}`, `is-${status}`, { 'is-compact': compact }]">
    <svg viewBox="0 0 160 112" role="img" :aria-label="ariaLabel">
      <path class="xt-module-glyph__deck" d="M25 77 78 49l57 30-53 28-57-30Z" />
      <path class="xt-module-glyph__deck-side" d="M25 77v9l57 30v-9L25 77Z" />
      <path class="xt-module-glyph__deck-side xt-module-glyph__deck-side--right" d="M135 79v9l-53 28v-9l53-28Z" />

      <g v-if="shape === 'flow'" class="xt-module-glyph__shape">
        <path d="M42 62h24l12-9h37" />
        <path d="M62 82h34l14-10h20" />
        <circle cx="42" cy="62" r="6" />
        <circle cx="78" cy="53" r="6" />
        <circle cx="130" cy="72" r="6" />
      </g>
      <g v-else-if="shape === 'entry'" class="xt-module-glyph__shape">
        <rect x="50" y="37" width="47" height="56" rx="6" />
        <path d="M60 51h27M60 64h21M60 77h30" />
        <path class="xt-module-glyph__accent" d="M100 76h20l8 6-8 6h-20Z" />
      </g>
      <g v-else-if="shape === 'ingestion'" class="xt-module-glyph__shape">
        <circle cx="80" cy="60" r="24" />
        <path d="M34 48h23M34 73h23M103 48h24M103 73h24" />
        <circle cx="34" cy="48" r="5" />
        <circle cx="127" cy="73" r="5" />
      </g>
      <g v-else-if="shape === 'triage'" class="xt-module-glyph__shape">
        <rect x="44" y="39" width="72" height="52" rx="7" />
        <path d="M57 54h30M57 67h43M57 80h24" />
        <path class="xt-module-glyph__accent" d="M104 53h16v28h-16Z" />
      </g>
      <g v-else-if="shape === 'report'" class="xt-module-glyph__shape">
        <path d="M44 82h72" />
        <rect x="50" y="46" width="16" height="34" rx="3" />
        <rect x="72" y="36" width="16" height="44" rx="3" />
        <rect x="94" y="55" width="16" height="25" rx="3" />
        <path class="xt-module-glyph__accent" d="M116 45h14l8 8-8 8h-14Z" />
      </g>
      <g v-else-if="shape === 'brain'" class="xt-module-glyph__shape">
        <circle cx="80" cy="59" r="23" />
        <path d="M58 59h44M80 37v44M65 44l30 30M95 44 65 74" />
        <circle class="xt-module-glyph__accent" cx="80" cy="59" r="7" />
      </g>
      <g v-else-if="shape === 'matrix'" class="xt-module-glyph__shape">
        <rect x="45" y="39" width="22" height="18" rx="3" />
        <rect x="71" y="39" width="22" height="18" rx="3" />
        <rect x="97" y="39" width="22" height="18" rx="3" />
        <rect x="45" y="62" width="22" height="18" rx="3" />
        <rect x="71" y="62" width="22" height="18" rx="3" />
        <rect x="97" y="62" width="22" height="18" rx="3" />
      </g>
      <g v-else class="xt-module-glyph__shape">
        <path d="M43 74h74M50 57h22M86 57h24" />
        <rect x="50" y="40" width="28" height="34" rx="4" />
        <rect x="86" y="44" width="28" height="30" rx="4" />
        <circle class="xt-module-glyph__accent" cx="122" cy="58" r="7" />
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtModuleGlyph' })

const props = defineProps({
  moduleId: {
    type: String,
    default: ''
  },
  variant: {
    type: String,
    default: ''
  },
  status: {
    type: String,
    default: 'normal'
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const resolvedVariant = computed(() => props.variant || props.moduleId || 'overview')
const shape = computed(() => {
  const key = resolvedVariant.value
  if (['overview', 'factory'].includes(key)) return 'flow'
  if (['entry'].includes(key)) return 'entry'
  if (['ingestion'].includes(key)) return 'ingestion'
  if (['review', 'quality'].includes(key)) return 'triage'
  if (['report', 'cost'].includes(key)) return 'report'
  if (['brain', 'ai'].includes(key)) return 'brain'
  if (['ops', 'governance', 'master'].includes(key)) return 'matrix'
  return 'default'
})
const ariaLabel = computed(() => `${resolvedVariant.value} 模块图形`)
</script>

<style scoped>
.xt-module-glyph {
  position: relative;
  width: 100%;
  min-height: 104px;
  color: var(--xt-primary);
}

.xt-module-glyph.is-compact {
  min-height: 76px;
}

.xt-module-glyph svg {
  width: 100%;
  height: 100%;
  min-height: inherit;
  overflow: visible;
}

.xt-module-glyph__deck {
  fill: var(--xt-bg-panel-soft);
  stroke: var(--xt-border);
  stroke-width: 1.4;
}

.xt-module-glyph__deck-side {
  fill: color-mix(in srgb, var(--xt-primary) 8%, var(--xt-bg-panel-muted));
  stroke: var(--xt-border);
  stroke-width: 1.2;
}

.xt-module-glyph__deck-side--right {
  fill: color-mix(in srgb, var(--xt-accent) 8%, var(--xt-bg-panel-muted));
}

.xt-module-glyph__shape {
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 4;
}

.xt-module-glyph__shape rect,
.xt-module-glyph__shape circle:not(.xt-module-glyph__accent) {
  fill: var(--xt-bg-panel);
}

.xt-module-glyph__accent {
  fill: var(--xt-accent);
  stroke: var(--xt-accent);
}

.xt-module-glyph.is-warning {
  color: var(--xt-warning);
}

.xt-module-glyph.is-danger {
  color: var(--xt-danger);
}

.xt-module-glyph.is-success {
  color: var(--xt-success);
}
</style>
