export const factoryLineGraphic = `
<svg viewBox="0 0 520 150" class="cmd-industry-graphic" role="img" aria-label="生产线">
  <defs>
    <linearGradient id="line-blue" x1="0" x2="1">
      <stop offset="0" stop-color="#1f6fff" stop-opacity=".12"/>
      <stop offset="1" stop-color="#14b8d4" stop-opacity=".24"/>
    </linearGradient>
  </defs>
  <path d="M28 104h464" stroke="#d5e2f1" stroke-width="2"/>
  <path d="M42 90h70l18-28h72l22 28h78l20-34h82l24 34h50" fill="none" stroke="#1f6fff" stroke-width="4" stroke-linejoin="round"/>
  <g fill="url(#line-blue)" stroke="#9dbdf5">
    <rect x="34" y="70" width="88" height="42" rx="8"/>
    <rect x="154" y="50" width="92" height="62" rx="8"/>
    <rect x="282" y="64" width="92" height="48" rx="8"/>
    <rect x="408" y="58" width="70" height="54" rx="8"/>
  </g>
  <g fill="#1f6fff">
    <circle cx="78" cy="116" r="5"/><circle cx="198" cy="116" r="5"/><circle cx="328" cy="116" r="5"/><circle cx="444" cy="116" r="5"/>
  </g>
</svg>`

export const dataFlowGraphic = `
<svg viewBox="0 0 360 120" class="cmd-industry-graphic" role="img" aria-label="数据流">
  <path d="M38 60h74l42-34 58 68 44-34h66" fill="none" stroke="#1f6fff" stroke-width="3" stroke-linecap="round"/>
  <g fill="#fff" stroke="#1f6fff" stroke-width="3">
    <circle cx="38" cy="60" r="13"/><circle cx="112" cy="60" r="13"/><circle cx="154" cy="26" r="13"/><circle cx="212" cy="94" r="13"/><circle cx="256" cy="60" r="13"/><circle cx="322" cy="60" r="13"/>
  </g>
</svg>`

export const equipmentOutlineGraphic = `
<svg viewBox="0 0 260 140" class="cmd-industry-graphic" role="img" aria-label="设备线框">
  <rect x="26" y="44" width="208" height="56" rx="10" fill="#f8fbff" stroke="#d5e2f1"/>
  <path d="M48 44V28h74v16M144 44V30h52v14M58 100v20M202 100v20" fill="none" stroke="#1f6fff" stroke-width="3" stroke-linecap="round"/>
  <path d="M54 70h152M72 84h110" stroke="#14b8d4" stroke-width="3" stroke-linecap="round"/>
</svg>`

export function statusRingGraphic(value = 72) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0))
  const dash = `${safeValue} ${100 - safeValue}`
  return `
<svg viewBox="0 0 42 42" class="cmd-status-ring" role="img" aria-label="完成率${safeValue}%">
  <circle cx="21" cy="21" r="15.9" fill="none" stroke="#e5edf7" stroke-width="4"/>
  <circle cx="21" cy="21" r="15.9" fill="none" stroke="#1f6fff" stroke-width="4" stroke-dasharray="${dash}" stroke-dashoffset="25" pathLength="100"/>
  <text x="21" y="24" text-anchor="middle" font-size="9" fill="#102033" font-weight="800">${safeValue}%</text>
</svg>`
}

export const riskPulseGraphic = `
<svg viewBox="0 0 120 80" class="cmd-industry-graphic" role="img" aria-label="风险脉冲">
  <path d="M8 42h24l10-20 18 42 16-30 10 8h26" fill="none" stroke="#ef3e52" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="88" cy="42" r="8" fill="#ef3e52" opacity=".18"/>
  <circle cx="88" cy="42" r="4" fill="#ef3e52"/>
</svg>`
