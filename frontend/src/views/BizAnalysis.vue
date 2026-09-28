<template>
  <div class="split">
    <div class="card chat">
      <div class="card-header"><h3 class="card-title">DataAgent 问数</h3></div>
      <div class="log">
        <div v-for="(m, i) in msgs" :key="i" class="msg" :class="m.role">
          <div class="bubble">{{ m.text }}</div>
        </div>
      </div>
      <div class="row" style="gap:8px">
        <input class="input" v-model="q" placeholder="如：准时达效率、在途异常、未闭环风险" @keyup.enter="ask" />
        <button class="btn btn-primary" @click="ask" :disabled="busy || !q.trim()">提问</button>
      </div>
    </div>
    <div>
      <div class="card" v-if="rows.length">
        <div class="card-header"><h3 class="card-title">指标结果</h3></div>
        <table class="tbl">
          <thead><tr><th>指标</th><th>当前</th><th>目标</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td>{{ r.name }}</td>
              <td>{{ r.value }}{{ r.unit }}</td>
              <td>{{ r.target }}{{ r.unit }}</td>
              <td><span class="badge" :class="r.ok ? 'badge-success' : 'badge-danger'">{{ r.ok ? '达标' : '关注' }}</span></td>
            </tr>
          </tbody>
        </table>
        <p class="hint" v-for="r in rows" :key="'d'+r.id">{{ r.name }}：{{ r.definition }}</p>
      </div>
      <div class="card" style="margin-top:12px">
        <div class="card-header"><h3 class="card-title">指标技能库（{{ catalog.length }}）</h3></div>
        <div class="chips">
          <button class="chip" v-for="s in catalog" :key="s.id" @click="q = s.name; ask()">{{ s.name }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { askBizDataAgent, getBizMetrics } from '../api'

const q = ref('准时达和未闭环风险怎么样')
const busy = ref(false)
const msgs = ref([{ role: 'ai', text: 'DataAgent 已就绪。可按指标名称或业务口径提问。' }])
const rows = ref([])
const catalog = ref([])

async function ask() {
  const query = q.value.trim()
  if (!query) return
  msgs.value.push({ role: 'user', text: query })
  busy.value = true
  try {
    const r = await askBizDataAgent(query)
    const data = r.data || {}
    rows.value = data.rows || []
    const summary = (data.rows || []).map((x) => `${x.name} ${x.value}${x.unit}`).join('；') || '无匹配指标'
    msgs.value.push({ role: 'ai', text: summary + '\n' + (data.note || '') })
  } catch (e) {
    msgs.value.push({ role: 'ai', text: '问数失败' })
  } finally { busy.value = false }
}
onMounted(async () => {
  try { catalog.value = (await getBizMetrics()).data || [] } catch (e) { catalog.value = [] }
})
</script>

<style scoped>
.split { display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
@media (max-width: 960px) { .split { grid-template-columns: 1fr; } }
.chat { display:flex; flex-direction:column; min-height:420px; }
.log { flex:1; overflow:auto; display:flex; flex-direction:column; gap:8px; margin-bottom:10px; }
.msg { display:flex; } .msg.user { justify-content:flex-end; }
.bubble { max-width:90%; padding:8px 12px; border-radius:8px; background: var(--surface-3); white-space:pre-wrap; }
.msg.user .bubble { background: var(--primary-soft); }
.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip { border:1px solid var(--border); background: var(--surface); border-radius:99px; padding:4px 10px; cursor:pointer; }
</style>
