<template>
  <div class="xt-workshop-glyph" :class="[`xt-workshop-glyph--${resolvedType}`, { 'is-active': active, 'is-compact': compact }]">
    <svg viewBox="0 0 168 112" role="img" :aria-label="ariaLabel">
      <path class="xt-workshop-glyph__base" d="M22 78 82 46l64 34-60 32-64-34Z" />
      <path class="xt-workshop-glyph__side" d="M22 78v9l64 34v-9L22 78Z" />
      <path class="xt-workshop-glyph__side xt-workshop-glyph__side--right" d="M146 80v9l-60 32v-9l60-32Z" />

      <g v-if="shape === 'casting'" class="xt-workshop-glyph__machine">
        <path d="M45 68h30V38H45v30Z" />
        <path class="xt-workshop-glyph__heat" d="M55 64c5-11 10-11 15 0" />
        <path d="M82 65h38M104 57l16 8-16 8" />
        <rect x="118" y="58" width="18" height="14" rx="3" />
      </g>
      <g v-else-if="shape === 'hotRoll'" class="xt-workshop-glyph__machine">
        <rect class="xt-workshop-glyph__slab" x="42" y="59" width="84" height="16" rx="4" />
        <circle cx="64" cy="52" r="10" />
        <circle cx="96" cy="52" r="10" />
        <path d="M40 80h92" />
      </g>
      <g v-else-if="shape === 'coldRoll'" class="xt-workshop-glyph__machine">
        <circle cx="62" cy="63" r="20" />
        <circle cx="62" cy="63" r="9" />
        <path d="M84 63h42M103 50v26" />
        <circle cx="103" cy="50" r="8" />
        <circle cx="103" cy="76" r="8" />
      </g>
      <g v-else-if="shape === 'leveling'" class="xt-workshop-glyph__machine">
        <path d="M42 61c14-12 28 12 42 0s28 12 42 0" />
        <path d="M42 77h84" />
        <circle cx="55" cy="50" r="6" />
        <circle cx="86" cy="50" r="6" />
        <circle cx="117" cy="50" r="6" />
      </g>
      <g v-else-if="shape === 'annealing'" class="xt-workshop-glyph__machine">
        <rect x="42" y="47" width="84" height="34" rx="6" />
        <path class="xt-workshop-glyph__heat" d="M56 72c4-11 10-11 14 0M78 72c4-11 10-11 14 0M100 72c4-11 10-11 14 0" />
        <path d="M33 64h20M115 64h20" />
      </g>
      <g v-else-if="shape === 'inventory'" class="xt-workshop-glyph__machine">
        <path d="M44 76h28V61H44v15ZM74 76h28V61H74v15ZM104 76h28V61h-28v15Z" />
        <path d="M59 60h28V45H59v15ZM89 60h28V45H89v15Z" />
      </g>
      <g v-else-if="shape === 'flow'" class="xt-workshop-glyph__machine">
        <path d="M38 64h22l12-12h24l12 12h22" />
        <path d="M60 78h24l10-8h36" />
        <circle cx="38" cy="64" r="6" />
        <circle cx="72" cy="52" r="6" />
        <circle cx="108" cy="64" r="6" />
        <circle cx="130" cy="78" r="6" />
      </g>
      <g v-else class="xt-workshop-glyph__machine">
        <rect x="44" y="52" width="80" height="22" rx="5" />
        <path d="M54 45h60M64 81h40M78 45v36" />
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtWorkshopGlyph' })

const props = defineProps({
  workshopType: {
    type: String,
    default: 'casting'
  },
  active: {
    type: Boolean,
    default: false
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const resolvedType = computed(() => props.workshopType || 'casting')
const shape = computed(() => {
  const type = resolvedType.value
  if (type === 'casting') return 'casting'
  if (type === 'hot_roll') return 'hotRoll'
  if (type === 'cold_roll') return 'coldRoll'
  if (type === 'leveling') return 'leveling'
  if (['online_annealing'].includes(type)) return 'annealing'
  if (['inventory'].includes(type)) return 'inventory'
  if (['cross_workshop_flow'].includes(type)) return 'flow'
  return 'finishing'
})
const ariaLabel = computed(() => `${resolvedType.value} 车间图形`)
</script>

<style scoped>
.xt-workshop-glyph {
  width: 100%;
  min-height: 100px;
  color: var(--xt-primary);
}

.xt-workshop-glyph.is-compact {
  min-height: 72px;
}

.xt-workshop-glyph svg {
  width: 100%;
  height: 100%;
  min-height: inherit;
  overflow: visible;
}

.xt-workshop-glyph__base {
  fill: var(--xt-bg-panel-soft);
  stroke: var(--xt-border);
  stroke-width: 1.4;
}

.xt-workshop-glyph__side {
  fill: color-mix(in srgb, var(--xt-primary) 8%, var(--xt-bg-panel-muted));
  stroke: var(--xt-border);
  stroke-width: 1.2;
}

.xt-workshop-glyph__side--right {
  fill: color-mix(in srgb, var(--xt-accent) 8%, var(--xt-bg-panel-muted));
}

.xt-workshop-glyph__machine {
  fill: var(--xt-bg-panel);
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 4;
}

.xt-workshop-glyph__heat,
.xt-workshop-glyph__slab {
  stroke: var(--xt-accent);
}

.xt-workshop-glyph__slab {
  fill: var(--xt-accent-light);
}

.xt-workshop-glyph.is-active {
  color: var(--xt-primary-hover);
}
</style>
