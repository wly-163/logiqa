<template>
  <div>
    <div class="card" style="margin-bottom:12px">
      <p class="hint" style="margin:0 0 10px">这是知识三元组的立体视图（同一份知识图谱数据），不是仓库地图。仓内位置请到「仓配孪生」。</p>
      <div class="row" style="gap:8px">
        <input class="input" v-model="entity" placeholder="搜索实体（如：冷链 / AGV / 爆仓，空=全量）" @keyup.enter="loadGraph" style="flex:1" />
        <button class="btn btn-primary" @click="loadGraph" :disabled="loading">{{ loading ? '加载中…' : '🔍 搜索' }}</button>
      </div>
      <div class="row" style="gap:6px;margin-top:10px;flex-wrap:wrap" v-if="relationTypes.length">
        <button class="btn btn-sm" :class="relFilter === '' ? 'btn-primary' : 'btn-ghost'" @click="relFilter = ''">全部关系</button>
        <button class="btn btn-sm" :class="relFilter === r ? 'btn-primary' : 'btn-ghost'" v-for="r in relationTypes" :key="r" @click="relFilter = r">{{ r }}</button>
      </div>
    </div>

    <div class="graph-container" ref="containerRef">
      <canvas ref="canvasRef"></canvas>
      <button class="fs-btn" @click="toggleFullscreen" :title="isFs ? '退出全屏(Esc)' : '全屏'">{{ isFs ? '⤫' : '⛶' }}</button>
      <div v-if="!graph" class="graph-hint">点击「搜索」加载知识图谱</div>
      <div class="graph-info" v-if="graph">
        <span class="badge badge-neutral">{{ visibleGraph.nodes?.length || 0 }} 节点</span>
        <span class="badge badge-neutral">{{ visibleGraph.links?.length || 0 }} 条边</span>
        <span class="badge badge-neutral" v-if="relFilter">关系：{{ relFilter }}</span>
      </div>
      <div class="graph-legend" v-if="graph">
        <span><i class="dot" style="background:#3498db"></i>仓配节点/设备</span>
        <span><i class="dot" style="background:#e74c3c"></i>异常</span>
        <span><i class="dot" style="background:#2ecc71"></i>作业/处置</span>
        <span><i class="dot" style="background:#9b59b6"></i>规程/单据</span>
        <span><i class="dot" style="background:#f39c12"></i>参数/SLA</span>
        <span><i class="dot" style="background:#1abc9c"></i>货品/库位</span>
      </div>
    </div>

    <div class="card" v-if="selected">
      <div class="src-head">节点详情</div>
      <div class="cause">
        <b>{{ selected.label || selected.name }}</b>
        <div class="cause-line">类型：{{ selected.type }} · 相连 {{ selected.outDegree || 0 }} 条</div>
      </div>
      <div v-if="selected.edges?.length" style="margin-top:8px">
        <div class="muted" style="font-size:12px;margin-bottom:4px">关系</div>
        <div class="cause" v-for="(e, i) in selected.edges" :key="i" style="font-size:13px">{{ e }}</div>
      </div>
      <div class="row" style="margin-top:10px;gap:8px" v-if="selected.twinDeviceId">
        <button class="btn btn-primary btn-sm" @click="goTwin(selected.twinDeviceId)">在仓配孪生中定位</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getKgGraph, getStationOverview } from '../api'
import * as THREE from 'three'

const route = useRoute()
const router = useRouter()
const entity = ref('')
const graph = ref(null)
const loading = ref(false)
const selected = ref(null)
const relFilter = ref('')
const twinDevices = ref([])

const containerRef = ref(null)
const canvasRef = ref(null)
let animId = null
let dragCleanup = null
let currentRenderer = null
let currentCamera = null
const isFs = ref(false)

const DIM_LABEL = {
  equipment: '仓配节点/设备',
  fault: '异常',
  action: '作业/处置',
  rule: '规程/单据',
  metric: '参数/SLA',
  component: '货品/库位',
  default: '其它',
}

const relationTypes = computed(() => {
  const s = new Set()
  for (const l of graph.value?.links || []) {
    if (l.value) s.add(l.value)
  }
  return [...s].sort()
})

const visibleGraph = computed(() => {
  const nodes = graph.value?.nodes || []
  const links = graph.value?.links || []
  if (!relFilter.value) return { nodes, links }
  const kept = links.filter((l) => l.value === relFilter.value)
  const ids = new Set()
  for (const l of kept) {
    ids.add(typeof l.source === 'object' ? l.source.id : l.source)
    ids.add(typeof l.target === 'object' ? l.target.id : l.target)
  }
  return { nodes: nodes.filter((n) => ids.has(n.id)), links: kept }
})

function classify(raw) {
  const s = (raw || '').toString()
  if (/[0-9.]+\s*(℃|°C|%|小时|h|km|件|箱|吨|天)/.test(s) ||
      /(不低于|不高于|不超过|至少|以上|以下|约为|左右|≤|≥|阈值|SLA|周转)/.test(s)) return 'metric'
  if (/(爆仓|断链|延误|破损|拒收|错发|错配|积压|冲突|料不齐|超温|宕机|故障|异常|泄漏|盘亏|碰撞)/.test(s)) return 'fault'
  if (/(票|单|制度|规程|监护|许可|措施|复核|交接|作业单|运单)/.test(s)) return 'rule'
  if (/^(用|检查|测量|拣货|复核|发运|装车|调拨|配送|安装|验货|签收|巡视|操作|执行|申请|判断|进行|做好|持续|严禁|不得|禁止|由|每)/.test(s)
      || /(处置|应急换仓|隔离|上报)/.test(s)) return 'action'
  if (/(仓库|月台|RDC|CDC|FDC|WMS|TMS|AGV|叉车|干线|冷链|一盘货|VMI|货架|波次|立体库|分拣)/.test(s)) return 'equipment'
  return 'component'
}

function matchTwin(name) {
  const n = (name || '').trim()
  if (!n) return null
  return twinDevices.value.find((d) => d.kgEntity === n || d.name === n)
    || twinDevices.value.find((d) => (d.kgEntity && (d.kgEntity.includes(n) || n.includes(d.kgEntity)))
      || (d.name && (d.name.includes(n) || n.includes(d.name))))
}

function goTwin(deviceId) {
  router.push({ path: '/twin', query: { device: deviceId } })
}

function toggleFullscreen() {
  const el = containerRef.value
  if (!el) return
  if (document.fullscreenElement) document.exitFullscreen()
  else el.requestFullscreen()
}
function onFsChange() {
  isFs.value = !!document.fullscreenElement
  const w = containerRef.value?.clientWidth || window.innerWidth
  const h = containerRef.value?.clientHeight || window.innerHeight
  if (currentRenderer) { currentRenderer.setSize(w, h); currentCamera.aspect = w / h; currentCamera.updateProjectionMatrix() }
}

async function loadGraph() {
  loading.value = true
  try {
    const r = await getKgGraph(entity.value, 2000)
    graph.value = r.data || null
    await nextTick()
    render3D()
  } catch { /* silent */ } finally { loading.value = false }
}

function makeTextSprite(text, { width = 128, height = 32, fill = '#fde68a', font = '12px sans-serif' } = {}) {
  const lc = document.createElement('canvas')
  lc.width = width
  lc.height = height
  const ctx = lc.getContext('2d')
  ctx.fillStyle = 'rgba(0,0,0,0.55)'
  ctx.fillRect(0, 4, width, height - 8)
  ctx.fillStyle = fill
  ctx.font = font
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText((text || '').slice(0, 10), width / 2, height / 2)
  const tex = new THREE.CanvasTexture(lc)
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false })
  const sprite = new THREE.Sprite(mat)
  sprite.scale.set(width / 42, height / 42, 1)
  sprite.renderOrder = 20
  return sprite
}

// 简易 3D 力导向图（基于 Three.js）
function render3D() {
  cleanup()
  if (!canvasRef.value || !visibleGraph.value?.nodes?.length) return
  const container = containerRef.value
  const W = container.clientWidth || 600
  const H = container.clientHeight || 500

  try {
      const scene = new THREE.Scene()
      scene.background = new THREE.Color(0x1a1a2e)
      const camera = new THREE.PerspectiveCamera(60, W / H, 0.1, 1000)
      currentCamera = camera
      camera.position.set(25, 22, 25)
      const renderer = new THREE.WebGLRenderer({ canvas: canvasRef.value, antialias: true })
      currentRenderer = renderer
      renderer.setSize(W, H)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

      // 光源
      const ambient = new THREE.AmbientLight(0x404060)
      scene.add(ambient)
      const dir = new THREE.DirectionalLight(0xffffff, 0.8)
      dir.position.set(10, 20, 10)
      scene.add(dir)

      // 布局
      const nodes = visibleGraph.value.nodes || []
      const links = visibleGraph.value.links || []
      const N = nodes.length
      const positions = new Array(N).fill(0).map(() => ({
        x: (Math.random() - 0.5) * 12,
        y: (Math.random() - 0.5) * 12,
        z: (Math.random() - 0.5) * 12,
        vx: 0, vy: 0, vz: 0,
      }))
      // 拖动交互状态 + 渲染同步（simulate 与拖动共用，避免位置/连线不一致）
      const raycaster = new THREE.Raycaster()
      const ndcMouse = new THREE.Vector2()
      const dragPlane = new THREE.Plane()
      const dragHit = new THREE.Vector3()
      let dragIdx = -1
      let downXY = { x: 0, y: 0 }
      const edgeLabels = []
      const syncRender = () => {
        for (let i = 0; i < N; i++) {
          spheres[i]?.position.set(positions[i].x, positions[i].y, positions[i].z)
          labels[i]?.position.set(positions[i].x, positions[i].y + 1.0, positions[i].z)
        }
        while (lineGroup.children.length) lineGroup.remove(lineGroup.children[0])
        for (let k = 0; k < linkPairs.length; k++) {
          const { si, ti } = linkPairs[k]
          const pts = [new THREE.Vector3(positions[si].x, positions[si].y, positions[si].z),
                       new THREE.Vector3(positions[ti].x, positions[ti].y, positions[ti].z)]
          lineGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat))
          if (edgeLabels[k]) {
            edgeLabels[k].position.set(
              (positions[si].x + positions[ti].x) / 2,
              (positions[si].y + positions[ti].y) / 2 + 0.35,
              (positions[si].z + positions[ti].z) / 2,
            )
          }
        }
      }

      const DIM_COLORS = {
        equipment: 0x3498db,
        fault:     0xe74c3c,
        action:    0x2ecc71,
        rule:      0x9b59b6,
        metric:    0xf39c12,
        component: 0x1abc9c,
        default:   0x95a5a6,
      }
      const spheres = []
      for (let i = 0; i < N; i++) {
        const color = DIM_COLORS[classify(nodes[i]?.name)] ?? DIM_COLORS.default
        // 节点大小按 symbolSize 映射（数据 28~36 → 0.7~1.3 可视区间）
        const sym = nodes[i]?.symbolSize || 28
        const size = Math.min(1.3, Math.max(0.7, sym / 28))
        const geo = new THREE.SphereGeometry(size, 18, 18)
        const mat = new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.45 })
        const mesh = new THREE.Mesh(geo, mat)
        mesh.position.set(positions[i].x, positions[i].y, positions[i].z)
        scene.add(mesh)
        spheres.push(mesh)
      }

      // 连线
      const lineMat = new THREE.LineBasicMaterial({ color: 0x555577, transparent: true, opacity: 0.4 })
      const lineGroup = new THREE.Group()
      const linkPairs = []
      const showEdgeText = links.length <= 48 || !!relFilter.value
      for (const l of links || []) {
        const si = nodes.findIndex(n => n.id === l.source || n.id === l.source?.id)
        const ti = nodes.findIndex(n => n.id === l.target || n.id === l.target?.id)
        if (si >= 0 && ti >= 0) {
          linkPairs.push({ si, ti, rel: l.value || '' })
          const pts = [new THREE.Vector3(positions[si].x, positions[si].y, positions[si].z),
                       new THREE.Vector3(positions[ti].x, positions[ti].y, positions[ti].z)]
          const geo = new THREE.BufferGeometry().setFromPoints(pts)
          const line = new THREE.Line(geo, lineMat)
          lineGroup.add(line)
          if (showEdgeText && l.value) {
            const spr = makeTextSprite(l.value)
            spr.position.set(
              (positions[si].x + positions[ti].x) / 2,
              (positions[si].y + positions[ti].y) / 2 + 0.35,
              (positions[si].z + positions[ti].z) / 2,
            )
            scene.add(spr)
            edgeLabels.push(spr)
          } else {
            edgeLabels.push(null)
          }
        }
      }
      scene.add(lineGroup)

      // 标签 Sprite（每个标签独立 canvas，避免共用 ctx 导致 CanvasTexture 串台成同一文字）
      const labels = []
      for (let i = 0; i < Math.min(N, 50); i++) {
        const label = (nodes[i]?.name || nodes[i]?.label || '')?.slice(0, 8)
        if (!label) continue
        const lc = document.createElement('canvas')
        lc.width = 128; lc.height = 64
        const ctx = lc.getContext('2d')
        ctx.fillStyle = '#ffffff'; ctx.font = '14px sans-serif'; ctx.textAlign = 'center'
        ctx.fillText(label, 64, 36)
        const tex = new THREE.CanvasTexture(lc)
        const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0.8 })
        const sprite = new THREE.Sprite(mat)
        sprite.position.set(positions[i].x, positions[i].y + 1.0, positions[i].z)
        sprite.scale.set(3, 1.5, 1)
        scene.add(sprite)
        labels.push(sprite)
      }

      // 简单力导向模拟
      let iter = 0
      const L0 = 3, REPULSE = 18, SPRING_K = 0.06, GRAVITY = 0.012, BOUND = N > 120 ? 24 : 14
      function simulate() {
        if (iter++ > 120) return
        const damp = Math.max(0.35, 0.88 - iter * 0.004)   // 降温收敛
        for (let i = 0; i < N; i++) {
          if (i === dragIdx) continue
          let fx = 0, fy = 0, fz = 0
          // 电荷斥力（带 cutoff：距离>12 忽略，省算力 + 防节点四散）
          for (let j = 0; j < N; j++) {
            if (i === j) continue
            const dx = positions[i].x - positions[j].x
            const dy = positions[i].y - positions[j].y
            const dz = positions[i].z - positions[j].z
            const d2 = dx * dx + dy * dy + dz * dz
            if (d2 > 144) continue
            const d = Math.sqrt(d2) + 0.1
            const f = REPULSE / (d * d)
            fx += f * dx / d; fy += f * dy / d; fz += f * dz / d
          }
          // 弹簧力（带平衡长度 L0：边长趋近 L0=4，而非越拉越长）
          for (const { si, ti } of linkPairs) {
            if (si === i || ti === i) {
              const j = si === i ? ti : si
              const dx = positions[j].x - positions[i].x
              const dy = positions[j].y - positions[i].y
              const dz = positions[j].z - positions[i].z
              const d = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.1
              const f = (d - L0) * SPRING_K
              fx += f * dx / d; fy += f * dy / d; fz += f * dz / d
            }
          }
          // 向心力（拉回原点，防飞出视野）
          fx -= positions[i].x * GRAVITY
          fy -= positions[i].y * GRAVITY
          fz -= positions[i].z * GRAVITY
          positions[i].vx = (positions[i].vx + fx) * damp
          positions[i].vy = (positions[i].vy + fy) * damp
          positions[i].vz = (positions[i].vz + fz) * damp
          // 位置边界约束（防飞出相机视野）
          positions[i].x = Math.max(-BOUND, Math.min(BOUND, positions[i].x + positions[i].vx))
          positions[i].y = Math.max(-BOUND, Math.min(BOUND, positions[i].y + positions[i].vy))
          positions[i].z = Math.max(-BOUND, Math.min(BOUND, positions[i].z + positions[i].vz))
        }
        syncRender()
        if (iter < 100) setTimeout(simulate, 30)
      }
      simulate()

      // 节点拖动（raycaster 命中 → 投影平面跟随鼠标 → syncRender 实时刷新）
      const dom = renderer.domElement
      const setMouse = (e) => {
        const r = dom.getBoundingClientRect()
        ndcMouse.x = ((e.clientX - r.left) / r.width) * 2 - 1
        ndcMouse.y = -((e.clientY - r.top) / r.height) * 2 + 1
      }
      const onDown = (e) => {
        downXY = { x: e.clientX, y: e.clientY }
        setMouse(e)
        raycaster.setFromCamera(ndcMouse, camera)
        const hits = raycaster.intersectObjects(spheres)
        if (hits.length) {
          dragIdx = spheres.indexOf(hits[0].object)
          const camDir = new THREE.Vector3()
          camera.getWorldDirection(camDir)
          dragPlane.setFromNormalAndCoplanarPoint(camDir, hits[0].point)
          dom.style.cursor = 'grabbing'
          e.preventDefault()
        }
      }
      const onMove = (e) => {
        setMouse(e)
        if (dragIdx >= 0) {
          raycaster.setFromCamera(ndcMouse, camera)
          if (raycaster.ray.intersectPlane(dragPlane, dragHit)) {
            positions[dragIdx].x = Math.max(-BOUND, Math.min(BOUND, dragHit.x))
            positions[dragIdx].y = Math.max(-BOUND, Math.min(BOUND, dragHit.y))
            positions[dragIdx].z = Math.max(-BOUND, Math.min(BOUND, dragHit.z))
            positions[dragIdx].vx = 0; positions[dragIdx].vy = 0; positions[dragIdx].vz = 0
            syncRender()
          }
        } else {
          raycaster.setFromCamera(ndcMouse, camera)
          dom.style.cursor = raycaster.intersectObjects(spheres).length ? 'grab' : 'default'
        }
      }
      const onUp = (e) => {
        const moved = Math.hypot((e?.clientX || 0) - downXY.x, (e?.clientY || 0) - downXY.y)
        if (moved < 6 && dragIdx >= 0) {
          const node = nodes[dragIdx]
          const name = node?.name || node?.id || ''
          const edges = linkPairs
            .filter((p) => p.si === dragIdx || p.ti === dragIdx)
            .map((p) => {
              const other = p.si === dragIdx ? nodes[p.ti] : nodes[p.si]
              const dir = p.si === dragIdx ? '→' : '←'
              return `${dir} ${p.rel || '相关'} ${other?.name || ''}`
            })
          const twin = matchTwin(name)
          selected.value = {
            name,
            label: name,
            type: DIM_LABEL[classify(name)] || '其它',
            outDegree: edges.length,
            edges,
            twinDeviceId: twin?.deviceId || '',
          }
        }
        dragIdx = -1
        dom.style.cursor = 'default'
      }
      dom.addEventListener('pointerdown', onDown)
      dom.addEventListener('pointermove', onMove)
      dom.addEventListener('pointerup', onUp)
      dragCleanup = () => { dom.removeEventListener('pointerdown', onDown); dom.removeEventListener('pointermove', onMove); dom.removeEventListener('pointerup', onUp) }

      // 旋转动画：先左右逆时针 10 圈，再上下 10 圈，循环；拖动时暂停
      let phase = 1, phaseAngle = 0
      const RADIUS = 30, Y0 = 22, SPIN_SPEED = 0.0025
      const TEN_LOOPS = Math.PI * 20
      function animate() {
        if (dragIdx < 0) {
          phaseAngle += SPIN_SPEED
          if (phaseAngle >= TEN_LOOPS) { phaseAngle = 0; phase = phase === 1 ? 2 : 1 }
          if (phase === 1) {
            camera.position.set(RADIUS * Math.cos(phaseAngle), Y0, RADIUS * Math.sin(phaseAngle))
          } else {
            camera.position.set(0, RADIUS * Math.sin(phaseAngle), RADIUS * Math.cos(phaseAngle))
          }
        }
        camera.lookAt(0, 0, 0)
        renderer.render(scene, camera)
        animId = requestAnimationFrame(animate)
      }
      animate()
  } catch (e) { console.error('3D render error:', e) }
}

function cleanup() {
  if (animId) { cancelAnimationFrame(animId); animId = null }
  if (dragCleanup) { dragCleanup(); dragCleanup = null }
  if (currentRenderer) {
    currentRenderer.dispose()
    currentRenderer = null
  }
}

watch(relFilter, () => { nextTick(() => render3D()) })

onMounted(async () => {
  if (route.query.entity) entity.value = String(route.query.entity)
  try {
    const ov = await getStationOverview('rdc-east-demo')
    twinDevices.value = ov.data?.devices || []
  } catch { twinDevices.value = [] }
  loadGraph()
  document.addEventListener('fullscreenchange', onFsChange)
})
onUnmounted(() => { cleanup(); document.removeEventListener('fullscreenchange', onFsChange) })
</script>

<style scoped>
.graph-container { position: relative; background: var(--surface-2); border-radius: var(--radius); min-height: 500px; overflow: hidden; }
.graph-container canvas { display: block; width: 100%; height: 100%; }
.graph-hint { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 14px; }
.graph-info { position: absolute; top: 50px; right: 10px; display: flex; gap: 6px; }
.fs-btn { position: absolute; top: 10px; right: 10px; z-index: 10; width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(0,0,0,.55); color: #fff; border: 1px solid rgba(255,255,255,.25); cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; }
.fs-btn:hover { background: rgba(0,0,0,.75); }
.graph-legend { position: absolute; left: 10px; bottom: 10px; display: flex; flex-wrap: wrap; gap: 6px 12px; padding: 8px 10px; background: rgba(0,0,0,.5); border: 1px solid rgba(255,255,255,.15); border-radius: var(--radius-sm); color: #e6e6e6; font-size: 12px; max-width: 60%; }
.graph-legend span { display: inline-flex; align-items: center; gap: 4px; }
.graph-legend .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
</style>