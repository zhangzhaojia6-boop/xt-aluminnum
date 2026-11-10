import {
  ACESFilmicToneMapping,
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  EdgesGeometry,
  Fog,
  HemisphereLight,
  InstancedMesh,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  Raycaster,
  Scene,
  Vector2,
  Vector3,
  WebGLRenderer
} from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

import { PLAN_SIZE, SITE } from '../../utils/factory-layout.js'
import { UNIT, buildingParts, siteRects } from '../../utils/plant-parts.js'

export { supportsWebGL } from '../../utils/webgl-support.js'

const BAR_MS = 500
const BAR_STAGGER = 40
const MAX_PIXELS = 4.5e6

const DEFAULT_COLORS = {
  ground: '#0a1424',
  road: '#162238',
  lane: '#3a4a63',
  fence: '#3a4a63',
  wall: '#c9d0d8',
  annexWall: '#8e98a6',
  plinth: '#5a6470',
  roof: '#2a5fa8',
  skylight: '#cfe0f0',
  window: '#24384f',
  vent: '#8a96a8',
  bar: '#8fd0ff',
  annexRoof: '#56627a',
  hover: '#6aa2ff'
}

// 单位双坡屋顶：底面 x、z ∈ [-0.5, 0.5]，屋脊沿 x 轴、高 1。8 个三角面，自写避免引入 earcut。
export function createGableRoofGeometry() {
  const a = [-0.5, 0, -0.5]
  const b = [0.5, 0, -0.5]
  const c = [0.5, 0, 0.5]
  const d = [-0.5, 0, 0.5]
  const r1 = [-0.5, 1, 0]
  const r2 = [0.5, 1, 0]
  const tris = [
    a, r1, r2, a, r2, b,
    d, c, r2, d, r2, r1,
    a, d, r1,
    b, r2, c,
    a, b, c, a, c, d
  ]
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(tris.flat()), 3))
  geometry.computeVertexNormals()
  return geometry
}

function instanced(geometry, material, count) {
  const mesh = new InstancedMesh(geometry, material, Math.max(count, 1))
  mesh.count = count
  return mesh
}

const dummy = new Object3D()

function setBox(mesh, index, { cx, cz, w, d, y = 0, h }) {
  dummy.position.set(cx, y + h / 2, cz)
  dummy.rotation.set(0, 0, 0)
  dummy.scale.set(w, h, d)
  dummy.updateMatrix()
  mesh.setMatrixAt(index, dummy.matrix)
}

export function createPlantScene(container, { colors = {}, animate, onSelect, onHover, onLabels, onLost }) {
  const palette = { ...DEFAULT_COLORS, ...colors }
  const renderer = new WebGLRenderer({ antialias: true, alpha: true, failIfMajorPerformanceCaveat: true })
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = PCFShadowMap
  renderer.shadowMap.autoUpdate = false
  container.appendChild(renderer.domElement)

  const scene = new Scene()
  scene.fog = new Fog(palette.ground, 95, 210)
  const camera = new PerspectiveCamera(32, 1, 1, 400)
  camera.position.set(8, 70, 62)

  const controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0, 3)
  controls.enablePan = false
  controls.minDistance = 40
  controls.maxDistance = 160
  controls.maxPolarAngle = Math.PI * 0.36
  controls.update()

  scene.add(new HemisphereLight('#bcd4ff', '#0a1220', 0.9))
  const sun = new DirectionalLight('#ffffff', 1.2)
  sun.position.set(40, 70, 50)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  sun.shadow.radius = 3
  Object.assign(sun.shadow.camera, { left: -55, right: 55, top: 40, bottom: -40, near: 10, far: 200 })
  scene.add(sun)

  const disposables = []
  const material = (options) => {
    const m = new MeshStandardMaterial(options)
    disposables.push(m)
    return m
  }
  const geometry = (g) => {
    disposables.push(g)
    return g
  }

  // 地面、道路、车道线、围墙、大门、停车位
  const groundGeo = geometry(new PlaneGeometry(PLAN_SIZE.width * UNIT, PLAN_SIZE.height * UNIT))
  const ground = new Mesh(groundGeo, material({ color: palette.ground, roughness: 1 }))
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  const unitPlane = geometry(new PlaneGeometry(1, 1))
  const roads = siteRects(SITE.roads)
  const roadMesh = instanced(unitPlane, material({ color: palette.road, roughness: 0.95 }), roads.length)
  roads.forEach((road, i) => {
    dummy.position.set(road.cx, 0.01, road.cz)
    dummy.rotation.set(-Math.PI / 2, 0, 0)
    dummy.scale.set(road.w, road.d, 1)
    dummy.updateMatrix()
    roadMesh.setMatrixAt(i, dummy.matrix)
  })
  roadMesh.receiveShadow = true
  scene.add(roadMesh)

  const linePoints = []
  for (const road of roads) {
    const horizontal = road.w >= road.d
    const half = (horizontal ? road.w : road.d) / 2 - 0.4
    for (let t = -half; t < half; t += 1.6) {
      const end = Math.min(t + 0.8, half)
      if (horizontal) linePoints.push(road.cx + t, 0.03, road.cz, road.cx + end, 0.03, road.cz)
      else linePoints.push(road.cx, 0.03, road.cz + t, road.cx, 0.03, road.cz + end)
    }
  }
  for (const lot of siteRects(SITE.parking)) {
    const stall = lot.w / lot.rect.stalls
    for (let i = 0; i <= lot.rect.stalls; i++) {
      const x = lot.cx - lot.w / 2 + i * stall
      linePoints.push(x, 0.03, lot.cz - lot.d / 2, x, 0.03, lot.cz + lot.d / 2)
    }
  }
  const lineGeo = geometry(new BufferGeometry())
  lineGeo.setAttribute('position', new BufferAttribute(new Float32Array(linePoints), 3))
  const lineMat = new LineBasicMaterial({ color: palette.lane })
  disposables.push(lineMat)
  scene.add(new LineSegments(lineGeo, lineMat))

  const unitBox = geometry(new BoxGeometry(1, 1, 1))
  const fence = siteRects([SITE.fence])[0]
  const fenceSides = [
    { cx: fence.cx, cz: fence.cz - fence.d / 2, w: fence.w, d: 0.12, h: 0.35 },
    { cx: fence.cx, cz: fence.cz + fence.d / 2, w: fence.w, d: 0.12, h: 0.35 },
    { cx: fence.cx - fence.w / 2, cz: fence.cz, w: 0.12, d: fence.d, h: 0.35 },
    { cx: fence.cx + fence.w / 2, cz: fence.cz, w: 0.12, d: fence.d, h: 0.35 }
  ]
  const gatePosts = siteRects(SITE.gates).flatMap((gate) => [-1, 1].map((side) => ({
    cx: gate.cx + side * (gate.w / 2), cz: gate.cz, w: 0.35, d: 0.35, h: 1.1
  })))
  const fenceParts = [...fenceSides, ...gatePosts]
  const fenceMesh = instanced(unitBox, material({ color: palette.fence, roughness: 0.8 }), fenceParts.length)
  fenceParts.forEach((part, i) => setBox(fenceMesh, i, part))
  scene.add(fenceMesh)

  // 厂房部件：同一种材质一个 InstancedMesh，绘制调用固定
  const roofGeo = geometry(createGableRoofGeometry())
  const ventGeo = geometry(new CylinderGeometry(0.12, 0.16, 0.28, 8))
  let walls = null
  let plinths = null
  let roofs = null
  let skylights = null
  let windows = null
  let vents = null
  let bars = null
  let parts = []
  let current = []
  let built = false
  let barProgress = animate ? 0 : 1
  let frame = 0
  let destroyed = false
  let hoveredIndex = -1

  const hoverEdges = new LineSegments(geometry(new EdgesGeometry(unitBox)), new LineBasicMaterial({ color: palette.hover }))
  disposables.push(hoverEdges.material)
  hoverEdges.visible = false
  scene.add(hoverEdges)

  function build(blocks) {
    const wallMat = material({ color: '#ffffff', roughness: 0.85 })
    const wallColor = new Color(palette.wall)
    const annexWall = new Color(palette.annexWall)
    const n = blocks.length
    walls = instanced(unitBox, wallMat, n)
    plinths = instanced(unitBox, material({ color: palette.plinth, roughness: 0.9 }), n)
    roofs = instanced(roofGeo, material({ color: '#ffffff', metalness: 0.3, roughness: 0.6 }), n)
    skylights = instanced(unitBox, material({ color: palette.skylight, emissive: palette.skylight, emissiveIntensity: 0.15 }), n)
    windows = instanced(unitBox, material({ color: palette.window, roughness: 0.4 }), n * 2)
    vents = instanced(ventGeo, material({ color: palette.vent, metalness: 0.4, roughness: 0.5 }), 400)
    bars = instanced(unitBox, material({ color: palette.bar, emissive: palette.bar, emissiveIntensity: 0.55 }), n)
    walls.castShadow = roofs.castShadow = plinths.castShadow = true
    walls.receiveShadow = true
    for (const mesh of [walls, plinths, roofs, skylights, windows, vents, bars]) scene.add(mesh)
    const roofColor = new Color(palette.roof)
    const annexRoof = new Color(palette.annexRoof)
    blocks.forEach((block, i) => {
      walls.setColorAt(i, block.isWorkshop ? wallColor : annexWall)
      roofs.setColorAt(i, block.isWorkshop ? roofColor : annexRoof)
    })
    walls.instanceColor.needsUpdate = true
    roofs.instanceColor.needsUpdate = true
    built = true
  }

  function layout() {
    let windowIndex = 0
    let ventIndex = 0
    let skyIndex = 0
    let barIndex = 0
    parts.forEach((part, i) => {
      setBox(walls, i, part.wall)
      setBox(plinths, i, part.plinth)
      const roof = part.roof
      dummy.position.set(roof.cx, roof.y, roof.cz)
      dummy.rotation.set(0, roof.alongX ? 0 : Math.PI / 2, 0)
      dummy.scale.set(roof.alongX ? roof.w : roof.d, roof.rise, roof.alongX ? roof.d : roof.w)
      dummy.updateMatrix()
      roofs.setMatrixAt(i, dummy.matrix)
      if (part.skylight) setBox(skylights, skyIndex++, part.skylight)
      for (const win of part.windows) setBox(windows, windowIndex++, win)
      for (const vent of part.vents) {
        if (ventIndex >= 400) break
        dummy.position.set(vent.x, vent.y + 0.14, vent.z)
        dummy.rotation.set(0, 0, 0)
        dummy.scale.set(1, 1, 1)
        dummy.updateMatrix()
        vents.setMatrixAt(ventIndex++, dummy.matrix)
      }
      if (part.bar) {
        const t = Math.min(Math.max((barProgress * (BAR_MS + BAR_STAGGER * parts.length) - barIndex * BAR_STAGGER) / BAR_MS, 0), 1)
        const eased = 1 - (1 - t) ** 3
        setBox(bars, barIndex++, { ...part.bar, h: Math.max(part.bar.h * eased, 0.001) })
      }
    })
    skylights.count = skyIndex
    windows.count = windowIndex
    vents.count = ventIndex
    bars.count = barIndex
    for (const mesh of [walls, plinths, roofs, skylights, windows, vents, bars]) mesh.instanceMatrix.needsUpdate = true
    applyHover()
  }

  function applyHover() {
    const part = parts[hoveredIndex]
    if (!part) {
      hoverEdges.visible = false
      return
    }
    hoverEdges.visible = true
    hoverEdges.position.set(part.wall.cx, (part.wall.h + part.roof.rise) / 2, part.wall.cz)
    hoverEdges.scale.set(part.wall.w + 0.1, part.wall.h + part.roof.rise + 0.05, part.wall.d + 0.1)
  }

  const point = new Vector3()
  function emitLabels() {
    const rect = renderer.domElement.getBoundingClientRect()
    const labels = {}
    for (const part of parts) {
      point.set(part.wall.cx, part.labelY, part.wall.cz).project(camera)
      labels[part.key] = {
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
    frame = requestAnimationFrame((now) => {
      start ??= now
      barProgress = Math.min((now - start) / (BAR_MS + BAR_STAGGER * parts.length), 1)
      layout()
      render()
      if (barProgress < 1) runBars(start)
    })
  }

  function update(blocks) {
    current = blocks
    parts = blocks.map((block) => buildingParts(block))
    if (!built) build(blocks)
    layout()
    renderer.shadowMap.needsUpdate = true
    render()
  }

  function resize() {
    const width = container.clientWidth
    const height = container.clientHeight
    if (!width || !height) return
    const ratio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(MAX_PIXELS / (width * height)))
    renderer.setPixelRatio(Math.max(ratio, 1))
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    render()
  }

  const raycaster = new Raycaster()
  const pointer = new Vector2()
  function pick(event) {
    if (!walls) return -1
    const rect = renderer.domElement.getBoundingClientRect()
    pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObjects([walls, roofs])[0]
    return hit ? hit.instanceId : -1
  }

  let downAt = null
  let hoverFrame = 0
  let lastMove = null
  function onPointerDown(event) {
    downAt = { x: event.clientX, y: event.clientY }
  }
  function onPointerUp(event) {
    if (!downAt || Math.hypot(event.clientX - downAt.x, event.clientY - downAt.y) > 4) return
    const index = pick(event)
    if (index >= 0) onSelect?.(current[index])
  }
  function onPointerMove(event) {
    lastMove = event
    if (hoverFrame) return
    hoverFrame = requestAnimationFrame(() => {
      hoverFrame = 0
      const index = pick(lastMove)
      if (index === hoveredIndex) return
      hoveredIndex = index
      renderer.domElement.style.cursor = current[index]?.workshopId ? 'pointer' : ''
      applyHover()
      onHover?.(current[index]?.key || null)
      render()
    })
  }
  function onPointerLeave() {
    if (hoveredIndex === -1) return
    hoveredIndex = -1
    applyHover()
    onHover?.(null)
    render()
  }
  function onContextLost(event) {
    event.preventDefault()
    onLost?.()
  }

  const el = renderer.domElement
  el.addEventListener('pointerdown', onPointerDown)
  el.addEventListener('pointerup', onPointerUp)
  el.addEventListener('pointermove', onPointerMove)
  el.addEventListener('pointerleave', onPointerLeave)
  el.addEventListener('webglcontextlost', onContextLost)
  controls.addEventListener('change', render)
  const observer = new ResizeObserver(resize)
  observer.observe(container)
  resize()

  return {
    update(blocks) {
      update(blocks)
      if (animate && barProgress === 0 && !frame) runBars()
    },
    destroy() {
      destroyed = true
      cancelAnimationFrame(frame)
      cancelAnimationFrame(hoverFrame)
      observer.disconnect()
      controls.removeEventListener('change', render)
      controls.dispose()
      el.removeEventListener('pointerdown', onPointerDown)
      el.removeEventListener('pointerup', onPointerUp)
      el.removeEventListener('pointermove', onPointerMove)
      el.removeEventListener('pointerleave', onPointerLeave)
      el.removeEventListener('webglcontextlost', onContextLost)
      for (const mesh of [walls, plinths, roofs, skylights, windows, vents, bars, roadMesh, fenceMesh]) mesh?.dispose?.()
      disposables.forEach((item) => item.dispose())
      renderer.dispose()
      el.remove()
    }
  }
}

