// 不依赖 three.js，页面可以先判断再决定要不要下载 3D 代码。
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
