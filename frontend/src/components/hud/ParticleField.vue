<template>
  <div class="xt-hud-particles" aria-hidden="true">
    <div class="xt-hud-particles__fallback" data-testid="hud-particles-fallback"></div>
  </div>
</template>

<style scoped>
.xt-hud-particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.xt-hud-particles__fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background:
    radial-gradient(120% 80% at 70% 20%, rgba(94, 184, 255, 0.14), transparent 60%),
    radial-gradient(90% 70% at 20% 90%, rgba(37, 99, 235, 0.12), transparent 60%),
    linear-gradient(rgba(94, 184, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(94, 184, 255, 0.04) 1px, transparent 1px),
    linear-gradient(180deg, #04101f 0%, #020812 100%);
  background-size: auto, auto, 34px 34px, 34px 34px, auto;
}

@media (prefers-reduced-motion: reduce) {
  .xt-hud-particles__fallback {
    transition: none;
  }
}
</style>
