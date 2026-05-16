<template>
  <div class="xt-app-shell">
    <aside v-if="$slots.left" class="xt-app-shell__left">
      <slot name="left" />
    </aside>
    <div class="xt-app-shell__body">
      <header v-if="$slots.top" class="xt-app-shell__top">
        <slot name="top" />
      </header>
      <main class="xt-app-shell__main">
        <slot />
      </main>
    </div>
    <aside v-if="$slots.drawer" class="xt-app-shell__drawer">
      <slot name="drawer" />
    </aside>
  </div>
</template>

<script setup>
defineOptions({ name: 'XtAppShell' })
</script>

<style scoped>
.xt-app-shell {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.xt-app-shell__left {
  flex-shrink: 0;
  width: var(--xt-shell-sidebar-width, 220px);
  overflow-y: auto;
  border-right: 1px solid var(--xt-border-light);
}

.xt-app-shell__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.xt-app-shell__top {
  flex-shrink: 0;
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-app-shell__main {
  flex: 1;
  overflow-y: auto;
  padding: var(--xt-space-6);
}

.xt-app-shell__drawer {
  flex-shrink: 0;
  width: var(--xt-shell-drawer-width, 420px);
  overflow-y: auto;
  border-left: 1px solid var(--xt-border-light);
}
</style>
