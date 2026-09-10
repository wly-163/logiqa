/**
 * 设备几何体工厂 — 每种 device.model 都有专属造型
 *
 * 不用 glTF/glb（避免外部资源依赖），全部用 Three.js 原生几何体组合。
 * 返回 Group，每台设备可整体定位/着色/拾取。
 *
 * 设计原则：
 *   1. 视觉辨识度 — AGV/立体库/月台/叉车/冷链库一眼可辨
 *   2. 风险可视化 — riskColor 仅在指定组（外壳/标识面）上体现，金属本体保持工业色
 *   3. 性能 — 共享材质（同一颜色/粗糙度共用 Material 实例）
 */
import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'

// ========== 共享材质（按需懒加载，全场景共享） ==========
const _matCache = new Map()
function getMaterial(key, factory) {
  if (!_matCache.has(key)) _matCache.set(key, factory())
  return _matCache.get(key)
}

function metalMat(color, opts = {}) {
  return getMaterial(`metal-${color}-${JSON.stringify(opts)}`, () =>
    new THREE.MeshStandardMaterial({
      color,
      metalness: opts.metalness ?? 0.7,
      roughness: opts.roughness ?? 0.35,
      emissive: opts.emissive ?? 0x000000,
      emissiveIntensity: opts.emissiveIntensity ?? 0.0,
    })
  )
}

function concreteMat() {
  // 水泥底座/地面
  return getMaterial('concrete', () =>
    new THREE.MeshStandardMaterial({ color: 0x9AA0A6, metalness: 0.05, roughness: 0.9 })
  )
}

function grassMat() {
  // 园区外绿地
  return getMaterial('grass', () =>
    new THREE.MeshStandardMaterial({ color: 0x3E5C3A, metalness: 0.0, roughness: 0.95 })
  )
}

function buildingMat() {
  // 仓控室/设备间墙体
  return getMaterial('building', () =>
    new THREE.MeshStandardMaterial({ color: 0xC8C2B4, metalness: 0.05, roughness: 0.85 })
  )
}

function roofMat() {
  // 屋顶（深灰）
  return getMaterial('roof', () =>
    new THREE.MeshStandardMaterial({ color: 0x4D4D4D, metalness: 0.2, roughness: 0.7 })
  )
}

function roadMat() {
  // 巡检道路
  return getMaterial('road', () =>
    new THREE.MeshStandardMaterial({ color: 0x555A5F, metalness: 0.1, roughness: 0.8 })
  )
}

function fenceMat() {
  // 围栏（铁艺）
  return getMaterial('fence', () =>
    new THREE.MeshStandardMaterial({ color: 0x8B8E91, metalness: 0.6, roughness: 0.5, transparent: true, opacity: 0.7 })
  )
}

function cartonMat(color) {
  return getMaterial(`carton-${color}`, () =>
    new THREE.MeshStandardMaterial({ color, metalness: 0.08, roughness: 0.85 })
  )
}

// ========== 通用辅助：圆角金属底座 ==========
function buildBase(width, depth, height = 0.2) {
  const base = new THREE.Mesh(
    new RoundedBoxGeometry(width, height, depth, 2, 0.04),
    concreteMat()
  )
  base.position.y = height / 2
  base.castShadow = true
  base.receiveShadow = true
  return base
}

// ========== 立体库货架 ==========
function buildAsrs(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  const frame = metalMat(0x4A5568, { metalness: 0.55, roughness: 0.45 })
  const pallet = metalMat(riskColor, { metalness: 0.2, roughness: 0.7, emissive: riskColor, emissiveIntensity: 0.04 })
  g.add(buildBase(w * 1.05, d * 1.05, 0.12))
  const postW = Math.max(0.08, Math.min(w, d) * 0.03)
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      const post = new THREE.Mesh(new THREE.BoxGeometry(postW, h, postW), frame)
      post.position.set(sx * (w / 2 - 0.12), h / 2, sz * (d / 2 - 0.12))
      post.castShadow = true
      g.add(post)
    }
  }
  const levels = Math.max(3, Math.round(h / 1.7))
  for (let i = 1; i < levels; i++) {
    const y = (i / levels) * h
    const beam = new THREE.Mesh(new THREE.BoxGeometry(w * 0.96, 0.07, d * 0.96), frame)
    beam.position.y = y
    g.add(beam)
    const cols = 3
    const rows = 2
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < rows; r++) {
        const boxH = Math.min(0.65, (h / levels) * 0.5)
        const box = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.22, boxH, d * 0.32),
          c + r === 0 ? pallet : cartonMat(0xC9A66B)
        )
        box.position.set(-w * 0.3 + c * w * 0.3, y + boxH / 2 + 0.04, -d * 0.2 + r * d * 0.4)
        box.castShadow = true
        g.add(box)
      }
    }
  }
  return g
}

// ========== AGV ==========
function buildAgv(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  const body = new THREE.Mesh(
    new RoundedBoxGeometry(w, h * 0.45, d, 2, 0.08),
    metalMat(riskColor, { metalness: 0.45, roughness: 0.4, emissive: riskColor, emissiveIntensity: 0.08 })
  )
  body.position.y = h * 0.35
  body.castShadow = true
  g.add(body)
  const cargo = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.7, h * 0.35, d * 0.7),
    cartonMat(0xC4A574)
  )
  cargo.position.y = h * 0.72
  cargo.castShadow = true
  g.add(cargo)
  const wheelMat = metalMat(0x222222, { metalness: 0.2, roughness: 0.7 })
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      const wh = new THREE.Mesh(new THREE.CylinderGeometry(h * 0.14, h * 0.14, 0.12, 12), wheelMat)
      wh.rotation.z = Math.PI / 2
      wh.position.set(sx * w * 0.38, h * 0.14, sz * d * 0.32)
      g.add(wh)
    }
  }
  const dome = new THREE.Mesh(
    new THREE.SphereGeometry(h * 0.12, 12, 8),
    metalMat(0x1A1A1A, { metalness: 0.8, roughness: 0.2 })
  )
  dome.position.set(0, h * 0.55, d * 0.32)
  g.add(dome)
  return g
}

// ========== 叉车充电桩 ==========
function buildCharger(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  g.add(buildBase(w * 1.4, d * 1.4, 0.1))
  const pole = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.35, h, d * 0.25),
    metalMat(0x2C3E50, { metalness: 0.4, roughness: 0.5 })
  )
  pole.position.y = h / 2
  pole.castShadow = true
  g.add(pole)
  const head = new THREE.Mesh(
    new RoundedBoxGeometry(w * 0.7, h * 0.35, d * 0.5, 2, 0.04),
    metalMat(riskColor, { metalness: 0.3, roughness: 0.45, emissive: riskColor, emissiveIntensity: 0.12 })
  )
  head.position.y = h * 0.85
  head.castShadow = true
  g.add(head)
  return g
}

// ========== 叉车 ==========
function buildForklift(size, riskColor) {
  const [w, h, d] = size
  if (h <= 1.6 && w <= 1.2) return buildCharger(size, riskColor)
  const g = new THREE.Group()
  const body = new THREE.Mesh(
    new RoundedBoxGeometry(w, h * 0.45, d * 0.55, 2, 0.06),
    metalMat(riskColor, { metalness: 0.35, roughness: 0.5, emissive: riskColor, emissiveIntensity: 0.06 })
  )
  body.position.set(0, h * 0.35, -d * 0.08)
  body.castShadow = true
  g.add(body)
  const cabin = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.7, h * 0.4, d * 0.35),
    metalMat(0x1A5276, { metalness: 0.2, roughness: 0.4 })
  )
  cabin.position.set(0, h * 0.72, -d * 0.12)
  cabin.castShadow = true
  g.add(cabin)
  const mast = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.12, h, 0.08),
    metalMat(0x555555, { metalness: 0.7, roughness: 0.3 })
  )
  mast.position.set(0, h / 2, d * 0.28)
  mast.castShadow = true
  g.add(mast)
  for (const sx of [-0.22, 0.22]) {
    const fork = new THREE.Mesh(
      new THREE.BoxGeometry(w * 0.12, 0.06, d * 0.55),
      metalMat(0x888888, { metalness: 0.8, roughness: 0.25 })
    )
    fork.position.set(sx * w, 0.18, d * 0.22)
    fork.castShadow = true
    g.add(fork)
  }
  const wheelMat = metalMat(0x222222, { metalness: 0.15, roughness: 0.75 })
  for (const sz of [-0.2, 0.15]) {
    for (const sx of [-1, 1]) {
      const wh = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.14, 12), wheelMat)
      wh.rotation.z = Math.PI / 2
      wh.position.set(sx * w * 0.42, 0.18, sz * d)
      g.add(wh)
    }
  }
  return g
}

// ========== 装卸月台 ==========
function buildDock(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  const plat = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.35, d), concreteMat())
  plat.position.y = h * 0.175
  plat.castShadow = true
  plat.receiveShadow = true
  g.add(plat)
  const wall = new THREE.Mesh(
    new THREE.BoxGeometry(w, h * 0.85, 0.12),
    metalMat(0x7B8A99, { metalness: 0.35, roughness: 0.6 })
  )
  wall.position.set(0, h * 0.55, -d * 0.4)
  wall.castShadow = true
  g.add(wall)
  const door = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.7, h * 0.65, 0.04),
    metalMat(riskColor, { metalness: 0.25, roughness: 0.55, emissive: riskColor, emissiveIntensity: 0.05 })
  )
  door.position.set(0, h * 0.48, -d * 0.33)
  g.add(door)
  const canopy = new THREE.Mesh(
    new THREE.BoxGeometry(w * 1.1, 0.08, d * 0.7),
    metalMat(0x34495E, { metalness: 0.4, roughness: 0.5 })
  )
  canopy.position.set(0, h * 0.95, d * 0.05)
  canopy.castShadow = true
  g.add(canopy)
  const bump = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.9, 0.1, 0.12),
    metalMat(0xF4D03F, { metalness: 0.2, roughness: 0.5 })
  )
  bump.position.set(0, 0.12, d * 0.42)
  g.add(bump)
  return g
}

// ========== 托盘暂存 ==========
function buildStaging(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  g.add(buildBase(w, d, 0.08))
  const cols = 3
  const rows = 3
  const bw = w / cols * 0.7
  const bd = d / rows * 0.7
  const bh = Math.max(0.25, h * 0.35)
  for (let i = 0; i < cols; i++) {
    for (let j = 0; j < rows; j++) {
      const stacks = 1 + ((i + j) % 3)
      for (let s = 0; s < stacks; s++) {
        const top = s === stacks - 1
        const box = new THREE.Mesh(
          new THREE.BoxGeometry(bw, bh, bd),
          top
            ? metalMat(riskColor, { metalness: 0.08, roughness: 0.85, emissive: riskColor, emissiveIntensity: 0.04 })
            : cartonMat(0xC9A66B)
        )
        box.position.set(
          -w / 2 + (i + 0.5) * w / cols,
          0.08 + bh / 2 + s * bh,
          -d / 2 + (j + 0.5) * d / rows
        )
        box.castShadow = true
        g.add(box)
      }
    }
  }
  return g
}

// ========== WMS 工位 ==========
function buildStation(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  const desk = new THREE.Mesh(
    new THREE.BoxGeometry(w, h * 0.35, d),
    metalMat(0x5D6D7E, { metalness: 0.2, roughness: 0.7 })
  )
  desk.position.y = h * 0.25
  desk.castShadow = true
  g.add(desk)
  const pole = new THREE.Mesh(
    new THREE.BoxGeometry(0.08, h * 0.25, 0.08),
    metalMat(0x333333, { metalness: 0.5, roughness: 0.4 })
  )
  pole.position.set(0, h * 0.5, -d * 0.15)
  g.add(pole)
  const screen = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.45, h * 0.4, 0.06),
    metalMat(riskColor, { metalness: 0.3, roughness: 0.3, emissive: riskColor, emissiveIntensity: 0.15 })
  )
  screen.position.set(0, h * 0.7, -d * 0.15)
  g.add(screen)
  return g
}

// ========== 温控探头 ==========
function buildSensor(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  const s = Math.max(w, h, d, 0.25)
  const pole = new THREE.Mesh(
    new THREE.CylinderGeometry(0.03, 0.04, s * 2.2, 8),
    metalMat(0x888888, { metalness: 0.6, roughness: 0.4 })
  )
  pole.position.y = s * 1.1
  g.add(pole)
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(s * 0.45, 12, 10),
    metalMat(riskColor, { metalness: 0.2, roughness: 0.4, emissive: riskColor, emissiveIntensity: 0.25 })
  )
  head.position.y = s * 2.2
  g.add(head)
  return g
}

// ========== 冷链库 ==========
function buildColdStorage(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  const body = new THREE.Mesh(
    new RoundedBoxGeometry(w, h, d, 2, 0.12),
    metalMat(0xD6EAF8, { metalness: 0.15, roughness: 0.55 })
  )
  body.position.y = h / 2
  body.castShadow = true
  body.receiveShadow = true
  g.add(body)
  const stripe = new THREE.Mesh(
    new THREE.BoxGeometry(w * 1.01, h * 0.12, d * 1.01),
    metalMat(riskColor, { metalness: 0.3, roughness: 0.4, emissive: riskColor, emissiveIntensity: 0.08 })
  )
  stripe.position.y = h * 0.7
  g.add(stripe)
  const door = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.28, h * 0.7, 0.06),
    metalMat(0x1ABC9C, { metalness: 0.4, roughness: 0.35 })
  )
  door.position.set(0, h * 0.4, d / 2 + 0.02)
  g.add(door)
  const cond = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.3, 0.35, d * 0.3),
    metalMat(0x5D6D7E, { metalness: 0.5, roughness: 0.45 })
  )
  cond.position.y = h + 0.18
  cond.castShadow = true
  g.add(cond)
  return g
}

// ========== 危险品库 ==========
function buildHazmat(size, riskColor) {
  const [w, h, d] = size
  const g = new THREE.Group()
  const body = new THREE.Mesh(
    new RoundedBoxGeometry(w, h, d, 2, 0.12),
    metalMat(0xF5CBA7, { metalness: 0.1, roughness: 0.7 })
  )
  body.position.y = h / 2
  body.castShadow = true
  g.add(body)
  const band = new THREE.Mesh(
    new THREE.BoxGeometry(w * 1.02, 0.25, d * 1.02),
    metalMat(riskColor, { metalness: 0.2, roughness: 0.5, emissive: riskColor, emissiveIntensity: 0.1 })
  )
  band.position.y = h * 0.55
  g.add(band)
  const door = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.25, h * 0.55, 0.06),
    metalMat(0x922B21, { metalness: 0.3, roughness: 0.5 })
  )
  door.position.set(0, h * 0.35, d / 2 + 0.02)
  g.add(door)
  return g
}

// ========== 工厂入口 ==========
const BUILDERS = {
  dock: buildDock,
  asrs: buildAsrs,
  agv: buildAgv,
  forklift: buildForklift,
  sensor: buildSensor,
  station: buildStation,
  staging: buildStaging,
  cold_storage: buildColdStorage,
  hazmat: buildHazmat,
  charger: buildCharger,
}

/**
 * 构建设备 3D 模型 Group
 * @param {string} model - 设备模型描述符（来自后端 twin_service.DEVICE_TYPES）
 * @param {number[]} size - [宽, 高, 深]
 * @param {number} riskColor - 风险色（0xRRGGBB）
 * @returns {THREE.Group}
 */
export function buildDevice(model, size, riskColor) {
  const builder = BUILDERS[model] || buildDefault
  return builder(size, riskColor)
}

function buildDefault(size, riskColor) {
  // 兜底：单一金属盒子（但比之前稍好 — 仍保留基础样式）
  const g = new THREE.Group()
  const [w, h, d] = size
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    metalMat(riskColor, { metalness: 0.4, roughness: 0.55 })
  )
  body.position.y = h / 2
  body.castShadow = true
  g.add(body)
  return g
}

/**
 * 构建区域指示（地面矩形 + 文字）
 */
export function buildAreaFloor(area) {
  const g = new THREE.Group()
  const pos = area.position || [0, 0, 0]
  const sz = area.size || [4, 0, 4]
  // 关键：y 提到 0.025（高于 buildLand 的 platforms 0.005），配合 polygonOffset 防 z-fighting
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(sz[0], sz[2]),
    new THREE.MeshStandardMaterial({
      color: 0x2A2D3A,
      transparent: true,
      opacity: 0.55,
      metalness: 0.1,
      roughness: 0.85,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    })
  )
  floor.rotation.x = -Math.PI / 2
  floor.position.set(pos[0], 0.025, pos[2])
  // 半透明地面不接阴影(否则阴影 alpha 叠加会闪烁)
  floor.receiveShadow = false
  g.add(floor)

  // 边框（细线）
  const halfW = sz[0] / 2, halfD = sz[2] / 2
  const lineMat = new THREE.LineBasicMaterial({ color: 0x4A5468, transparent: true, opacity: 0.5 })
  const corners = [
    [-halfW, 0, -halfD], [halfW, 0, -halfD],
    [halfW, 0, halfD], [-halfW, 0, halfD], [-halfW, 0, -halfD]
  ].map(c => new THREE.Vector3(c[0] + pos[0], 0.026, c[2] + pos[2]))
  g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(corners), lineMat))
  return g
}

/**
 * 园区环境（地面 + 道路 + 围栏 + 建筑）
 */
export function buildEnvironment() {
  const g = new THREE.Group()

  // 大地面（绿地）— 60×60
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(80, 80),
    grassMat()
  )
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.01
  ground.receiveShadow = true
  g.add(ground)

  // 园区混凝土地面 — 30×30
  const inner = new THREE.Mesh(
    new THREE.PlaneGeometry(35, 25),
    new THREE.MeshStandardMaterial({ color: 0xB0B3B8, metalness: 0.05, roughness: 0.9 })
  )
  inner.rotation.x = -Math.PI / 2
  inner.position.set(0, 0, 0)
  inner.receiveShadow = true
  g.add(inner)

  // 巡检道路（十字交叉）— 1m 宽
  const road1 = new THREE.Mesh(
    new THREE.PlaneGeometry(35, 1.2),
    roadMat()
  )
  road1.rotation.x = -Math.PI / 2
  road1.position.set(0, 0.01, 0)
  road1.receiveShadow = true
  g.add(road1)
  const road2 = new THREE.Mesh(
    new THREE.PlaneGeometry(1.2, 25),
    roadMat()
  )
  road2.rotation.x = -Math.PI / 2
  road2.position.set(0, 0.01, 0)
  road2.receiveShadow = true
  g.add(road2)

  // 仓控室建筑（左侧 -12, 8）— 实心盒
  const cr = new THREE.Mesh(
    new THREE.BoxGeometry(8, 4, 4),
    buildingMat()
  )
  cr.position.set(-12, 2, 8)
  cr.castShadow = true
  cr.receiveShadow = true
  g.add(cr)
  // 屋顶
  const crRoof = new THREE.Mesh(
    new THREE.BoxGeometry(8.4, 0.2, 4.4),
    roofMat()
  )
  crRoof.position.set(-12, 4.1, 8)
  crRoof.castShadow = true
  g.add(crRoof)
  // 仓控室窗（深色玻璃）
  const winMat = new THREE.MeshStandardMaterial({ color: 0x1A2A3A, metalness: 0.7, roughness: 0.2, emissive: 0x0A141F, emissiveIntensity: 0.3 })
  for (let i = 0; i < 3; i++) {
    const win = new THREE.Mesh(
      new THREE.PlaneGeometry(1.5, 1.2),
      winMat
    )
    win.position.set(-12 + (-1 + i) * 2.5, 2.5, 10.01)
    g.add(win)
  }

  // 设备间（-12, 0）— 比仓控室矮一点
  const sw = new THREE.Mesh(
    new THREE.BoxGeometry(8, 3.5, 6),
    buildingMat()
  )
  sw.position.set(-12, 1.75, 0)
  sw.castShadow = true
  sw.receiveShadow = true
  g.add(sw)
  const swRoof = new THREE.Mesh(
    new THREE.BoxGeometry(8.4, 0.2, 6.4),
    roofMat()
  )
  swRoof.position.set(-12, 3.6, 0)
  swRoof.castShadow = true
  g.add(swRoof)

  // 围栏（仓储园区外圈）
  const fencePts = [
    [-17.5, 0, -12.5], [17.5, 0, -12.5],
    [17.5, 0, 12.5], [-17.5, 0, 12.5], [-17.5, 0, -12.5]
  ]
  for (let i = 0; i < fencePts.length - 1; i++) {
    const p1 = fencePts[i], p2 = fencePts[i + 1]
    const dx = p2[0] - p1[0], dz = p2[2] - p1[2]
    const len = Math.sqrt(dx * dx + dz * dz)
    const post = new THREE.Mesh(
      new THREE.BoxGeometry(0.1, 1.2, 0.1),
      fenceMat()
    )
    post.position.set(p1[0], 0.6, p1[2])
    g.add(post)
    // 横杆
    const bar = new THREE.Mesh(
      new THREE.BoxGeometry(len, 0.04, 0.04),
      fenceMat()
    )
    bar.position.set((p1[0] + p2[0]) / 2, 1.0, (p1[2] + p2[2]) / 2)
    bar.rotation.y = -Math.atan2(dz, dx)
    g.add(bar)
  }
  // 角落立柱
  for (const [x, _y, z] of [[-17.5, 0, -12.5], [17.5, 0, -12.5], [17.5, 0, 12.5], [-17.5, 0, 12.5]]) {
    const corner = new THREE.Mesh(
      new THREE.BoxGeometry(0.15, 1.3, 0.15),
      fenceMat()
    )
    corner.position.set(x, 0.65, z)
    g.add(corner)
  }

  return g
}

/**
 * 区域标签（白底蓝字大字号）
 */
export function buildAreaLabel(text, x, z, color = '#5DADE2') {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  // 关键：标签改为完全实心不透明（alpha=1.0），配合 transparent:false 彻底避免 z-sort 闪烁
  // 背景（实心圆角矩形）
  const r = 16
  ctx.fillStyle = 'rgb(20, 25, 40)'
  ctx.beginPath(); ctx.roundRect(0, 0, 256, 64, r); ctx.fill()
  // 左侧色条
  ctx.save(); ctx.beginPath(); ctx.roundRect(0, 0, 256, 64, r); ctx.clip()
  ctx.fillStyle = color
  ctx.fillRect(0, 0, 6, 64)
  ctx.restore()
  // 文字
  ctx.fillStyle = '#FFFFFF'
  ctx.font = 'bold 22px "PingFang SC", sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, 128, 32)
  const tex = new THREE.CanvasTexture(canvas)
  const mat = new THREE.SpriteMaterial({
    map: tex,
    transparent: false,
    depthTest: false,
    depthWrite: false,
  })
  const sprite = new THREE.Sprite(mat)
  sprite.position.set(x, 0.3, z)
  sprite.scale.set(4.0, 1.0, 1)
  // 强制最后画，避免与设备连接线/树遮挡竞争
  sprite.renderOrder = 100
  return sprite
}

/**
 * 设备标签（黑底白字 + 设备类型 icon）
 */
export function buildDeviceLabel(name, typeIcon, x, y, z, blink = false) {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 56
  const ctx = canvas.getContext('2d')
  // 关键：标签改为完全实心不透明（alpha=1.0），配合 transparent:false 彻底避免 z-sort 闪烁
  // 背景（实心圆角矩形）
  const r = 14
  ctx.fillStyle = blink ? 'rgb(120, 30, 30)' : 'rgb(15, 20, 35)'
  ctx.beginPath(); ctx.roundRect(0, 0, 256, 56, r); ctx.fill()
  // 边框（圆角）
  ctx.strokeStyle = blink ? '#FF6644' : '#4A5468'
  ctx.lineWidth = 2
  ctx.beginPath(); ctx.roundRect(1, 1, 254, 54, r - 1); ctx.stroke()
  // icon
  ctx.font = '20px sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = '#FFFFFF'
  ctx.fillText(typeIcon || '📦', 8, 28)
  // 名字
  ctx.fillStyle = blink ? '#FFDD66' : '#FFFFFF'
  ctx.font = 'bold 16px "PingFang SC", sans-serif'
  ctx.fillText(name, 36, 28)
  const tex = new THREE.CanvasTexture(canvas)
  const mat = new THREE.SpriteMaterial({
    map: tex,
    transparent: false,
    depthTest: false,
    depthWrite: false,
  })
  const sprite = new THREE.Sprite(mat)
  sprite.position.set(x, y, z)
  sprite.scale.set(2.6, 0.55, 1)
  // 强制最后画，避免与设备/连接线/树遮挡竞争
  sprite.renderOrder = 100
  return sprite
}

/**
 * 连接线（跨区管线）— 弧形
 */
export function buildConnectionLine(p1, p2, color = 0x8B95A1) {
  const v1 = new THREE.Vector3(...p1)
  const v2 = new THREE.Vector3(...p2)
  // 中点抬高（弧形更明显，避开设备几何）
  const mid = v1.clone().add(v2).multiplyScalar(0.5)
  const dist = v1.distanceTo(v2)
  mid.y += Math.max(0.8, dist * 0.2)
  const curve = new THREE.QuadraticBezierCurve3(v1, mid, v2)
  const pts = curve.getPoints(16)
  const geo = new THREE.BufferGeometry().setFromPoints(pts)
  // 关键：transparent: false — LineBasicMaterial 透明会 z-sort 闪烁
  const mat = new THREE.LineBasicMaterial({ color, transparent: false })
  return new THREE.Line(geo, mat)
}

/**
 * 释放共享材质（场景销毁时调用）
 */
export function disposeMaterials() {
  for (const m of _matCache.values()) {
    if (m.dispose) m.dispose()
  }
  _matCache.clear()
}
