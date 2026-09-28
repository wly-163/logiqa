import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppLayout from '../views/AppLayout.vue'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', redirect: '/chat' },
      { path: 'chat', component: () => import('../views/Chat.vue'), meta: { auth: true, titleKey: 'route.chat.title', subKey: 'route.chat.sub' } },
      { path: 'profile', component: () => import('../views/Profile.vue'), meta: { auth: true, titleKey: 'route.profile.title', subKey: 'route.profile.sub' } },
      { path: 'diagnose', component: () => import('../views/Diagnose.vue'), meta: { auth: true, titleKey: 'route.diagnose.title', subKey: 'route.diagnose.sub' } },
      { path: 'operations', component: () => import('../views/OperationsCenter.vue'), meta: { auth: true, titleKey: 'route.operations.title', subKey: 'route.operations.sub' } },
      { path: 'documents', component: () => import('../views/Documents.vue'), meta: { auth: true, titleKey: 'route.documents.title', subKey: 'route.documents.sub' } },
      { path: 'knowledge-governance', component: () => import('../views/KnowledgeGovernance.vue'), meta: { auth: true, roles: ['admin', 'editor'], titleKey: 'route.governance.title', subKey: 'route.governance.sub' } },
      { path: 'knowledge-evolution', component: () => import('../views/KnowledgeEvolution.vue'), meta: { auth: true, roles: ['admin', 'editor'], titleKey: 'route.evolution.title', subKey: 'route.evolution.sub' } },
      { path: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { auth: true, titleKey: 'route.dashboard.title', subKey: 'route.dashboard.sub' } },
      { path: 'kg', component: () => import('../views/KgGraph.vue'), meta: { auth: true, titleKey: 'route.kg.title', subKey: 'route.kg.sub' } },
      { path: 'kg-3d', component: () => import('../views/KgGraph3D.vue'), meta: { auth: true, titleKey: 'route.kg3d.title', subKey: 'route.kg3d.sub' } },
      { path: 'twin', component: () => import('../views/DigitalTwin.vue'), meta: { auth: true, titleKey: 'route.twin.title', subKey: 'route.twin.sub' } },
      { path: 'ticket', component: () => import('../views/TicketLifecycle.vue'), meta: { auth: true, titleKey: 'route.ticket.title', subKey: 'route.ticket.sub' } },
      { path: 'prediction', component: () => import('../views/FaultPrediction.vue'), meta: { auth: true, roles: ['admin', 'auditor'], titleKey: 'route.prediction.title', subKey: 'route.prediction.sub' } },
      { path: 'admin', component: () => import('../views/Admin.vue'), meta: { auth: true, roles: ['admin', 'auditor'], titleKey: 'route.admin.title', subKey: 'route.admin.sub' } },
      { path: 'retrieval-debug', component: () => import('../views/RetrievalDebug.vue'), meta: { auth: true, admin: true, titleKey: 'route.retrieval.title', subKey: 'route.retrieval.sub' } },
      { path: 'biz/assistant', component: () => import('../views/BizAssistant.vue'), meta: { auth: true, titleKey: 'route.bizAssistant.title', subKey: 'route.bizAssistant.sub' } },
      { path: 'biz/risk', component: () => import('../views/BizRiskCenter.vue'), meta: { auth: true, titleKey: 'route.bizRisk.title', subKey: 'route.bizRisk.sub' } },
      { path: 'biz/analysis', component: () => import('../views/BizAnalysis.vue'), meta: { auth: true, titleKey: 'route.bizAnalysis.title', subKey: 'route.bizAnalysis.sub' } },
      { path: 'biz/capability', component: () => import('../views/BizCapability.vue'), meta: { auth: true, titleKey: 'route.bizCapability.title', subKey: 'route.bizCapability.sub' } },
      { path: 'biz/ontology', component: () => import('../views/BizOntology.vue'), meta: { auth: true, titleKey: 'route.bizOntology.title', subKey: 'route.bizOntology.sub' } },
      { path: 'biz/agent-ops', component: () => import('../views/BizAgentOps.vue'), meta: { auth: true, titleKey: 'route.bizAgentOps.title', subKey: 'route.bizAgentOps.sub' } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.token) return '/login'
  if (to.meta.admin && auth.role !== 'admin') return '/chat'
  // 细粒度角色白名单（如 /admin 允许 admin+auditor）
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) return '/chat'
})

export default router
