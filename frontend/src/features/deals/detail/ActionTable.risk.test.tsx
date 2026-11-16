import { defaultMock } from '../../../test/fake/default'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import type { DealAction, DealDetail, Risk } from '../../../shared/model/types'
import { ActionTable } from './ActionTable'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'

const NOW = '2030-06-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => resetMock({ now: null }))

/** 시드 Deal 3(현재 Next Action의 Due가 지남)을 불러와 서버 risk만 바꿔 표를 그린다. */
async function renderTable(risk: Risk, clockNow = NOW) {
  const code = await dealCodeOf(3)
  await defaultMock.signInAs(USER_ID.root)
  const deal: DealDetail = { ...(await gateway.deals.get(code)), risk }
  const actions: DealAction[] = await gateway.actions.list(code, {})
  resetMock({ now: clockNow })
  expect(deal.nextAction).not.toBeNull()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ActionTable actions={actions} deal={deal} canEdit={false} me={null} onOpen={() => {}} sort={{ sort: 'actedAt', order: 'desc' }} onSort={() => {}} />
    </QueryClientProvider>,
  )
  const table = screen.getByRole('table', { name: 'Action 목록' })
  return within(table).getAllByRole('row').slice(1)
}

describe('Action 행 기한초과 배지는 서버 risk를 따른다', () => {
  // 서버 risk가 null이면 Due가 시계보다 지나 보여도 배지가 없다.
  // 테스트 코드: RK-058
  it('shows no row badge when the server risk is null even though the due date is past the clock', async () => {
    // when: Actions 탭 표를 그린다 (전제: Due가 지난 것처럼 보이는 Actions 목록이고 서버 risk가 null이다)
    const rows = await renderTable(null)
    // then: '기한초과' 배지가 없다
    expect(screen.queryByText('기한초과')).not.toBeInTheDocument()
    expect(rows.length).toBeGreaterThan(0)
  })

  // 서버 risk가 stale뿐이면 배지가 없다.
  // 테스트 코드: RK-058
  it('shows no row badge when the server risk is only stale', async () => {
    // when: Actions 탭 표를 그린다 (전제: 서버 risk가 stale이다)
    await renderTable('stale')
    // then: '기한초과' 배지가 없다
    expect(screen.queryByText('기한초과')).not.toBeInTheDocument()
  })

  // 서버 risk가 overdue면 현재 기준 행에만 배지를 단다.
  // 테스트 코드: RK-058
  it('shows the badge on the current action row only when the server risk is overdue', async () => {
    // when: Actions 탭 표를 그린다 (전제: 서버 risk가 overdue이다)
    const rows = await renderTable('overdue')
    // then: 첫 행(현재 기준 행)에만 '기한초과' 배지가 있고 이전 행에는 없다
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
    for (const older of rows.slice(1)) expect(within(older).queryByText('기한초과')).not.toBeInTheDocument()
  })

  // 서버 risk가 overdue_stale이어도 기준 행에 배지를 단다.
  // 테스트 코드: RK-058
  it('shows the badge when the server risk is overdue_stale', async () => {
    // when: Actions 탭 표를 그린다 (전제: 서버 risk가 overdue_stale이다)
    const rows = await renderTable('overdue_stale')
    // then: 첫 행에 '기한초과' 배지가 보인다
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
  })

  // 브라우저 시계가 Due 이전이어도 서버가 overdue면 배지가 보인다.
  // 테스트 코드: RK-058
  it('shows the badge for a server overdue even if the browser-side clock is before the due date', async () => {
    // when: Actions 탭 표를 그린다 (전제: 서버 risk가 overdue이고 시계는 2000-01-01이다)
    const rows = await renderTable('overdue', '2000-01-01T09:00:00+09:00')
    // then: 첫 행에 '기한초과' 배지가 보인다
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
  })
})
