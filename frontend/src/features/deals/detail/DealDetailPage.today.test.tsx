import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { formatRelativeTime } from '../../../shared/format'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf } from '../../../test/detailTestUtils'

const NOW = '2030-06-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => resetMock({ now: null }))

describe('상세와 mock 시계 (useToday)', () => {
  it('shows the last update as a relative time with the date in the tooltip', async () => {
    const code = await dealCodeOf(4)
    await gateway.auth.quickLogin('u-root')
    const deal = await gateway.deals.get(code)
    await renderAt(`/deals/${code}`)
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    const relative = formatRelativeTime(deal.lastUpdatedAt, NOW)
    expect(relative).toMatch(/일 전$/)
    expect(within(bar).getByText(relative)).toHaveAttribute('title', deal.lastUpdatedAt)
  })

  it('marks the overdue due date of the current next action by the mock clock date', async () => {
    const code = await dealCodeOf(3)
    await renderAt(`/deals/${code}`)
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
    for (const older of rows.slice(1)) expect(within(older).queryByText('기한초과')).not.toBeInTheDocument()
  })
})
