import {
  ACESFilmicToneMapping,
  BoxGeometry,
  CylinderGeometry,
  DirectionalLight,
  HemisphereLight,
  InstancedMesh,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  Vector3,
  WebGLRenderer
} from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

import { buildLineParts } from '../../utils/line-parts.js'

const MATERIALS = {
  furnace: { color: '#6b7891', roughness: 0.7 },
  glow: { color: '#f5b544', emissive: '#f5b544', emissiveIntensity: 0.8 },
  housing: { color: '#9aa6b8', metalness: 0.2, roughness: 0.55 },
  roll: { color: '#dfe6ef', metalness: 0.35, roughness: 0.3 },
  table: { color: '#4f607c', roughness: 0.8 },
  coil: { color: '#dfe6ef', metalness: 0.35, roughness: 0.3 },
  conveyor: { color: '#2c3f5e', roughness: 0.8 },
  roller: { color: '#9aa8bd', metalness: 0.25, roughness: 0.4 },
  bar: { color: '#8fd0ff', emissive: '#8fd0ff', emissiveIntensity: 0.55 },
  ground: { color: '#0a1424', roughness: 1 }
}

const COIL_SECONDS = 14
const FRAME_MS = 1000 / 30
const BAR_MS = 500

const dummy = new Object3D()

function place(mesh, index, part) {
  if (part.kind === 'roll') {
    dummy.position.set(part.cx, part.cy, part.cz)
    dummy.rotation.set(Math.PI / 2, 0, 0)
    dummy.scale.set(part.r, part.len, part.r)
  } else {
    dummy.position.set(part.cx, part.cy ?? part.y + part.h / 2, part.cz)
    dummy.rotation.set(0, 0, 0)
    dummy.scale.set(part.w, part.h, part.d)
  }
  dummy.updateMatrix()
  mesh.setMatrixAt(index, dummy.matrix)
}

// 实时页 3D 产线。数据变化只改数据柱；铝卷动画只在有数据、页面可见、舞台在视口内时运行，限 30fps。
export function createLineScene(container, { colors = {}, animate, onLabels, onLost }) {
  const renderer = new WebGLRenderer({ antialias: true, alpha: true, failIfMajorPerformanceCaveat: true })
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  container.appendChild(renderer.domElement)

  const scene = new Scene()
  const camera = new PerspectiveCamera(30, 1, 1, 300)
  camera.position.set(0, 13, 31)
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 1.2, 0)
  controls.enablePan = false
  controls.minDistance = 12
  controls.maxDistance = 80
  controls.maxPolarAngle = Math.PI * 0.42
  controls.update()

  scene.add(new HemisphereLight('#bcd4ff', '#1a2438', 1.6))
  const sun = new DirectionalLight('#ffffff', 1.3)
  sun.position.set(20, 30, 25)
  scene.add(sun)

  const disposables = []
  const mats = {}
  for (const [name, options] of Object.entries(MATERIALS)) {
    const merged = { ...options, ...(colors[name] ? { color: colors[name] } : {}) }
    mats[name] = new MeshStandardMaterial(merged)
    disposables.push(mats[name])
  }
  const boxGeo = new BoxGeometry(1, 1, 1)
  const rollGeo = new CylinderGeometry(1, 1, 1, 20)
  const groundGeo = new PlaneGeometry(90, 20)
  disposables.push(boxGeo, rollGeo, groundGeo)

  const ground = new Mesh(groundGeo, mats.ground)
  ground.rotation.x = -Math.PI / 2
  scene.add(ground)

  let meshes = []
  let barMesh = null
  let movingCoil = null
  let layout = null
  let signature = ''
  let barProgress = animate ? 0 : 1
  let barFrame = 0
  let coilFrame = 0
  let lastTick = 0
  let coilX = 0
  let visible = true
  let destroyed = false

  function clearMeshes() {
    for (const mesh of meshes) {
      scene.remove(mesh)
      mesh.dispose?.()
    }
    meshes = []
  }

  function buildEquipment() {
    clearMeshes()
    const groups = new Map()
    for (const part of layout.parts) {
      const key = `${part.kind}:${part.mat}`
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key).push(part)
    }
    for (const [key, parts] of groups) {
      const [kind, mat] = key.split(':')
      const mesh = new InstancedMesh(kind === 'roll' ? rollGeo : boxGeo, mats[mat], parts.length)
      parts.forEach((part, i) => place(mesh, i, part))
      scene.add(mesh)
      meshes.push(mesh)
    }
    if (layout.conveyor) {
      const conveyor = new InstancedMesh(boxGeo, mats.conveyor, 1)
      place(conveyor, 0, { kind: 'box', ...layout.conveyor })
      const rollers = new InstancedMesh(rollGeo, mats.roller, layout.rollers.length)
      layout.rollers.forEach((roller, i) => place(rollers, i, { kind: 'roll', cx: roller.x, cy: 0.3, cz: 0, r: 0.12, len: 1.5 }))
      scene.add(conveyor, rollers)
      meshes.push(conveyor, rollers)
    }
    barMesh = new InstancedMesh(boxGeo, mats.bar, Math.max(layout.stations.length, 1))
    scene.add(barMesh)
    meshes.push(barMesh)
    movingCoil = new Mesh(rollGeo, mats.coil)
    movingCoil.rotation.x = Math.PI / 2
    movingCoil.scale.set(0.55, 0.9, 0.55)
    coilX = layout.coilPath?.from ?? 0
    scene.add(movingCoil)
    meshes.push(movingCoil)
  }

  function placeBars() {
    let index = 0
    for (const station of layout.stations) {
      if (!station.bar) continue
      const order = layout.stations.indexOf(station)
      const t = Math.min(Math.max((barProgress * (BAR_MS + 40 * layout.stations.length) - order * 40) / BAR_MS, 0), 1)
      const eased = 1 - (1 - t) ** 3
      place(barMesh, index++, { kind: 'box', ...station.bar, h: Math.max(station.bar.h * eased, 0.001) })
    }
    barMesh.count = index
    barMesh.instanceMatrix.needsUpdate = true
  }

  function placeCoil() {
    if (!movingCoil) return
    const path = layout.coilPath
    movingCoil.visible = Boolean(path && layout.hasAnyData)
    if (movingCoil.visible) movingCoil.position.set(coilX, path.y, 0)
  }

  const point = new Vector3()
  function emitLabels() {
    const rect = renderer.domElement.getBoundingClientRect()
    const labels = {}
    for (const station of layout?.stations || []) {
      point.set(station.x, station.labelY, 0).project(camera)
      labels[station.key] = {
        left: ((point.x + 1) / 2) * rect.width,
        top: ((1 - point.y) / 2) * rect.height,
        visible: point.z < 1
      }
    }
    onLabels?.(labels)
  }

  function render() {
    if (destroyed) return
    renderer.render(scene, camera)
    container.dataset.drawCalls = String(renderer.info.render.calls)
    emitLabels()
  }

  function runBars(start) {
    barFrame = requestAnimationFrame((now) => {
      start ??= now
      barProgress = Math.min((now - start) / (BAR_MS + 40 * layout.stations.length), 1)
      placeBars()
      render()
      if (barProgress < 1) runBars(start)
      else barFrame = 0
    })
  }

  function coilShouldRun() {
    return animate && visible && !document.hidden && Boolean(layout?.hasAnyData && layout.coilPath)
  }

  function tick(now) {
    coilFrame = 0
    if (!coilShouldRun()) return
    if (now - lastTick >= FRAME_MS) {
      const path = layout.coilPath
      const dt = lastTick ? (now - lastTick) / 1000 : 0
      lastTick = now
      coilX += ((path.to - path.from) / COIL_SECONDS) * dt
      if (coilX > path.to) coilX = path.from
      placeCoil()
      render()
    }
    coilFrame = requestAnimationFrame(tick)
  }

  function syncCoilLoop() {
    if (coilShouldRun() && !coilFrame) {
      lastTick = 0
      coilFrame = requestAnimationFrame(tick)
    } else if (!coilShouldRun() && coilFrame) {
      cancelAnimationFrame(coilFrame)
      coilFrame = 0
    }
    container.dataset.coilRunning = coilShouldRun() ? 'true' : 'false'
  }

  function update(items) {
    layout = buildLineParts(items)
    const nextSignature = layout.stations.map((s) => s.key).join('|')
    if (nextSignature !== signature) {
      signature = nextSignature
      buildEquipment()
    }
    placeBars()
    placeCoil()
    render()
    if (animate && barProgress === 0 && !barFrame) runBars()
    syncCoilLoop()
  }

  function resize() {
    const width = container.clientWidth
    const height = container.clientHeight
    if (!width || !height) return
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    render()
  }

  function onVisibility() {
    syncCoilLoop()
  }
  function onContextLost(event) {
    event.preventDefault()
    onLost?.()
  }

  const intersection = typeof IntersectionObserver === 'undefined'
    ? null
    : new IntersectionObserver((entries) => {
      visible = entries.some((entry) => entry.isIntersecting)
      syncCoilLoop()
    })
  intersection?.observe(container)
  document.addEventListener('visibilitychange', onVisibility)
  renderer.domElement.addEventListener('webglcontextlost', onContextLost)
  controls.addEventListener('change', render)
  const observer = new ResizeObserver(resize)
  observer.observe(container)
  resize()

  return {
    update,
    destroy() {
      destroyed = true
      cancelAnimationFrame(barFrame)
      cancelAnimationFrame(coilFrame)
      intersection?.disconnect()
      observer.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost)
      controls.removeEventListener('change', render)
      controls.dispose()
      clearMeshes()
      disposables.forEach((item) => item.dispose())
      renderer.dispose()
      renderer.domElement.remove()
    }
  }
}
