<template>
  <svg class="xt-rolling" viewBox="0 0 640 260" role="img" aria-label="铝卷轧制线">
    <path class="xt-rolling__floor" d="M24 236H616" />

    <g class="xt-rolling__stand">
      <path d="M290 36V236M366 36V236M278 36H378" />
    </g>

    <path class="xt-rolling__strip xt-rolling__strip--thick" d="M112 202L328 130" />
    <path class="xt-rolling__strip xt-rolling__strip--thin" d="M328 130L556 202" />
    <path class="xt-rolling__flow xt-rolling__flow--thick" d="M112 202L328 130" />
    <path class="xt-rolling__flow xt-rolling__flow--thin" d="M328 130L556 202" />

    <g class="xt-rolling__spin xt-rolling__spin--slow" style="transform-origin: 112px 132px">
      <circle cx="112" cy="132" r="70" />
      <circle cx="112" cy="132" r="56" />
      <circle cx="112" cy="132" r="42" />
      <circle cx="112" cy="132" r="28" />
      <circle class="xt-rolling__core" cx="112" cy="132" r="14" />
      <path class="xt-rolling__mark" d="M112 118V62" />
    </g>

    <g class="xt-rolling__spin xt-rolling__spin--fast" style="transform-origin: 328px 92px">
      <circle cx="328" cy="92" r="30" />
      <circle class="xt-rolling__core" cx="328" cy="92" r="6" />
      <path class="xt-rolling__mark" d="M328 86V62" />
    </g>
    <g class="xt-rolling__spin xt-rolling__spin--reverse" style="transform-origin: 328px 168px">
      <circle cx="328" cy="168" r="30" />
      <circle class="xt-rolling__core" cx="328" cy="168" r="6" />
      <path class="xt-rolling__mark" d="M328 174V198" />
    </g>

    <g class="xt-rolling__spin xt-rolling__spin--slow" style="transform-origin: 556px 146px">
      <circle cx="556" cy="146" r="56" />
      <circle cx="556" cy="146" r="42" />
      <circle cx="556" cy="146" r="28" />
      <circle class="xt-rolling__core" cx="556" cy="146" r="14" />
      <path class="xt-rolling__mark" d="M556 132V90" />
    </g>
  </svg>
</template>

<style scoped>
.xt-rolling { display: block; width: 100%; height: auto; overflow: visible; color: var(--xt-primary); }
.xt-rolling circle, .xt-rolling__stand path { fill: none; stroke: currentColor; stroke-width: 1.5; }
.xt-rolling__floor { fill: none; stroke: var(--xt-border); stroke-width: 1.5; }
.xt-rolling__core { fill: var(--xt-primary-light) !important; }
.xt-rolling__mark { fill: none; stroke: currentColor; stroke-width: 3; stroke-linecap: round; }
.xt-rolling__strip { fill: none; stroke: var(--xt-primary-border); }
.xt-rolling__strip--thick { stroke-width: 7; }
.xt-rolling__strip--thin { stroke-width: 3; }
.xt-rolling__flow { fill: none; stroke: currentColor; stroke-dasharray: 18 26; animation: xt-rolling-flow 1.6s linear infinite; }
.xt-rolling__flow--thick { stroke-width: 2; animation-duration: 2.4s; }
.xt-rolling__flow--thin { stroke-width: 1.5; }
.xt-rolling__spin { animation: xt-rolling-spin 12s linear infinite; }
.xt-rolling__spin--fast { animation-duration: 3s; }
.xt-rolling__spin--reverse { animation-duration: 3s; animation-direction: reverse; }
@keyframes xt-rolling-spin { to { transform: rotate(360deg); } }
@keyframes xt-rolling-flow { to { stroke-dashoffset: -44; } }
@media (prefers-reduced-motion: reduce) {
  .xt-rolling__flow, .xt-rolling__spin { animation: none; }
}
</style>
