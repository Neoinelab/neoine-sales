import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { renderAt } from '../../test/mockApp'
import { lastQuery, mockSummary } from './testHelpers'

/**
 * 시간 기준 서버 통일 AC5: Dashboard의 기본 연도는 앱 시계(useToday, 서버 기준)로 정한다. 요약 응답의 today와 섞지 않는다.
 * Selected Quarter가 폐지돼(2026-10-28) 분기는 기본으로 아무것도 고르지 않은 상태(= 전체)다.
 */

afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const pressed = () => {
  const group = screen.getByRole('group', { name: 'Quarter' })
  return [1, 2, 3, 4].filter((n) => within(group).getByRole('button', { name: `Q${n}` }).getAttribute('aria-pressed') === 'true')
}

describe('Dashboard 기본값은 앱 시계 하나로 정한다', () => {
  it.each([
    ['year end in the app clock, next year in the response', '2026-12-31T23:30:00+09:00', '2027-01-01', 2026],
    ['new year in the app clock, previous year in the response', '2027-01-01T00:10:00+09:00', '2026-12-31', 2027],
    ['same day', '2026-07-15T09:00:00+09:00', '2026-07-15', 2026],
  ])('uses the app clock for the default year of both tabs and chooses no quarter: %s', async (_name, clockNow, responseToday, year) => {
    resetMock({ now: clockNow })
    const spy = mockSummary(dashboardSummaryFixture({ asOf: clockNow, today: responseToday }))

    await renderAt('/dashboard?tab=forecast')
    await screen.findByRole('group', { name: 'Quarter' })

    expect(screen.getByLabelText('연도')).toHaveValue(String(year))
    expect(lastQuery(spy)).toEqual({ year })
    expect(pressed()).toEqual([])
    expect(screen.queryByRole('group', { name: 'Selected Quarter' })).not.toBeInTheDocument()
  })
})
