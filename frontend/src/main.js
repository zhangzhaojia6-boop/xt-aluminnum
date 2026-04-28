import { createApp } from 'vue'
import { ElConfigProvider, ElLoadingDirective } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/es/components/config-provider/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import { createPinia } from 'pinia'

import App from './App.vue'
import router, { installRouterGuards } from './router'
import { setupApiInterceptors } from './api'
import { useAuthStore } from './stores/auth'
import './design/xt-tokens.css'
import './design/xt-base.css'
import './design/xt-motion.css'
import './design/industrial.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.component(ElConfigProvider.name, ElConfigProvider)
app.directive('loading', ElLoadingDirective)
app.config.globalProperties.$zhCn = zhCn

const authStore = useAuthStore(pinia)
authStore.hydrate()
installRouterGuards(router, authStore)
setupApiInterceptors(router, pinia)

app.use(router)

app.mount('#app')
