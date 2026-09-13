<template>
  <div class="login-page">
    <aside class="login-aside">
      <div class="aside-brand">
        <div class="brand-logo">LQ</div>
        <div>
          <div class="aside-title">{{ t('brand.name') }}</div>
          <div class="aside-en">{{ t('brand.en') }}</div>
        </div>
      </div>
      <p class="aside-desc">{{ t('login.desc') }}</p>
      <ul class="aside-list">
        <li>{{ t('login.f1') }}</li>
        <li>{{ t('login.f2') }}</li>
        <li>{{ t('login.f3') }}</li>
      </ul>
    </aside>
    <main class="login-main">
      <LangSwitcher class="login-lang" />
      <form class="login-card" @submit.prevent="doLogin">
        <h1>{{ t('login.title') }}</h1>
        <p class="login-desc">{{ t('login.hint') }}</p>
        <div class="field">
          <label class="field-label">{{ t('login.username') }}</label>
          <input class="input" v-model="username" :placeholder="t('login.userPh')" autocomplete="username" />
        </div>
        <div class="field">
          <label class="field-label">{{ t('login.password') }}</label>
          <input class="input" v-model="password" type="password" :placeholder="t('login.passPh')" autocomplete="current-password" />
        </div>
        <button class="btn btn-primary login-btn" type="submit" :disabled="loading">
          {{ loading ? t('login.submitting') : t('login.title') }}
        </button>
        <p class="hint">{{ t('login.demo') }}</p>
        <p class="err" v-if="err">{{ err }}</p>
      </form>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { login } from '../api'
import LangSwitcher from '../components/LangSwitcher.vue'

const { t } = useI18n()
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
  } catch (e) { err.value = t('login.fail') }
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
.login-main { position: relative; display: flex; align-items: center; justify-content: center; padding: 40px 24px; }
.login-lang { position: absolute; top: 20px; right: 24px; }
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
