import { setupReviewSessionAndMocks } from './review-mocks'

const fillOnlyUser = {
  id: 2,
  username: 'operator',
  name: 'Playwright Operator',
  role: 'operator',
  is_mobile_user: true,
  is_reviewer: false,
  is_manager: false,
  data_scope_type: 'self_team',
  assigned_shift_ids: []
}

// 只填报账号在管理端登录页会被拦下（「当前账号不能进入管理端」），只能直接写入已保存的会话
export async function setupStoredFillOnlySession(page) {
  const token = 'playwright-fill-token'
  await setupReviewSessionAndMocks(page, { token, user: fillOnlyUser, skipLogin: true })
  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
  }, { token, user: fillOnlyUser })
}
