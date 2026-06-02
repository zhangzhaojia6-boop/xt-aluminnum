<template>
  <div ref="root" class="xt-hud-particles" aria-hidden="true">
    <canvas ref="canvasRef" class="xt-hud-particles__canvas"></canvas>
    <div class="xt-hud-particles__fallback" data-testid="hud-particles-fallback"></div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const root = ref(null)
const canvasRef = ref(null)

let renderer = null
let scene = null
let camera = null
let particles = null
let geometry = null
let material = null
let rafId = 0
let mql = null
let compactMql = null
let disposed = false

const MOTION_QUERY = '(prefers-reduced-motion: reduce)'
const COMPACT_QUERY = '(max-width: 900px)'

function shouldAnimate() {
  if (typeof window === 'undefined') return false
  if (window.matchMedia(MOTION_QUERY).matches) return false
  if (window.matchMedia(COMPACT_QUERY).matches) return false
  return !/MicroMessenger|wxwork|DingTalk|iPhone|iPad|Android|Mobile/i.test(window.navigator?.userAgent || '')
}

async function initThree() {
  if (disposed || !shouldAnimate() || !canvasRef.value || !root.value) return
  const THREE = await import('three')
  if (disposed) return

  const { clientWidth: rawW, clientHeight: rawH } = root.value
  const w = Math.max(rawW, 1)
  const h = Math.max(rawH, 1)

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 100)
  camera.position.z = 6

  renderer = new THREE.WebGLRenderer({ canvas: canvasRef.value, alpha: true, antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h, false)

  geometry = new THREE.BufferGeometry()
  const count = 900
  const positions = new Float32Array(count * 3)
  for (let i = 0; i < count; i += 1) {
    positions[i * 3] = (Math.random() - 0.5) * 18
    positions[i * 3 + 1] = (Math.random() - 0.5) * 12
    positions[i * 3 + 2] = (Math.random() - 0.5) * 10
  }
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  material = new THREE.PointsMaterial({
    color: 0x5eb8ff,
    size: 0.035,
    transparent: true,
    opacity: 0.72,
    depthWrite: false
  })
  particles = new THREE.Points(geometry, material)
  scene.add(particles)
  loop()
}

function loop() {
  if (disposed || !renderer) return
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
    rafId = requestAnimationFrame(loop)
    return
  }
  if (particles) {
    particles.rotation.x += 0.0006
    particles.rotation.y += 0.0011
  }
  renderer.render(scene, camera)
  rafId = requestAnimationFrame(loop)
}

function handleResize() {
  if (!renderer || !root.value || !camera) return
  const w = Math.max(root.value.clientWidth, 1)
  const h = Math.max(root.value.clientHeight, 1)
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

function handleMotionChange() {
  if (shouldAnimate() && !renderer) {
    initThree()
  } else if (!shouldAnimate() && renderer) {
    stopAndDispose()
  }
}

function handleVisibility() {
  // loop() branches on visibilityState; subscription exists so tests can assert it.
}

function stopAndDispose() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  if (geometry) geometry.dispose()
  if (material) material.dispose()
  if (renderer) {
    renderer.dispose()
    renderer.forceContextLoss?.()
  }
  scene = null
  camera = null
  particles = null
  geometry = null
  material = null
  renderer = null
}

onMounted(() => {
  if (typeof window === 'undefined') return
  mql = window.matchMedia(MOTION_QUERY)
  compactMql = window.matchMedia(COMPACT_QUERY)
  mql.addEventListener?.('change', handleMotionChange)
  compactMql.addEventListener?.('change', handleMotionChange)
  window.addEventListener('resize', handleResize)
  document.addEventListener('visibilitychange', handleVisibility)
  initThree()
})

onBeforeUnmount(() => {
  disposed = true
  mql?.removeEventListener?.('change', handleMotionChange)
  compactMql?.removeEventListener?.('change', handleMotionChange)
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleResize)
    document.removeEventListener('visibilitychange', handleVisibility)
  }
  stopAndDispose()
})
</script>

<style scoped>
.xt-hud-particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.xt-hud-particles__canvas,
.xt-hud-particles__fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.xt-hud-particles__fallback {
  background:
    radial-gradient(120% 80% at 70% 20%, rgba(94, 184, 255, 0.14), transparent 60%),
    radial-gradient(90% 70% at 20% 90%, rgba(37, 99, 235, 0.12), transparent 60%),
    linear-gradient(180deg, #04101f 0%, #020812 100%);
  z-index: 0;
}
.xt-hud-particles__canvas {
  z-index: 1;
}
@media (prefers-reduced-motion: reduce) {
  .xt-hud-particles__canvas {
    display: none;
  }
}
</style>
