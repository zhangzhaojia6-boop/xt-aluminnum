import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'

// 暗色主题只覆盖管理端和登录页；手机填报、采购工作台保持浅色，不计入。
const EXCLUDED = [/\/views\/mobile\//, /\/layout\/EntryShell\.vue$/, /\/views\/procurement\//, /\/views\/entry\//]
const COLOR = /#[0-9a-fA-F]{3,8}\b|rgba?\(/g

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) walk(path, out)
    else if (name.endsWith('.vue')) out.push(path)
  }
  return out
}

function stripPrintBlocks(css) {
  let out = ''
  let i = 0
  while (i < css.length) {
    const at = css.indexOf('@media print', i)
    if (at === -1) return out + css.slice(i)
    out += css.slice(i, at)
    let depth = 0
    let j = css.indexOf('{', at)
    for (; j < css.length; j++) {
      if (css[j] === '{') depth += 1
      else if (css[j] === '}' && --depth === 0) break
    }
    i = j + 1
  }
  return out
}

export function countHardCodedColors(srcRoot) {
  const counts = {}
  for (const file of walk(srcRoot)) {
    const rel = relative(srcRoot, file).split(sep).join('/')
    if (EXCLUDED.some((re) => re.test(`/${rel}`))) continue
    const text = readFileSync(file, 'utf8')
    const style = (text.match(/<style[\s\S]*?<\/style>/g) || []).join('\n')
    const template = (text.match(/<template>[\s\S]*<\/template>/) || [''])[0]
    const n = (stripPrintBlocks(style).match(COLOR) || []).length + (template.match(COLOR) || []).length
    if (n) counts[rel] = n
  }
  return counts
}
