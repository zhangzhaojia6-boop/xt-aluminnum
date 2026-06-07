<template>
  <span class="xt-process-icon" :class="`is-${stage}`" aria-hidden="true">
    <svg viewBox="0 0 112 76" focusable="false">
      <ellipse class="xt-process-icon__shadow" cx="56" cy="61" rx="40" ry="9" />

      <g v-if="stage === 'casting'">
        <polygon class="xt-process-icon__top" points="22 33 37 24 53 32 38 42" />
        <polygon class="xt-process-icon__body" points="22 33 38 42 38 55 22 46" />
        <polygon class="xt-process-icon__dark" points="38 42 53 32 53 45 38 55" />
        <polygon class="xt-process-icon__top" points="41 25 56 16 72 24 57 34" />
        <polygon class="xt-process-icon__body" points="41 25 57 34 57 47 41 38" />
        <polygon class="xt-process-icon__dark" points="57 34 72 24 72 37 57 47" />
        <polygon class="xt-process-icon__top" points="58 37 73 28 89 36 74 46" />
        <polygon class="xt-process-icon__body" points="58 37 74 46 74 59 58 50" />
        <polygon class="xt-process-icon__dark" points="74 46 89 36 89 49 74 59" />
      </g>

      <g v-else-if="stage === 'cast-roll'">
        <polygon class="xt-process-icon__base" points="18 55 39 44 91 49 70 62" />
        <rect class="xt-process-icon__frame" x="31" y="25" width="52" height="25" rx="6" />
        <ellipse class="xt-process-icon__roll" cx="44" cy="38" rx="14" ry="17" />
        <ellipse class="xt-process-icon__roll" cx="69" cy="38" rx="14" ry="17" />
        <path class="xt-process-icon__line" d="M18 40h20M82 40h15" />
        <path class="xt-process-icon__line" d="M45 20h23" />
      </g>

      <g v-else-if="stage === 'hot-roll'">
        <polygon class="xt-process-icon__base" points="19 56 39 43 93 48 72 62" />
        <rect class="xt-process-icon__frame" x="25" y="20" width="54" height="36" rx="6" />
        <rect class="xt-process-icon__hot" x="33" y="29" width="38" height="12" rx="3" />
        <path class="xt-process-icon__line" d="M31 49h42" />
        <path class="xt-process-icon__line" d="M83 32h12M83 42h12" />
      </g>

      <g v-else-if="stage === 'cold-roll'">
        <polygon class="xt-process-icon__base" points="17 57 40 43 94 48 70 63" />
        <circle class="xt-process-icon__coil" cx="33" cy="38" r="17" />
        <circle class="xt-process-icon__inner" cx="33" cy="38" r="8" />
        <rect class="xt-process-icon__frame" x="51" y="25" width="34" height="26" rx="5" />
        <ellipse class="xt-process-icon__roll" cx="61" cy="38" rx="8" ry="11" />
        <ellipse class="xt-process-icon__roll" cx="76" cy="38" rx="8" ry="11" />
        <path class="xt-process-icon__line" d="M40 38h13" />
      </g>

      <g v-else-if="stage === 'finish'">
        <polygon class="xt-process-icon__base" points="17 57 40 43 95 48 71 63" />
        <rect class="xt-process-icon__frame" x="24" y="24" width="65" height="27" rx="6" />
        <circle class="xt-process-icon__roll" cx="38" cy="38" r="9" />
        <circle class="xt-process-icon__roll" cx="58" cy="38" r="9" />
        <circle class="xt-process-icon__roll" cx="78" cy="38" r="9" />
        <path class="xt-process-icon__line" d="M27 21h58M30 54h52" />
      </g>

      <g v-else>
        <polygon class="xt-process-icon__base" points="18 58 42 43 94 50 70 65" />
        <polygon class="xt-process-icon__top" points="28 31 56 15 85 31 57 47" />
        <polygon class="xt-process-icon__body" points="28 31 57 47 57 62 28 46" />
        <polygon class="xt-process-icon__dark" points="57 47 85 31 85 46 57 62" />
        <rect class="xt-process-icon__door" x="49" y="45" width="15" height="17" rx="2" />
        <path class="xt-process-icon__line" d="M36 35l21 12 20-12" />
      </g>
    </svg>
  </span>
</template>

<script setup>
defineProps({
  stage: {
    type: String,
    required: true,
  },
})
</script>

<style scoped>
.xt-process-icon {
  display: inline-grid;
  place-items: center;
}

.xt-process-icon svg {
  width: 100%;
  height: 100%;
}

.xt-process-icon__shadow {
  fill: rgba(0, 10, 22, 0.62);
}

.xt-process-icon__base {
  fill: rgba(6, 37, 67, 0.92);
  stroke: rgba(82, 176, 255, 0.48);
  stroke-width: 1.5;
}

.xt-process-icon__top,
.xt-process-icon__body,
.xt-process-icon__dark,
.xt-process-icon__frame,
.xt-process-icon__roll,
.xt-process-icon__coil,
.xt-process-icon__door {
  stroke-linejoin: round;
  stroke-width: 2;
}

.xt-process-icon__top {
  fill: rgba(36, 143, 224, 0.88);
  stroke: rgba(156, 225, 255, 0.9);
}

.xt-process-icon__body,
.xt-process-icon__frame {
  fill: rgba(11, 87, 143, 0.88);
  stroke: rgba(98, 196, 255, 0.88);
}

.xt-process-icon__dark,
.xt-process-icon__door {
  fill: rgba(5, 45, 83, 0.96);
  stroke: rgba(65, 156, 230, 0.74);
}

.xt-process-icon__roll,
.xt-process-icon__coil {
  fill: rgba(8, 62, 112, 0.96);
  stroke: rgba(140, 216, 255, 0.92);
}

.xt-process-icon__inner {
  fill: rgba(1, 19, 35, 0.84);
  stroke: rgba(100, 187, 255, 0.72);
  stroke-width: 1.5;
}

.xt-process-icon__hot {
  fill: rgba(245, 155, 45, 0.94);
  stroke: rgba(255, 214, 128, 0.92);
  stroke-width: 2;
}

.xt-process-icon__line {
  fill: none;
  stroke: rgba(165, 229, 255, 0.72);
  stroke-linecap: round;
  stroke-width: 2;
}
</style>
