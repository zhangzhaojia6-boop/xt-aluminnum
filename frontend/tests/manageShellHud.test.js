import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const shellPath = path.resolve('src/layout/ManageShell.vue')
const src = fs.readFileSync(shellPath, 'utf8')

const scriptMatch = src.match(/<script setup>([\s\S]*?)<\/script>/)
assert.ok(scriptMatch)
const scriptBody = scriptMatch[1]

test('ManageShell imports useHudTheme', () => {
  assert.match(scriptBody, /from ['"]\.\.\/composables\/useHudTheme\.js['"]/)
})

test('ManageShell opts into HUD without force (preference-driven)', () => {
  assert.match(scriptBody, /useHudTheme\(\s*\)/, 'must call useHudTheme() with no args')
  assert.doesNotMatch(scriptBody, /useHudTheme\(\s*\{\s*force:\s*true/)
})

test('ManageShell does not rewrite existing lifecycle handlers', () => {
  // The onBeforeUnmount block that removes keydown + assistant listeners
  // must still be present verbatim.
  assert.match(
    scriptBody,
    /onBeforeUnmount\(\(\)\s*=>\s*\{\s*window\.removeEventListener\(['"]keydown['"]/
  )
})

test('ManageShell keeps data-testid="manage-shell"', () => {
  assert.match(src, /data-testid="manage-shell"/)
})

test('ManageShell keeps 数据中枢 brand text', () => {
  assert.match(src, /数据中枢/)
})

test('ManageShell brand lands on the owner today tab', () => {
  assert.match(scriptBody, /const manageHomePath = computed\(\(\) => auth\.isWorkshopDirector \? '\/manage\/workshop-dashboard' : '\/manage\/today'\)/)
  assert.match(src, /class="xt-manage__brand" :to="navTo\(manageHomePath\)"/)
  assert.match(src, /class="xt-manage__drawer-brand" :to="navTo\(manageHomePath\)"/)
  assert.doesNotMatch(src, /class="xt-manage__brand" to="\/manage\/overview"/)
})

test('ManageShell wires the settings drawer trigger', () => {
  assert.match(src, /SettingsDrawer v-if="!isMobileViewport && settingsDrawerOpen" v-model:open="settingsDrawerOpen"/)
  assert.match(src, /v-if="!isMobileViewport" class="xt-manage__settings-trigger" type="button" aria-label="设置" @click="settingsDrawerOpen = true"/)
  assert.match(src, /if \(isMobileViewport\.value\) settingsDrawerOpen\.value = false/)
})

test('ManageShell adapts sidebar state to viewport width', () => {
  assert.match(scriptBody, /SIDEBAR_RAIL_BREAKPOINT\s*=\s*1180/)
  assert.match(scriptBody, /SIDEBAR_MOBILE_BREAKPOINT\s*=\s*900/)
  assert.match(scriptBody, /TOPBAR_COMPACT_BREAKPOINT\s*=\s*640/)
  assert.match(scriptBody, /const collapsed = computed\(\(\) => !isMobileViewport\.value && \(userCollapsed\.value \|\| isAutoRail\.value\)\)/)
  assert.match(scriptBody, /const navMode = computed\(\(\) => \{/)
  assert.match(scriptBody, /if \(isMobileViewport\.value\) return 'drawer'/)
  assert.match(scriptBody, /if \(isAutoRail\.value\) return 'auto-rail'/)
  assert.match(src, /:data-nav-mode="navMode"/)
  assert.match(scriptBody, /isCompactTopbar\.value = width <= TOPBAR_COMPACT_BREAKPOINT/)
  assert.match(scriptBody, /const drawerSize = computed\(\(\) => \(isMobileViewport\.value \? 'min\(312px, 88vw\)' : '300px'\)\)/)
  assert.match(scriptBody, /window\.addEventListener\(['"]resize['"], syncSidebarViewport/)
  assert.match(scriptBody, /window\.removeEventListener\(['"]resize['"], syncSidebarViewport/)
  assert.match(src, /--manage-sidebar-expanded:\s*216px/)
  assert.match(src, /width:\s*var\(--manage-sidebar-expanded\)/)
  assert.match(src, /margin-left:\s*var\(--manage-sidebar-expanded\)/)
})

test('ManageShell hides manual collapse control when viewport owns nav mode', () => {
  assert.match(src, /v-if="!isAutoRail && !isMobileViewport"/)
  assert.match(src, /:aria-label="collapsed \? '展开侧边栏' : '收起侧边栏'"/)
})

test('ManageShell keeps adaptive navigation usable in icon and mobile modes', () => {
  assert.match(scriptBody, /ChatDotRound,\s*Close,\s*Expand,\s*Fold,\s*Menu,\s*Search,\s*Setting/)
  assert.match(src, /'xt-manage--compact-topbar': isCompactTopbar/)
  assert.match(src, /class="xt-manage__drawer-overlay"/)
  assert.match(src, /:style="\{ width: drawerSize \}"/)
  assert.match(src, /class="xt-manage__drawer-head"/)
  assert.match(src, /class="xt-manage__drawer-brand" :to="navTo\(manageHomePath\)"/)
  assert.match(src, /aria-label="关闭导航" @click="drawerOpen = false"/)
  assert.match(src, /:aria-label="item\.title"/)
  assert.match(src, /:aria-current="isActive\(item\.path\) \? 'page' : undefined"/)
  assert.match(src, /:data-nav-title="item\.title"/)
  assert.match(src, /v-if="!collapsed \|\| isAutoRail" class="xt-manage__nav-group-label"/)
  assert.match(src, /v-if="!collapsed \|\| isAutoRail" class="xt-manage__nav-label"/)
  assert.match(src, /\.xt-manage--collapsed \.xt-manage__brand/)
  assert.match(src, /\.xt-manage--auto-rail \.xt-manage__sidebar:is\(:hover, :focus-within\)/)
  assert.doesNotMatch(src, /\.xt-manage--auto-rail \.xt-manage__sidebar:hover/)
  assert.match(src, /@media \(max-width: 900px\)/)
  assert.match(src, /@media \(max-width: 640px\)/)
  assert.match(src, /\.xt-manage__drawer-overlay/)
  assert.match(src, /display:\s*flex;\s*flex-direction:\s*column;/)
})

test('ManageShell mobile drawer shows full page titles instead of compact labels', () => {
  assert.match(src, /<nav class="xt-manage__drawer-nav" aria-label="移动端管理导航">/)
  assert.match(src, /<span>\{\{ item\.title \}\}<\/span>/)
})

test('ManageShell preserves desktop override while navigating inside mobile drawer', () => {
  assert.match(scriptBody, /function navTo\(path\)/)
  assert.match(scriptBody, /isMobileViewport\.value && route\.query\.desktop === ['"]1['"]/)
  assert.match(scriptBody, /return \{ path, query: \{ desktop: ['"]1['"] \} \}/)
  assert.match(src, /:to="navTo\(item\.path\)"/)
})

test('ManageShell closes transient overlays when route changes', () => {
  assert.match(scriptBody, /import \{ computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch \} from ['"]vue['"]/)
  assert.match(src, /<component :is="Component" :key="route\.path" \/>/)
  assert.match(scriptBody, /watch\(\(\) => route\.path/)
  assert.match(scriptBody, /searchOpen\.value = false/)
  assert.match(scriptBody, /drawerOpen\.value = false/)
  assert.match(scriptBody, /settingsDrawerOpen\.value = false/)
  assert.match(scriptBody, /assistantOpen\.value = false/)
  assert.match(scriptBody, /keyword\.value = ''/)
})

test('nested management pages get xt tokens from the global light theme', () => {
  const tokens = fs.readFileSync(path.resolve('src/design/xt-tokens.css'), 'utf8')
  for (const token of ['--xt-bg-panel', '--xt-bg-ink-panel', '--xt-text', '--xt-border']) {
    assert.match(tokens, new RegExp(`${token}:`))
  }
})

test('ManageShell removes app chrome from printed pages', () => {
  assert.match(src, /@media print/)
  assert.match(src, /\.xt-manage__sidebar,\s*\.xt-manage__topbar,\s*\.xt-manage__drawer-overlay\s*\{\s*display:\s*none;/)
  assert.match(src, /\.xt-manage__main,\s*\.xt-manage--collapsed \.xt-manage__main\s*\{\s*min-height:\s*auto;\s*margin-left:\s*0;/)
  assert.match(src, /\.xt-manage__content\s*\{\s*padding:\s*0;/)
})

test('ManageShell has no forbidden product lexicon', () => {
  assert.doesNotMatch(src, /cyberpunk|palantir|quantum|sci-?fi/i)
})
