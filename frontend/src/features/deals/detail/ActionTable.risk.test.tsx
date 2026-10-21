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
  await gateway.auth.quickLogin(USER_ID.root)
  const deal: DealDetail = { ...(await gateway.deals.get(code)), risk }
  const actions: DealAction[] = await gateway.actions.list(code, {})
  resetMock({ now: clockNow })
  expect(deal.nextAction).not.toBeNull()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ActionTable actions={actions} deal={deal} canEdit={false} me={null} onEdit={() => {}} onDelete={() => {}} />
    </QueryClientProvider>,
  )
  const table = screen.getByRole('table', { name: 'Action 목록' })
  return within(table).getAllByRole('row').slice(1)
}

describe('Action 행 기한초과 배지는 서버 risk를 따른다 (R3 Minor 1)', () => {
  it('shows no row badge when the server risk is null even though the due date is past the clock', async () => {
    const rows = await renderTable(null)
    expect(screen.queryByText('기한초과')).not.toBeInTheDocument()
    expect(rows.length).toBeGreaterThan(0)
  })

  it('shows no row badge when the server risk is only stale', async () => {
    await renderTable('stale')
    expect(screen.queryByText('기한초과')).not.toBeInTheDocument()
  })

  it('shows the badge on the current action row only when the server risk is overdue', async () => {
    const rows = await renderTable('overdue')
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
    for (const older of rows.slice(1)) expect(within(older).queryByText('기한초과')).not.toBeInTheDocument()
  })

  it('shows the badge when the server risk is overdue_stale', async () => {
    const rows = await renderTable('overdue_stale')
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
  })

  it('shows the badge for a server overdue even if the browser-side clock is before the due date', async () => {
    const rows = await renderTable('overdue', '2000-01-01T09:00:00+09:00')
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
  })
})
