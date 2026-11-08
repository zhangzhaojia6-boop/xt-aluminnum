<template>
  <svg class="xt-coil-mark" viewBox="0 0 64 64" aria-hidden="true">
    <g class="xt-coil-mark__spin">
      <circle cx="32" cy="32" r="26" />
      <circle cx="32" cy="32" r="18" />
      <circle cx="32" cy="32" r="10" />
      <path d="M32 22V6" />
    </g>
  </svg>
</template>

<style scoped>
.xt-coil-mark { display: block; width: 64px; height: 64px; margin: 0 auto; fill: none; stroke: var(--xt-primary-border); stroke-width: 1.5; stroke-linecap: round; }
.xt-coil-mark path { stroke: var(--xt-primary); stroke-width: 2.5; }
.xt-coil-mark__spin { transform-origin: 32px 32px; animation: xt-coil-spin 900ms cubic-bezier(0.16, 1, 0.3, 1) backwards; }
@keyframes xt-coil-spin { from { transform: rotate(-120deg); opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  .xt-coil-mark__spin { animation: none; }
}
</style>
