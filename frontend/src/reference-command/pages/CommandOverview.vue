<template>
  <div class="cmd-page">
    <CommandCanvas :modules="referenceModules" :view-models="viewModels" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

import CommandCanvas from '../components/CommandCanvas.vue'
import { referenceModules } from '../data/moduleCatalog.js'
import { adaptModuleView } from '../data/moduleAdapters.js'

const viewModels = computed(() => Object.fromEntries(
  referenceModules.map((module) => [module.moduleId, adaptModuleView(module.moduleId)])
))
</script>
