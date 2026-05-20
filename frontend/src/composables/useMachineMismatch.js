import { ElMessage } from 'element-plus'

const MACHINE_BINDING_SOURCES = new Set(['direct_machine_code', 'route_inferred'])

function readBoundMachineId(auth) {
  if (!auth) return null
  if (auth.boundMachineId != null) return Number(auth.boundMachineId)
  const ctx = auth.machineContext
  return ctx?.machine_id != null ? Number(ctx.machine_id) : null
}

export function checkMachineMismatch(scanResult, auth) {
  if (!scanResult || scanResult.source !== 'coil_snapshot') return null
  if (!MACHINE_BINDING_SOURCES.has(scanResult.machine_binding_source)) return null
  const inferredId = scanResult.machine_line_id != null ? Number(scanResult.machine_line_id) : null
  if (inferredId == null) return null
  const boundId = readBoundMachineId(auth)
  if (boundId == null) return null
  if (inferredId === boundId) return null
  return {
    boundId,
    inferredId,
    boundName: auth.machineContext?.machine_name || auth.machineContext?.machine_code || '',
    inferredName: scanResult.machine_line_name || scanResult.machine_line_code || '',
  }
}

export function warnIfMachineMismatch(scanResult, auth, message = ElMessage) {
  const mismatch = checkMachineMismatch(scanResult, auth)
  if (!mismatch) return null
  message.warning({
    message: `登录机列与 MES 推断不一致：当前 ${mismatch.boundName || `机列 #${mismatch.boundId}`}，这卷应在 ${mismatch.inferredName || `机列 #${mismatch.inferredId}`}`,
    duration: 4500,
  })
  return mismatch
}
