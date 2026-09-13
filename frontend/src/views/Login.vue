<template>
  <div class="login-page">
    <aside class="login-aside">
      <div class="aside-brand">
        <div class="brand-logo">LQ</div>
        <div>
          <div class="aside-title">智链问答</div>
          <div class="aside-en">LogiQA</div>
        </div>
      </div>
      <p class="aside-desc">仓配作业、异常处置、干线时效与末端送装的智能问答系统。</p>
      <ul class="aside-list">
        <li>知识库检索与可信问答</li>
        <li>知识图谱与仓配孪生</li>
        <li>异常预警与作业协同</li>
      </ul>
    </aside>
    <main class="login-main">
      <form class="login-card" @submit.prevent="doLogin">
        <h1>登录</h1>
        <p class="login-desc">请使用系统账号登录</p>
        <div class="field">
          <label class="field-label">用户名</label>
          <input class="input" v-model="username" placeholder="请输入用户名" autocomplete="username" />
        </div>
        <div class="field">
          <label class="field-label">密码</label>
          <input class="input" v-model="password" type="password" placeholder="请输入密码" autocomplete="current-password" />
        </div>
        <button class="btn btn-primary login-btn" type="submit" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
        <p class="hint">演示账号 admin / admin123</p>
        <p class="err" v-if="err">{{ err }}</p>
      </form>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { login } from '../api'

const username = ref('admin')
const password = ref('admin123')
const loading = ref(false)
const err = ref('')
const router = useRouter()
const auth = useAuthStore()

async function doLogin() {
  loading.value = true
  err.value = ''
  try {
    const r = await login(username.value, password.value)
    if (r.code === 200) { auth.setAuth(r.data); router.push('/chat') }
    else err.value = r.message
  } catch (e) { err.value = '登录失败，请检查网络' }
  loading.value = false
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(280px, 42%) 1fr;
  background: var(--bg);
}
.login-aside {
  background: #001529;
  color: rgba(255,255,255,.85);
  padding: 56px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.aside-brand { display: flex; align-items: center; gap: 14px; margin-bottom: 28px; }
.brand-logo {
  width: 44px; height: 44px; border-radius: 6px; background: #1677ff;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 15px;
}
.aside-title { font-size: 22px; font-weight: 600; color: #fff; line-height: 1.3; }
.aside-en { font-size: 13px; color: rgba(255,255,255,.45); }
.aside-desc { margin: 0 0 24px; font-size: 14px; line-height: 1.7; color: rgba(255,255,255,.65); max-width: 360px; }
.aside-list { margin: 0; padding-left: 18px; color: rgba(255,255,255,.55); font-size: 13px; line-height: 2; }
.login-main { display: flex; align-items: center; justify-content: center; padding: 40px 24px; }
.login-card { width: 100%; max-width: 360px; }
.login-card h1 { margin: 0 0 6px; font-size: 24px; font-weight: 600; color: var(--text); }
.login-desc { color: var(--text-muted); font-size: 13px; margin: 0 0 28px; }
.login-btn { width: 100%; padding: 10px; margin-top: 4px; }
.hint { color: var(--text-soft); font-size: 12px; text-align: center; margin: 16px 0 0; }
.err { color: var(--danger); font-size: 12px; text-align: center; margin: 8px 0 0; }
@media (max-width: 768px) {
  .login-page { grid-template-columns: 1fr; }
  .login-aside { padding: 28px 24px; }
  .aside-list { display: none; }
}
</style>
