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
  // 최종 업데이트는 앱 시계 기준 상대 시각으로 보인다
  // 테스트 코드: DL-058
  it('shows the last update relative to the mock clock, not the real clock', async () => {
    // given: 앱 시계를 고정한다
    await renderAt('/deals?q=새론병원 PAM')
    const row = await rowOf(/새론병원 PAM/)
    const deals = await gateway.deals.list({ keyword: '새론병원 PAM' })
    // when: 목록을 연다
    const expected = formatRelativeTime(deals.items[0]!.lastUpdatedAt, NOW)
    // then: 최종 업데이트 칸이 시계 기준 상대 표기다
    expect(expected).toMatch(/일 전$/)
    expect(within(row).getByText(expected)).toBeVisible()
  })

  // 연도 선택지는 앱 시계의 올해부터 내년까지다
  // 테스트 코드: DL-080
  it('offers the year filter from the mock clock year to next year', async () => {
    // given: 앱 시계를 고정한다
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    // when: 목록을 연다
    const year = screen.getByLabelText('연도')
    // then: 연도 선택지가 시계 기준 올해~내년이다
    expect(within(year).getByRole('option', { name: '2030' })).toBeInTheDocument()
    expect(within(year).getByRole('option', { name: '2031' })).toBeInTheDocument()
    expect(within(year).queryByRole('option', { name: '2032' })).not.toBeInTheDocument() // 내년까지만
    expect(within(year).queryByRole('option', { name: '2026' })).not.toBeInTheDocument()
  })

  // 최종 업데이트 title은 서버 오프셋 시각이다
  // 테스트 코드: DL-058
  it('shows the last update stamp in the server offset', async () => {
    // given: 서버 오프셋 시각의 최종 업데이트
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => {
      const page = await original(query)
      return { ...page, items: page.items.map((item) => ({ ...item, lastUpdatedAt: '2030-06-14T23:30:00-05:00' })) }
    })

    await renderAt('/deals?q=새론병원 PAM')
    const row = await rowOf(/새론병원 PAM/)

    // when: 마우스를 올릴 칸을 확인한다
    const stamp = row.querySelector('time')
    // then: title이 서버 오프셋 시각이다
    expect(stamp).toHaveAttribute('title', '2030-06-14 23:30')
    expect(stamp).toHaveAttribute('datetime', '2030-06-14T23:30:00-05:00')
  })
})
