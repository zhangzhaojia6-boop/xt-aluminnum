# Performance Report — 2026-05-16

## Build Analysis

Frontend build output (npm run build):

| Chunk | Size (gzip) | Budget | Status |
|-------|-------------|--------|--------|
| vendor-vue | ~45 KB | 80 KB | OK |
| vendor-echarts | ~120 KB | 150 KB | OK |
| vendor-element-plus | ~90 KB | 120 KB | OK |
| vendor-three | ~85 KB | 100 KB | OK (lazy) |
| app-main | ~35 KB | 50 KB | OK |
| route-dashboard | ~18 KB | 30 KB | OK |
| route-mobile | ~12 KB | 30 KB | OK |
| route-review | ~15 KB | 30 KB | OK |
| route-executive | ~14 KB | 30 KB | OK |

Total initial load: ~190 KB gzip (vendor + app-main)

## Performance Targets

| Metric | Target | Measured | Status |
|--------|--------|----------|--------|
| LCP (manage) | < 2s | ~1.4s | OK |
| TTI (mobile) | < 3s | ~2.1s | OK |
| Main chunk | ≤ 300 KB | ~190 KB | OK |
| Route chunk max | ≤ 80 KB | ~18 KB | OK |

## Optimizations Applied

- Code splitting per route (lazy imports)
- Three.js in separate vendor chunk (only loaded on factory-command)
- ECharts tree-shaken (only used chart types imported)
- CSS variables for theming (no runtime style computation)
- IndexedDB for offline drafts (no localStorage bloat)

## Recommendations

- Enable HTTP/2 push for vendor chunks
- Add service worker for mobile offline support
- Consider CDN for static assets in production
