export const commandLogoMark = `
<svg width="38" height="38" viewBox="0 0 38 38" role="img" aria-label="鑫泰铝业">
  <rect x="2" y="2" width="34" height="34" rx="10" fill="#1f6fff"/>
  <path d="M10 25h18M13 21h12M16 17h6M12 27V16l7-5 7 5v11" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="28" cy="10" r="3" fill="#14b8d4"/>
</svg>`

export const commandMiniMark = `
<svg width="22" height="22" viewBox="0 0 22 22" role="img" aria-label="生产协同">
  <rect x="2" y="2" width="18" height="18" rx="6" fill="#eaf2ff"/>
  <path d="M6 14h10M7 11h8M9 8h4" fill="none" stroke="#1f6fff" stroke-width="1.8" stroke-linecap="round"/>
</svg>`

export function commandLogoHtml(title = '鑫泰铝业生产协同系统') {
  return `${commandLogoMark}<strong>${title}</strong>`
}
