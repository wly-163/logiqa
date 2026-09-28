<template>
  <div class="split">
    <div class="card">
      <div class="card-header"><h3 class="card-title">供应链风险本体</h3></div>
      <div ref="graphEl" class="graph" v-if="graph.nodes?.length"></div>
      <div v-else class="empty">提问后展示关联图谱（无三元组时请先在知识图谱抽取）</div>
    </div>
    <div class="card chat">
      <div class="card-header"><h3 class="card-title">本体 Agent</h3></div>
      <div class="log">
        <div v-for="(m, i) in msgs" :key="i" class="msg" :class="m.role">
          <div class="bubble">{{ m.text }}</div>
        </div>
      </div>
      <div class="row" style="gap:8px">
        <input class="input" v-model="q" placeholder="如：华东仓在途异常归因" @keyup.enter="ask" />
        <button class="btn btn-primary" @click="ask" :disabled="busy">提问</button>
      </div>
    </div>
  </div>
  <div class="card" style="margin-top:12px" v-if="steps.length">
    <div class="card-header"><h3 class="card-title">推理链路（{{ last?.toolsUsed || 0 }} tools）</h3></div>
    <table class="tbl">
      <thead><tr><th>步</th><th>主体</th><th>关系</th><th>客体</th></tr></thead>
      <tbody>
        <tr v-for="s in steps" :key="s.step"><td>{{ s.step }}</td><td>{{ s.subject }}</td><td>{{ s.relation }}</td><td>{{ s.object }}</td></tr>
      </tbody>
    </table>
  </div>
  <div class="card" style="margin-top:12px" v-if="dist.length">
    <div class="card-header"><h3 class="card-title">节点风险分布</h3></div>
    <table class="tbl">
      <thead><tr><th>节点</th><th>开放风险</th><th>P0</th></tr></thead>
      <tbody>
        <tr v-for="d in dist" :key="d.node"><td>{{ d.node }}</td><td>{{ d.openRisks }}</td><td>{{ d.p0 }}</td></tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref } from 'vue'
import * as echarts from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { askBizOntology } from '../api'

echarts.use([GraphChart, TooltipComponent, CanvasRenderer])

const q = ref('仓配作业异常归因')
const busy = ref(false)
const msgs = ref([{ role: 'ai', text: '本体 Agent 已就绪。将结合知识图谱给出推理步骤。' }])
const graph = ref({ nodes: [], links: [] })
const steps = ref([])
const dist = ref([])
const last = ref(null)
const graphEl = ref(null)
let chart = null

function render() {
  if (!graphEl.value || !graph.value.nodes?.length) return
  if (chart) { chart.dispose(); chart = null }
  chart = echarts.init(graphEl.value)
  chart.setOption({
    tooltip: { formatter: (p) => p.dataType === 'edge' ? `${p.data.source} —${p.data.value}→ ${p.data.target}` : p.data.name },
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      data: graph.value.nodes, links: graph.value.links,
      label: { show: true, fontSize: 11 },
      force: { repulsion: 160, edgeLength: [50, 120] },
    }],
  })
}

async function ask() {
  const query = q.value.trim()
  if (!query) return
  msgs.value.push({ role: 'user', text: query })
  busy.value = true
  try {
    const r = await askBizOntology(query)
    last.value = r.data
    graph.value = r.data.graph || { nodes: [], links: [] }
    steps.value = r.data.steps || []
    dist.value = r.data.distribution || []
    msgs.value.push({ role: 'ai', text: r.data.answer || '无结果' })
    await nextTick()
    render()
  } catch (e) {
    msgs.value.push({ role: 'ai', text: '归因失败' })
  } finally { busy.value = false }
}
onBeforeUnmount(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.split { display:grid; grid-template-columns: 1.2fr 1fr; gap:12px; }
@media (max-width: 960px) { .split { grid-template-columns: 1fr; } }
.graph { height: 420px; }
.chat { display:flex; flex-direction:column; min-height:420px; }
.log { flex:1; overflow:auto; display:flex; flex-direction:column; gap:8px; margin-bottom:10px; }
.msg { display:flex; } .msg.user { justify-content:flex-end; }
.bubble { max-width:90%; padding:8px 12px; border-radius:8px; background: var(--surface-3); white-space:pre-wrap; }
.msg.user .bubble { background: var(--primary-soft); }
</style>
