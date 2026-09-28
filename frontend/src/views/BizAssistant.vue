<template>
  <div v-if="data">
    <div class="row" style="margin-bottom:12px;gap:8px;align-items:center">
      <label class="hint">角色视角</label>
      <select class="select" v-model="expertKey" @change="load" style="max-width:260px">
        <option v-for="e in data.experts || []" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
      <button class="btn btn-primary" @click="genReport" :disabled="busy">{{ busy ? '生成中…' : '生成今日日报' }}</button>
    </div>

    <div class="card" style="margin-bottom:12px">
      <div class="card-header"><h3 class="card-title">经营简报</h3></div>
      <pre class="brief">{{ data.insights }}</pre>
    </div>

    <div class="stat-grid cols-4">
      <div class="stat" v-for="k in data.kpis" :key="k.id" :class="k.ok ? 'stat-accent' : 'stat-warn'">
        <div class="stat-val">{{ fmt(k.value) }}<small class="unit">{{ k.unit }}</small></div>
        <div class="stat-lbl">{{ k.name }}</div>
        <div class="hint">目标 {{ k.target }}{{ k.unit }}</div>
      </div>
    </div>

    <div class="card" style="margin-top:12px">
      <div class="card-header"><h3 class="card-title">待闭环风险</h3></div>
      <div v-if="!data.openRisks?.length" class="empty">暂无开放风险</div>
      <table class="tbl" v-else>
        <thead><tr><th>严重度</th><th>分类</th><th>标题</th><th>状态</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="r in data.openRisks" :key="r.id">
            <td><span class="badge" :class="sev(r.severity)">{{ r.severity }}</span></td>
            <td>{{ cat(r.category) }}</td>
            <td>{{ r.title }}</td>
            <td>{{ st(r.status) }}</td>
            <td class="muted">{{ r.createdAt }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <div v-else class="loading">{{ t('common.loading') }}</div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getBizOverview, getBizReport } from '../api'

const { t } = useI18n()
const data = ref(null)
const expertKey = ref('logistics')
const busy = ref(false)

function fmt(v) { return Number.isInteger(v) ? v : Number(v).toFixed(1) }
function sev(s) { return s === 'P0' ? 'badge-danger' : s === 'P1' ? 'badge-warning' : 'badge-primary' }
function cat(c) {
  return { warehouse: '仓配', in_transit: '在途', quality: '品质', order_delay: '延期', equipment: '设备' }[c] || c
}
function st(s) {
  return { discovered: '发现', analyzing: '分析', rectifying: '整改', closed: '闭环' }[s] || s
}

async function load() {
  try {
    const r = await getBizOverview(expertKey.value)
    data.value = r.data
    expertKey.value = r.data.expertKey || expertKey.value
  } catch (e) { data.value = { kpis: [], openRisks: [], experts: [], insights: '加载失败' } }
}
async function genReport() {
  busy.value = true
  try {
    const r = await getBizReport(expertKey.value)
    if (data.value) {
      data.value.insights = r.data.insights
      data.value.kpis = r.data.kpis
      data.value.openRisks = r.data.openRisks
    }
  } finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.brief { white-space: pre-wrap; margin: 0; font-family: inherit; line-height: 1.7; color: var(--text); }
.unit { font-size: 12px; margin-left: 4px; color: var(--text-muted); }
.stat-warn { outline: 1px solid var(--warning); }
</style>
