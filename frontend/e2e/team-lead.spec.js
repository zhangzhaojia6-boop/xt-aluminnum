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
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    localStorage.removeItem('aluminum_bypass_machine')
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
            members: [
              {
                employee_id: 102,
                name: '李四',
                route: '/team-lead/worker/102/2026-05-03?shift_id=1'
              }
            ]
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

  await page.route('**/api/v1/attendance/results/102/2026-05-03', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        result: {
          id: 401,
          employee_id: 102,
          employee_no: 'E102',
          employee_name: '李四',
          business_date: '2026-05-03',
          attendance_status: 'absent',
          check_in_time: null,
          check_out_time: null,
          late_minutes: 0,
          early_leave_minutes: 0,
          data_status: 'pending',
          is_manual_override: false
        },
        schedules: [],
        clocks: [],
        exceptions: []
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

  await page.getByRole('link', { name: '李四' }).click()

  await expect(page).toHaveURL(/\/team-lead\/worker\/102\/2026-05-03\?shift_id=1$/)
  await expect(page.getByTestId('team-lead-worker-detail')).toContainText('李四')
})
