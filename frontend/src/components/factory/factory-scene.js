import {
  AmbientLight,
  BoxGeometry,
  Color,
  DirectionalLight,
  EdgesGeometry,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  PlaneGeometry,
  Raycaster,
  Scene,
  Vector2,
  Vector3,
  WebGLRenderer
} from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

import { PLAN_SIZE } from '../../utils/factory-layout.js'

const UNIT = 0.1
const HEIGHT_UNIT = 0.12
const ENTRY_MS = 600

export function supportsWebGL() {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2', { failIfMajorPerformanceCaveat: true })
      || canvas.getContext('webgl', { failIfMajorPerformanceCaveat: true })
    const ok = Boolean(gl)
    gl?.getExtension('WEBGL_lose_context')?.loseContext()
    return ok
  } catch {
    return false
  }
}

function toWorld(block) {
  return {
    x: (block.x + block.w / 2 - PLAN_SIZE.width / 2) * UNIT,
    z: (block.y + block.h / 2 - PLAN_SIZE.height / 2) * UNIT
  }
}

// 只在数据变化、拖动视角或入场动画时重绘，平时不跑渲染循环。
export function createFactoryScene(container, { colors, animate, onSelect, onLabels, onLost }) {
  const renderer = new WebGLRenderer({ antialias: true, alpha: true, failIfMajorPerformanceCaveat: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  container.appendChild(renderer.domElement)

  const scene = new Scene()
  const camera = new PerspectiveCamera(32, 1, 1, 400)
  camera.position.set(6, 78, 58)

  const controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0, 3)
  controls.enablePan = false
  controls.minDistance = 50
  controls.maxDistance = 160
  controls.maxPolarAngle = Math.PI * 0.32
  controls.update()

  scene.add(new AmbientLight(0xffffff, 1.6))
  const sun = new DirectionalLight(0xffffff, 1.4)
  sun.position.set(-30, 80, 40)
  scene.add(sun)

  const ground = new Mesh(
    new PlaneGeometry(PLAN_SIZE.width * UNIT, PLAN_SIZE.height * UNIT),
    new MeshStandardMaterial({ color: new Color(colors.ground) })
  )
  ground.rotation.x = -Math.PI / 2
  scene.add(ground)

  const unitBox = new BoxGeometry(1, 1, 1)
  const unitEdges = new EdgesGeometry(unitBox)
  const materials = {
    data: new MeshStandardMaterial({ color: new Color(colors.data) }),
    empty: new MeshStandardMaterial({ color: new Color(colors.empty) }),
    building: new MeshStandardMaterial({ color: new Color(colors.building) })
  }
  const edgeMaterial = new LineBasicMaterial({ color: new Color(colors.edge) })

  const meshes = new Map()
  let current = []
  let progress = animate ? 0 : 1
  let frame = 0
  let destroyed = false

  function materialFor(block) {
    if (!block.isWorkshop) return materials.building
    return block.hasData ? materials.data : materials.empty
  }

  function applyHeights() {
    for (const block of current) {
      const entry = meshes.get(block.key)
      if (!entry) continue
      const height = Math.max(block.height * HEIGHT_UNIT * progress, 0.01)
      entry.mesh.scale.y = height
      entry.mesh.position.y = height / 2
      entry.mesh.material = materialFor(block)
      entry.edges.scale.y = height
      entry.edges.position.y = height / 2
    }
  }

  const point = new Vector3()
  function emitLabels() {
    const rect = renderer.domElement.getBoundingClientRect()
    const labels = {}
    for (const block of current) {
      const entry = meshes.get(block.key)
      if (!entry) continue
      point.set(entry.mesh.position.x, entry.mesh.scale.y + 0.6, entry.mesh.position.z).project(camera)
      labels[block.key] = {
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
    emitLabels()
  }

  function runEntry(start) {
    frame = requestAnimationFrame((now) => {
      start ??= now
      progress = Math.min((now - start) / ENTRY_MS, 1)
      progress = 1 - (1 - progress) ** 3
      applyHeights()
      render()
      if (progress < 1) runEntry(start)
    })
  }

  function update(blocks) {
    current = blocks
    for (const block of blocks) {
      if (meshes.has(block.key)) continue
      const { x, z } = toWorld(block)
      const mesh = new Mesh(unitBox, materialFor(block))
      mesh.scale.set(block.w * UNIT - 0.4, 0.01, block.h * UNIT - 0.4)
      mesh.position.set(x, 0, z)
      mesh.userData.block = block.key
      const edges = new LineSegments(unitEdges, edgeMaterial)
      edges.scale.copy(mesh.scale)
      edges.position.copy(mesh.position)
      scene.add(mesh, edges)
      meshes.set(block.key, { mesh, edges })
    }
    applyHeights()
    render()
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

  const raycaster = new Raycaster()
  const pointer = new Vector2()
  let downAt = null
  function pick(event) {
    const rect = renderer.domElement.getBoundingClientRect()
    pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObjects([...meshes.values()].map((entry) => entry.mesh))[0]
    return hit ? current.find((block) => block.key === hit.object.userData.block) : null
  }
  function onPointerDown(event) {
    downAt = { x: event.clientX, y: event.clientY }
  }
  function onPointerUp(event) {
    if (!downAt || Math.hypot(event.clientX - downAt.x, event.clientY - downAt.y) > 4) return
    const block = pick(event)
    if (block) onSelect?.(block)
  }
  function onPointerMove(event) {
    const block = pick(event)
    renderer.domElement.style.cursor = block?.workshopId ? 'pointer' : ''
  }
  function onContextLost(event) {
    event.preventDefault()
    onLost?.()
  }

  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('webglcontextlost', onContextLost)
  controls.addEventListener('change', render)
  const observer = new ResizeObserver(resize)
  observer.observe(container)
  resize()
  if (animate) runEntry()

  return {
    update,
    destroy() {
      destroyed = true
      cancelAnimationFrame(frame)
      observer.disconnect()
      controls.removeEventListener('change', render)
      controls.dispose()
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      renderer.domElement.removeEventListener('pointermove', onPointerMove)
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost)
      unitBox.dispose()
      unitEdges.dispose()
      ground.geometry.dispose()
      ground.material.dispose()
      Object.values(materials).forEach((material) => material.dispose())
      edgeMaterial.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }
}
