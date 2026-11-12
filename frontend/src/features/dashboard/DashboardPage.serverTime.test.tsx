import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { renderAt } from '../../test/mockApp'
import { lastQuery, mockSummary } from './testHelpers'

/**
 * Dashboard의 기본 연도는 앱 시계(useToday, 서버 기준)로 정한다. 요약 응답의 today와 섞지 않는다.
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
  // 테스트 코드: DSH-027
  it.each([
    ['앱 시계는 연말, 응답은 다음 해', '2026-12-31T23:30:00+09:00', '2027-01-01', 2026],
    ['앱 시계는 새해, 응답은 지난 해', '2027-01-01T00:10:00+09:00', '2026-12-31', 2027],
    ['같은 날', '2026-07-15T09:00:00+09:00', '2026-07-15', 2026],
  ])('기본 연도는 앱 시계로 정하고 분기는 고르지 않는다: %s', async (_name, clockNow, responseToday, year) => {
    // given: 앱 시계와 요약 응답의 today가 다를 수 있는 응답
    resetMock({ now: clockNow })
    const spy = mockSummary(dashboardSummaryFixture({ asOf: clockNow, today: responseToday }))

    // when: 조건 없이 Forecast 탭을 연다
    await renderAt('/dashboard?tab=forecast')
    await screen.findByRole('group', { name: 'Quarter' })

    // then: 연도는 앱 시계의 해이고 조회는 연도뿐이며 분기는 모두 눌리지 않았다
    expect(screen.getByLabelText('연도')).toHaveValue(String(year))
    expect(lastQuery(spy)).toEqual({ year })
    expect(pressed()).toEqual([])
    expect(screen.queryByRole('group', { name: 'Selected Quarter' })).not.toBeInTheDocument()
  })
})
