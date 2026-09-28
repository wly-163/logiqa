<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ collapsed, 'mobile-open': mobileOpen }">
      <div class="brand">
        <div class="brand-logo">LQ</div>
        <div class="brand-text">{{ t('brand.name') }}<small>{{ t('brand.en') }}</small></div>
      </div>
      <nav class="nav-list">
        <template v-for="g in navGroups" :key="g.title">
          <div class="nav-section">{{ g.title }}</div>
          <router-link v-for="n in g.items" :key="n.to" :to="n.to" class="nav-item"
                       :class="{ active: isActive(n.to) }" @click="mobileOpen = false">
            <span class="nav-icon">{{ n.icon }}</span>
            <span class="nav-label">{{ n.label }}</span>
          </router-link>
        </template>
      </nav>
      <div class="sidebar-footer">
        <a class="nav-item" @click="toggleDark()" :title="isDark ? t('common.toLight') : t('common.toDark')">
          <span class="nav-icon">{{ isDark ? '☀️' : '🌙' }}</span>
          <span class="nav-label">{{ isDark ? t('common.light') : t('common.dark') }}</span>
        </a>
        <a class="nav-item" @click="logout" :title="t('common.logout')">
          <span class="nav-icon">🚪</span>
          <span class="nav-label">{{ t('common.logout') }}</span>
        </a>
      </div>
    </aside>

    <div class="main-area" :class="{ expanded: collapsed }">
      <header class="topbar">
        <button class="icon-btn" @click="toggleSidebar" :title="t('common.collapse')">☰</button>
        <div class="topbar-title">
          {{ title }}
          <span class="topbar-sub" v-if="sub">{{ sub }}</span>
        </div>
        <div class="topbar-spacer"></div>
        <slot name="actions" />
        <LangSwitcher />
        <div class="topbar-user" style="cursor:pointer" @click="router.push('/profile')" :title="t('common.profile')">
          <div class="avatar">{{ (auth.username || 'U')[0].toUpperCase() }}</div>
          <span>{{ auth.username }} <span class="muted">· {{ t('role.' + (auth.role || 'operator')) }}</span></span>
        </div>
      </header>
      <main class="page-body">
        <router-view />
      </main>
    </div>
    <div class="global-toast" v-if="notifyMsg">{{ notifyMsg }}</div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDark, useToggle } from '@vueuse/core'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { hasPerm } from '../utils/perm'
import LangSwitcher from '../components/LangSwitcher.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isDark = useDark()
const toggleDark = useToggle(isDark)

const collapsed = ref(localStorage.getItem('nav-collapsed') === '1')
const mobileOpen = ref(false)
function toggleSidebar() {
  if (window.innerWidth <= 768) { mobileOpen.value = !mobileOpen.value; return }
  collapsed.value = !collapsed.value
  localStorage.setItem('nav-collapsed', collapsed.value ? '1' : '0')
}

const title = computed(() => t(route.meta.titleKey || 'brand.name'))
const sub = computed(() => route.meta.subKey ? t(route.meta.subKey) : '')

watch([title, locale], () => {
  document.title = `${title.value} · LogiQA`
}, { immediate: true })

const navGroups = computed(() => {
  const biz = [
    { to: '/biz/assistant', icon: '🧭', label: t('nav.bizAssistant') },
    { to: '/biz/risk', icon: '⚠️', label: t('nav.bizRisk') },
    { to: '/biz/analysis', icon: '📈', label: t('nav.bizAnalysis') },
    { to: '/biz/capability', icon: '🗺️', label: t('nav.bizCapability') },
    { to: '/biz/ontology', icon: '🔗', label: t('nav.bizOntology') },
    { to: '/biz/agent-ops', icon: '🤖', label: t('nav.bizAgentOps') },
  ]
  const work = [
    { to: '/chat', icon: '💬', label: t('nav.chat') },
    { to: '/diagnose', icon: '🩺', label: t('nav.diagnose') },
    { to: '/operations', icon: '⚡', label: t('nav.operations') },
    { to: '/ticket', icon: '📋', label: t('nav.ticket') },
  ]
  const knowledge = [
    { to: '/documents', icon: '📄', label: t('nav.documents') },
  ]
  if (hasPerm(auth.role, 'doc:manage')) {
    knowledge.push(
      { to: '/knowledge-governance', icon: '🧭', label: t('nav.governance') },
      { to: '/knowledge-evolution', icon: '🧬', label: t('nav.evolution') },
    )
  }
  knowledge.push(
    { to: '/kg', icon: '🧠', label: t('nav.kg') },
    { to: '/kg-3d', icon: '🌐', label: t('nav.kg3d') },
  )
  const analyze = [
    { to: '/dashboard', icon: '📊', label: t('nav.dashboard') },
    { to: '/twin', icon: '🏭', label: t('nav.twin') },
  ]
  if (hasPerm(auth.role, 'metric:read')) {
    analyze.push({ to: '/prediction', icon: '🔮', label: t('nav.prediction') })
  }
  const system = []
  if (hasPerm(auth.role, 'system:config')) {
    system.push({ to: '/retrieval-debug', icon: '🔬', label: t('nav.retrieval') })
  }
  if (hasPerm(auth.role, 'system:config') || hasPerm(auth.role, 'alert:read')) {
    system.push({ to: '/admin', icon: '⚙️', label: t('nav.admin') })
  }
  return [
    { title: t('nav.biz'), items: biz },
    { title: t('nav.work'), items: work },
    { title: t('nav.knowledge'), items: knowledge },
    { title: t('nav.analyze'), items: analyze },
    { title: t('nav.system'), items: system },
  ].filter((g) => g.items.length)
})
function isActive(to) { return route.path === to || route.path.startsWith(to + '/') }

function logout() { auth.logout(); router.push('/login') }

const notifyMsg = ref('')
let notifyTimer = null
function onNotify(e) {
  notifyMsg.value = e.detail.msg
  clearTimeout(notifyTimer)
  notifyTimer = setTimeout(() => (notifyMsg.value = ''), 2600)
}
onMounted(() => window.addEventListener('app:notify', onNotify))
onUnmounted(() => window.removeEventListener('app:notify', onNotify))
</script>

<style scoped>
.global-toast {
  position: fixed; top: 18px; left: 50%; transform: translateX(-50%);
  background: var(--danger, #e74c3c); color: #fff; padding: 10px 20px;
  border-radius: 8px; font-size: 14px; z-index: 9999;
  box-shadow: 0 6px 20px rgba(0,0,0,.25);
}
</style>
