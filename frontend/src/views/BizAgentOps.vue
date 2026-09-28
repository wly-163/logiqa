<template>
  <div>
    <div class="stat-grid cols-4" v-if="health">
      <div class="stat stat-accent"><div class="stat-val">{{ health.score }}</div><div class="stat-lbl">Agent 健康分</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ health.queueDepth }}</div><div class="stat-lbl">队列深度</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ health.agents?.length || 0 }}</div><div class="stat-lbl">Agent 数</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ health.personas?.length || 0 }}</div><div class="stat-lbl">Persona</div></div>
    </div>

    <div class="card" style="margin-top:12px">
      <div class="card-header"><h3 class="card-title">Agent 运行状态</h3></div>
      <table class="tbl">
        <thead><tr><th>Agent</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="a in health?.agents || []" :key="a.id">
            <td>{{ a.name }}</td>
            <td><span class="badge" :class="a.status==='healthy' ? 'badge-success' : 'badge-warning'">{{ a.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-top:12px">
      <div class="card-header"><h3 class="card-title">定时任务（分析 → 预警 → 推送）</h3></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin-bottom:10px">
        <input class="input" v-model="job.name" placeholder="任务名称" style="max-width:200px" />
        <select class="select" v-model="job.jobType" style="max-width:140px">
          <option value="briefing">经营日报</option>
          <option value="risk_scan">风险扫描</option>
        </select>
        <select class="select" v-model="job.frequency" style="max-width:120px">
          <option value="hourly">每小时</option>
          <option value="daily">每日</option>
        </select>
        <input class="input" v-model="job.recipientsText" placeholder="收件人，逗号分隔" style="max-width:220px" />
        <button class="btn btn-primary" @click="saveJob">保存任务</button>
      </div>
      <table class="tbl">
        <thead><tr><th>名称</th><th>类型</th><th>频率</th><th>上次</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-for="j in jobs" :key="j.id">
            <td>{{ j.name }}</td>
            <td>{{ j.jobType }}</td>
            <td>{{ j.frequency }}</td>
            <td class="muted">{{ j.lastRunAt || '—' }}</td>
            <td>{{ j.lastStatus || '—' }}</td>
            <td><button class="btn btn-primary btn-sm" @click="run(j)">立即执行</button></td>
          </tr>
          <tr v-if="!jobs.length"><td colspan="6" class="empty">尚未配置任务</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-top:12px">
      <div class="card-header"><h3 class="card-title">配置我的经营专家</h3></div>
      <div class="field"><label class="field-label">名称</label><input class="input" v-model="expert.name" placeholder="如：华东仓配专家" /></div>
      <div class="field"><label class="field-label">视角</label>
        <select class="select" v-model="expert.personaKey" style="max-width:200px">
          <option value="gm">总经理</option>
          <option value="logistics">物流</option>
          <option value="quality">品质</option>
        </select>
      </div>
      <div class="field"><label class="field-label">引用技能（指标 id，逗号分隔）</label>
        <input class="input" v-model="expert.skillsText" placeholder="otif,ticket_close,in_transit_exc" />
      </div>
      <div class="field"><label class="field-label">分析 Prompt</label>
        <textarea class="input" v-model="expert.analysisPrompt" rows="3" placeholder="关注仓配时效与在途异常，输出可执行建议"></textarea>
      </div>
      <div class="row" style="gap:12px;align-items:center">
        <label><input type="checkbox" v-model="expert.shared" /> 共享给同事</label>
        <select class="select" v-model="expert.schedule" style="max-width:140px">
          <option value="none">不定时</option>
          <option value="daily">每日</option>
        </select>
        <button class="btn btn-primary" @click="saveExpert">保存专家</button>
      </div>
      <table class="tbl" style="margin-top:12px">
        <thead><tr><th>名称</th><th>视角</th><th>共享</th><th></th></tr></thead>
        <tbody>
          <tr v-for="e in experts.filter(x => !x.builtin)" :key="e.id">
            <td>{{ e.name }}</td>
            <td>{{ e.personaKey }}</td>
            <td>{{ e.shared ? '是' : '否' }}</td>
            <td><button class="btn btn-danger btn-sm" @click="delExpert(e)">删除</button></td>
          </tr>
          <tr v-if="!experts.filter(x => !x.builtin).length"><td colspan="4" class="empty">暂无自定义专家（内置 {{ experts.filter(x=>x.builtin).length }} 个）</td></tr>
        </tbody>
      </table>
    </div>
    <p class="hint" v-if="toast">{{ toast }}</p>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { deleteBizExpert, getBizAgentHealth, listBizExperts, listBizJobs, runBizJob, saveBizExpert, saveBizJob } from '../api'

const health = ref(null)
const jobs = ref([])
const experts = ref([])
const toast = ref('')
const job = reactive({ name: '每日经营日报', jobType: 'briefing', frequency: 'daily', recipientsText: '' })
const expert = reactive({ name: '', personaKey: 'logistics', skillsText: 'otif,ticket_close', analysisPrompt: '', shared: false, schedule: 'none' })

async function load() {
  try { health.value = (await getBizAgentHealth()).data } catch (e) {}
  try { jobs.value = (await listBizJobs()).data || [] } catch (e) { jobs.value = [] }
  try { experts.value = (await listBizExperts()).data || [] } catch (e) { experts.value = [] }
}
async function saveJob() {
  const r = await saveBizJob({
    name: job.name, jobType: job.jobType, frequency: job.frequency,
    recipients: job.recipientsText.split(',').map((s) => s.trim()).filter(Boolean), enabled: true,
  })
  toast.value = r.message || '已保存'
  await load()
}
async function run(j) {
  const r = await runBizJob(j.id)
  toast.value = r.message || '已执行'
  await load()
}
async function saveExpert() {
  if (!expert.name.trim()) { toast.value = '请填写名称'; return }
  await saveBizExpert({
    name: expert.name, personaKey: expert.personaKey,
    skills: expert.skillsText.split(',').map((s) => s.trim()).filter(Boolean),
    analysisPrompt: expert.analysisPrompt, schedule: expert.schedule, shared: expert.shared,
  })
  toast.value = '专家已保存'
  expert.name = ''
  await load()
}
async function delExpert(e) {
  await deleteBizExpert(e.id)
  await load()
}
onMounted(load)
</script>
