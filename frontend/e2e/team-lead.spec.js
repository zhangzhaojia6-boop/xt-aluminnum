import { expect, test } from '@playwright/test'

const leaderUser = {
  id: 7,
  username: 'leader',
  name: '一车间班长',
  role: 'team_leader',
  is_mobile_user: true,
  is_reviewer: false,
  is_manager: false,
  data_scope_type: 'self_team',
  workshop_id: 1,
  team_id: 10,
  assigned_shift_ids: [1]
}

async function setupTeamLeadSession(page) {
  const token = 'playwright-team-lead-token'

  await page.addInitScript(({ token, user }) => {
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    sessionStorage.removeItem('aluminum_bypass_machine')
  }, { token, user: leaderUser })

  await page.route('**/api/v1/team-lead/overview**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        scheduled_count: 5,
        attended_count: 4,
        reported_count: 3,
        returned_count: 2,
        reminder_count: 1,
        escalation_count: 0,
        pending_list: [
          {
            business_date: '2026-05-03',
            shift_id: 1,
            workshop: '冷轧一车间',
            shift: '白班',
            team: '甲班',
            members: ['李四']
          }
        ],
        returned_list: [
          { report_id: 201, returned_reason: '产出需核对', member: '班长' }
        ],
        reminder_list: [
          { shift: '白班', count: 1, last_at: '2026-05-03T09:00:00' }
        ],
        shift_health: 'red'
      })
    })
  })
}

test('team leader lands on one screen and can jump from pending work', async ({ page }) => {
  await setupTeamLeadSession(page)

  await page.goto('/login')

  await expect(page).toHaveURL(/\/team-lead$/)
  await expect(page.getByTestId('team-lead-shell')).toBeVisible()
  const overview = page.getByTestId('team-lead-overview')
  await expect(overview.getByText('排班').first()).toBeVisible()
  await expect(overview.getByText('出勤').first()).toBeVisible()
  await expect(overview.getByText('已报').first()).toBeVisible()
  await expect(overview.getByText('退回').first()).toBeVisible()
  await expect(overview.getByText('催报').first()).toBeVisible()
  await expect(page.locator('.team-lead-overview.is-red')).toBeVisible()

  await page.getByRole('link', { name: /冷轧一车间 · 白班 · 甲班/ }).click()

  await expect(page).toHaveURL(/\/entry\/report\/2026-05-03\/1$/)
})
