<template>
  <div>
    <div class="stat-grid cols-4" v-if="data">
      <div class="stat stat-accent"><div class="stat-val">{{ data.skillCount }}</div><div class="stat-lbl">指标技能</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ data.modules?.length || 0 }}</div><div class="stat-lbl">产品模块</div></div>
      <div class="stat stat-accent"><div class="stat-val">{{ data.experts?.length || 0 }}</div><div class="stat-lbl">专家</div></div>
    </div>
    <div class="card" style="margin-top:12px">
      <div class="card-header"><h3 class="card-title">产品模块</h3></div>
      <div class="mod-grid">
        <div class="mod" v-for="m in data?.modules || []" :key="m.id">
          <b>{{ m.name }}</b>
          <p class="hint">{{ m.desc }}</p>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:12px">
      <div class="card-header"><h3 class="card-title">专家矩阵</h3></div>
      <table class="tbl">
        <thead><tr><th>名称</th><th>视角</th><th>来源</th></tr></thead>
        <tbody>
          <tr v-for="e in data?.experts || []" :key="e.id">
            <td>{{ e.name }}</td>
            <td>{{ e.focus || e.personaKey }}</td>
            <td>{{ e.builtin ? '内置' : '自定义' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card" style="margin-top:12px">
      <div class="card-header"><h3 class="card-title">技能目录</h3></div>
      <table class="tbl">
        <thead><tr><th>技能</th><th>分类</th><th>目标</th><th>口径</th></tr></thead>
        <tbody>
          <tr v-for="s in data?.skills || []" :key="s.id">
            <td>{{ s.name }}</td>
            <td>{{ s.category }}</td>
            <td>{{ s.target }}{{ s.unit }}</td>
            <td class="hint">{{ s.definition }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getBizCapability } from '../api'
const data = ref(null)
onMounted(async () => {
  try { data.value = (await getBizCapability()).data } catch (e) { data.value = { modules: [], skills: [], experts: [] } }
})
</script>

<style scoped>
.mod-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap:10px; }
.mod { padding:12px; border:1px solid var(--border); border-radius: var(--radius); background: var(--surface-2); }
</style>
