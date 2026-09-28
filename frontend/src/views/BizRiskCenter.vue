<template>
  <div>
    <div class="stat-grid cols-4" v-if="pack">
      <div class="stat stat-accent"><div class="stat-val">{{ pack.healthScore }}</div><div class="stat-lbl">健康分</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ pack.openCount }}</div><div class="stat-lbl">未闭环</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ pack.closedCount }}</div><div class="stat-lbl">已闭环</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ pack.closeRate }}%</div><div class="stat-lbl">闭环率</div></div>
    </div>

    <div class="row" style="margin:12px 0;gap:8px;flex-wrap:wrap">
      <select class="select" v-model="category" @change="load(true)" style="max-width:160px">
        <option value="">全部分类</option>
        <option v-for="c in cats" :key="c.id" :value="c.id">{{ c.label }}</option>
      </select>
      <select class="select" v-model="status" @change="load(true)" style="max-width:140px">
        <option value="">全部状态</option>
        <option value="discovered">发现</option>
        <option value="analyzing">分析</option>
        <option value="rectifying">整改</option>
        <option value="closed">闭环</option>
      </select>
      <select class="select" v-model="severity" @change="load(true)" style="max-width:120px">
        <option value="">全部严重度</option>
        <option>P0</option><option>P1</option><option>P2</option>
      </select>
    </div>

    <div class="card">
      <table class="tbl">
        <thead>
          <tr><th>严重度</th><th>分类</th><th>标题</th><th>责任人</th><th>状态</th><th>催办</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in list" :key="r.id">
            <td><span class="badge" :class="sev(r.severity)">{{ r.severity }}</span></td>
            <td>{{ cat(r.category) }}</td>
            <td>{{ r.title }}</td>
            <td>{{ r.owner || '—' }}</td>
            <td>{{ st(r.status) }}</td>
            <td>{{ r.urgeCount }}</td>
            <td style="white-space:nowrap">
              <button class="btn btn-ghost btn-sm" @click="open(r.id)">详情</button>
              <button class="btn btn-primary btn-sm" @click="urge(r)" :disabled="r.status==='closed'">催办</button>
            </td>
          </tr>
          <tr v-if="!list.length"><td colspan="7" class="empty">暂无风险</td></tr>
        </tbody>
      </table>
      <div class="row" style="justify-content:center;gap:10px;margin-top:10px">
        <button class="btn btn-ghost btn-sm" :disabled="page<=1" @click="page--; load()">上一页</button>
        <span class="hint">第 {{ page }} 页 · 共 {{ total }} 条</span>
        <button class="btn btn-ghost btn-sm" :disabled="page * size >= total" @click="page++; load()">下一页</button>
      </div>
    </div>

    <div class="mask" v-if="detail" @click.self="detail=null">
      <div class="card modal">
        <div class="card-header"><h3 class="card-title">风险详情</h3><button class="btn btn-ghost btn-sm" @click="detail=null">关闭</button></div>
        <div class="stages">
          <div class="stage" v-for="s in detail.stages" :key="s.key" :class="{ done: s.done }">{{ s.label }}</div>
        </div>
        <p><b>{{ detail.title }}</b> · {{ cat(detail.category) }} · {{ detail.severity }}</p>
        <p class="hint">{{ detail.summary }}</p>
        <div class="field"><label class="field-label">责任人</label><input class="input" v-model="detail.owner" /></div>
        <div class="field"><label class="field-label">治理建议</label><textarea class="input" v-model="detail.recommendation" rows="3"></textarea></div>
        <div class="field"><label class="field-label">经验沉淀</label><textarea class="input" v-model="detail.experience" rows="2"></textarea></div>
        <div class="field">
          <label class="field-label">状态</label>
          <select class="select" v-model="detail.status">
            <option value="discovered">发现</option>
            <option value="analyzing">分析</option>
            <option value="rectifying">整改</option>
            <option value="closed">闭环</option>
          </select>
        </div>
        <div class="row" style="gap:8px">
          <button class="btn btn-primary" @click="save">保存</button>
          <button class="btn btn-ghost" @click="similar">举一反三</button>
        </div>
        <p class="hint" v-if="msg">{{ msg }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { applyBizRiskSimilar, getBizRisk, listBizRisks, updateBizRisk, urgeBizRisk } from '../api'

const pack = ref(null)
const list = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const category = ref('')
const status = ref('')
const severity = ref('')
const detail = ref(null)
const msg = ref('')
const cats = [
  { id: 'warehouse', label: '仓配' },
  { id: 'in_transit', label: '在途' },
  { id: 'quality', label: '品质' },
  { id: 'order_delay', label: '延期' },
  { id: 'equipment', label: '设备' },
]
function cat(c) { return (cats.find((x) => x.id === c) || {}).label || c }
function st(s) { return { discovered: '发现', analyzing: '分析', rectifying: '整改', closed: '闭环' }[s] || s }
function sev(s) { return s === 'P0' ? 'badge-danger' : s === 'P1' ? 'badge-warning' : 'badge-primary' }

async function load(reset) {
  if (reset) page.value = 1
  const r = await listBizRisks({ category: category.value, status: status.value, severity: severity.value, page: page.value, size })
  pack.value = r.data
  list.value = r.data.list || []
  total.value = r.data.total || 0
}
async function open(id) {
  msg.value = ''
  const r = await getBizRisk(id)
  detail.value = r.data
}
async function urge(r) {
  await urgeBizRisk(r.id, '请尽快整改')
  await load()
}
async function save() {
  const d = detail.value
  await updateBizRisk(d.id, { status: d.status, owner: d.owner, recommendation: d.recommendation, experience: d.experience })
  msg.value = '已保存'
  await load()
  await open(d.id)
}
async function similar() {
  const r = await applyBizRiskSimilar(detail.value.id)
  msg.value = r.code === 200 ? `已应用到同类 ${r.data.applied} 项` : (r.message || '失败')
}
onMounted(() => load())
</script>

<style scoped>
.mask { position:fixed; inset:0; background:rgba(0,0,0,.35); z-index:20; display:flex; align-items:center; justify-content:center; padding:24px; }
.modal { width:min(640px, 100%); max-height:90vh; overflow:auto; }
.stages { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
.stage { padding:4px 10px; border-radius:99px; background: var(--surface-3); color: var(--text-muted); font-size:12px; }
.stage.done { background: var(--success-soft); color: var(--success); }
</style>
