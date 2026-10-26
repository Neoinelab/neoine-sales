import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { formatRelativeTime } from '../../../shared/format'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

/** 실제 시각과 크게 다른 mock 시계(시드 날짜는 이 시각 기준 상대값). */
const NOW = '2030-06-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

describe('목록과 mock 시계 (useToday)', () => {
  it('shows the last update relative to the mock clock, not the real clock', async () => {
    await renderAt('/deals?q=새론병원 PAM')
    const row = await rowOf(/새론병원 PAM/)
    const deals = await gateway.deals.list({ keyword: '새론병원 PAM' })
    const expected = formatRelativeTime(deals.items[0]!.lastUpdatedAt, NOW)
    expect(expected).toMatch(/일 전$/)
    expect(within(row).getByText(expected)).toBeVisible()
  })

  it('offers the year filter from the mock clock year to next year', async () => {
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const year = screen.getByLabelText('연도')
    expect(within(year).getByRole('option', { name: '2030' })).toBeInTheDocument()
    expect(within(year).getByRole('option', { name: '2031' })).toBeInTheDocument()
    expect(within(year).queryByRole('option', { name: '2032' })).not.toBeInTheDocument() // 내년까지만
    expect(within(year).queryByRole('option', { name: '2026' })).not.toBeInTheDocument()
  })

  it('shows the last update stamp in the server offset', async () => {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => {
      const page = await original(query)
      return { ...page, items: page.items.map((item) => ({ ...item, lastUpdatedAt: '2030-06-14T23:30:00-05:00' })) }
    })

    await renderAt('/deals?q=새론병원 PAM')
    const row = await rowOf(/새론병원 PAM/)

    const stamp = row.querySelector('time')
    expect(stamp).toHaveAttribute('title', '2030-06-14 23:30')
    expect(stamp).toHaveAttribute('datetime', '2030-06-14T23:30:00-05:00')
  })
})
