import { defineStore } from 'pinia'

import { dingtalkLoginApi, loginApi, meApi, qrLoginApi, workshopQuickEntryApi } from '../api/auth.js'

const TOKEN_KEY = 'aluminum_bypass_token'
const USER_KEY = 'aluminum_bypass_user'
const MACHINE_KEY = 'aluminum_bypass_machine'

function readStoredToken() {
  return sessionStorage.getItem(TOKEN_KEY) || ''
}

function readStoredJson(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key) || 'null')
  } catch {
    sessionStorage.removeItem(key)
    return null
  }
}

function normalizeUser(user) {
  if (user == null) return null
  return {
    ...user,
    assigned_shift_ids: user.assigned_shift_ids || [],
    data_scope_type: user.data_scope_type || 'self_team',
    is_mobile_user: Boolean(user.is_mobile_user),
    is_reviewer: Boolean(user.is_reviewer),
    is_manager: Boolean(user.is_manager)
  }
}

function normalizeMachine(machine) {
  if (machine == null) return null
  return {
    machine_id: machine.machine_id ?? null,
    machine_code: machine.machine_code || '',
    machine_name: machine.machine_name || '',
    workshop_id: machine.workshop_id ?? null,
    workshop_name: machine.workshop_name || '',
    qr_code: machine.qr_code || ''
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: readStoredToken(),
    user: normalizeUser(readStoredJson(USER_KEY)),
    machineContext: normalizeMachine(readStoredJson(MACHINE_KEY)),
    hydrated: false
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    role: (state) => state.user?.role || '',
    dataScopeType: (state) => state.user?.data_scope_type || 'self_team',
    displayName: (state) => state.user?.name || state.user?.username || '系统用户',
    isAdmin: (state) => state.user?.role === 'admin',
    isMachineBound: (state) => Boolean(state.machineContext?.machine_id),
    boundMachineId: (state) => state.machineContext?.machine_id || null,
    isMobileUser() {
      return this.isAdmin || Boolean(this.user?.is_mobile_user)
    },
    isReviewer() {
      return this.isAdmin || Boolean(this.user?.is_reviewer)
    },
    isManager() {
      return this.isAdmin || Boolean(this.user?.is_manager)
    },
    hasGlobalReviewScope() {
      return this.isAdmin || (this.isReviewer && (this.dataScopeType === 'all' || this.user?.workshop_id == null))
    },
    canAccessFillSurface() {
      return this.isMobileUser
    },
    entrySurface() {
      return this.canAccessFillSurface
    },
    isFillOnlyRole() {
      return this.canAccessFillSurface && !this.canAccessReviewSurface && !this.canAccessDesktopConfig
    },
    canAccessReviewSurface() {
      return this.isAdmin || this.isManager
    },
    reviewSurface() {
      return this.canAccessReviewSurface
    },
    canAccessDesktopConfig() {
      return this.isAdmin || this.isManager
    },
    adminSurface() {
      return this.canAccessDesktopConfig
    },
    superAdminSurface() {
      return this.isAdmin && this.entrySurface && this.reviewSurface && this.adminSurface
    },
    defaultSurface() {
      if (this.entrySurface && !this.reviewSurface && !this.adminSurface) return 'entry'
      if (this.reviewSurface && !this.adminSurface) return 'review'
      if (this.adminSurface) return 'admin'
      return 'login'
    },
    canAccessMobile() {
      return this.canAccessFillSurface
    },
    canAccessDesktop() {
      return this.canAccessReviewSurface || this.canAccessDesktopConfig
    },
    canAccessReviewDesk() {
      return this.canAccessReviewSurface
    },
    canAccessFactoryDashboard() {
      return this.canAccessReviewSurface
    },
    canAccessWorkshopDashboard() {
      return this.canAccessReviewSurface
    },
    canAccessStatisticsDashboard() {
      return this.canAccessReviewSurface
    },
    canAccessManagerDashboard() {
      return this.canAccessReviewSurface
    }
  },
  actions: {
    hydrate() {
      this.token = readStoredToken()
      this.user = normalizeUser(readStoredJson(USER_KEY))
      this.machineContext = normalizeMachine(readStoredJson(MACHINE_KEY))
      this.hydrated = true
    },
    setSession(token, user, machineContext = null) {
      this.token = token
      this.user = normalizeUser(user)
      this.machineContext = normalizeMachine(machineContext)
      sessionStorage.setItem(TOKEN_KEY, token)
      sessionStorage.setItem(USER_KEY, JSON.stringify(this.user))
      if (this.machineContext) {
        sessionStorage.setItem(MACHINE_KEY, JSON.stringify(this.machineContext))
      } else {
        sessionStorage.removeItem(MACHINE_KEY)
      }
    },
    setMachineContext(machineContext) {
      this.machineContext = normalizeMachine(machineContext)
      if (this.machineContext) {
        sessionStorage.setItem(MACHINE_KEY, JSON.stringify(this.machineContext))
      } else {
        sessionStorage.removeItem(MACHINE_KEY)
      }
    },
    setToken(token) {
      this.token = token || ''
      if (this.token) {
        sessionStorage.setItem(TOKEN_KEY, this.token)
      } else {
        sessionStorage.removeItem(TOKEN_KEY)
      }
    },
    logout() {
      this.token = ''
      this.user = null
      this.machineContext = null
      sessionStorage.removeItem(TOKEN_KEY)
      sessionStorage.removeItem(USER_KEY)
      sessionStorage.removeItem(MACHINE_KEY)
    },
    async login(payload) {
      const result = await loginApi(payload)
      this.setSession(result.access_token, result.user, result.machine_info)
      return result
    },
    async dingtalkLogin(code) {
      const result = await dingtalkLoginApi({ code })
      const token = result.access_token || result.token || ''
      if (token === '') throw new Error('钉钉登录未返回令牌')

      this.setToken(token)
      this.setMachineContext(null)

      try {
        const user = await meApi({
          headers: { Authorization: 'Bearer ' + token }
        })
        this.setSession(token, user, null)
        return { ...result, access_token: token, user, machine_info: null }
      } catch (error) {
        this.logout()
        throw error
      }
    },
    async qrLogin(qrCode) {
      const result = await qrLoginApi({ qr_code: qrCode })
      if (result.type === 'workshop_redirect') {
        return result
      }
      this.setSession(result.access_token, result.user, result.machine_info)
      return result
    },
    async fetchProfile() {
      if (this.token === '') return null
      const user = await meApi()
      this.user = normalizeUser(user)
      sessionStorage.setItem(USER_KEY, JSON.stringify(this.user))
      return this.user
    },
    async workshopQuickEntry({ workshop_code, role }) {
      const result = await workshopQuickEntryApi({ workshop_code, role })
      this.setSession(result.access_token, result.user, result.machine_info)
      return result
    }
  }
})
