import { createApp } from 'vue'
import { ElConfigProvider, ElLoadingDirective } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/es/components/config-provider/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { setupApiInterceptors } from './api'
import { useAuthStore } from './stores/auth'
import './design/tokens.css'
import './design/theme.css'
import './styles.css'
import './reference-command/styles/command-tokens.css'
import './reference-command/styles/command-layout.css'
import './reference-command/styles/command-motion.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.component(ElConfigProvider.name, ElConfigProvider)
app.directive('loading', ElLoadingDirective)
app.config.globalProperties.$zhCn = zhCn

setupApiInterceptors(router, pinia)

const authStore = useAuthStore(pinia)
authStore.hydrate()

app.mount('#app')
