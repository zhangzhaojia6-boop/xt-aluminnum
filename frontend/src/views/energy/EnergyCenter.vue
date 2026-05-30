<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>能耗中心</h1>
      </div>
      <div class="header-actions">
        <el-date-picker v-model="filters.business_date" type="date" value-format="YYYY-MM-DD" />
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <el-card class="panel">
      <ReferenceDataTable :data="rows" stripe>
        <el-table-column prop="business_date" label="业务日期" width="120" />
        <el-table-column prop="workshop_code" label="车间" width="120" />
        <el-table-column prop="shift_code" label="班次" width="120" />
        <el-table-column prop="electricity_value" label="电耗" width="120" />
        <el-table-column prop="gas_value" label="气耗" width="120" />
        <el-table-column prop="water_value" label="水耗" width="120" />
        <el-table-column prop="total_energy" label="总能耗" width="120" />
        <el-table-column prop="output_weight" label="产量" width="120" />
        <el-table-column prop="energy_per_ton" label="单吨能耗" width="120" />
      </ReferenceDataTable>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'

import { fetchEnergySummary } from '../../api/energy'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'

const filters = reactive({
  business_date: dayjs().format('YYYY-MM-DD')
})
const rows = ref([])

async function load() {
  rows.value = await fetchEnergySummary({ business_date: filters.business_date })
}

onMounted(load)
</script>
