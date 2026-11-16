import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
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
  it.each([
    ['2030-06-15', '오늘'],
    ['2030-06-14', '어제'],
    ['2030-06-12', '3일 전'],
  ])('shows the last update %s as %s relative to the mock clock date', async (lastUpdatedOn, expected) => {
    // given: 앱 시계(2030-06-15)를 고정하고 한 Deal의 최종 업데이트일을 정한다
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => {
      const page = await original(query)
      return { ...page, items: page.items.map((item) => ({ ...item, lastUpdatedOn })) }
    })

    // when: 목록을 연다
    await renderAt('/deals?q=새론병원 PAM')
    const row = await rowOf(/새론병원 PAM/)

    // then: 최종 업데이트 칸이 시계 날짜 기준 '오늘·어제·N일 전'이고 시:분 상대 표기가 없다
    expect(within(row).getByText(expected)).toBeVisible()
    expect(within(row).queryByText(/방금 전|분 전|시간 전/)).not.toBeInTheDocument()
  })

  // 연도 선택지는 앱 시계의 올해부터 내년까지다
  // 테스트 코드: DL-080
  it('offers the year filter from the mock clock year to next year', async () => {
    // given: 앱 시계를 고정한다
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    // when: 목록을 연다
    const year = screen.getByLabelText('Close 연도')
    // then: 연도 선택지가 시계 기준 올해~내년이다
    expect(within(year).getByRole('option', { name: '2030' })).toBeInTheDocument()
    expect(within(year).getByRole('option', { name: '2031' })).toBeInTheDocument()
    expect(within(year).queryByRole('option', { name: '2032' })).not.toBeInTheDocument() // 내년까지만
    expect(within(year).queryByRole('option', { name: '2026' })).not.toBeInTheDocument()
  })

  // 최종 업데이트 title은 날짜(YYYY-MM-DD)이고 시각이 없다
  // 테스트 코드: DL-058
  it('shows the last update title as the date only', async () => {
    // given: 최종 업데이트일이 2030-06-12인 Deal
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => {
      const page = await original(query)
      return { ...page, items: page.items.map((item) => ({ ...item, lastUpdatedOn: '2030-06-12' })) }
    })

    await renderAt('/deals?q=새론병원 PAM')
    const row = await rowOf(/새론병원 PAM/)

    // when: 마우스를 올릴 칸을 확인한다
    const cell = within(row).getByText('3일 전')
    // then: title이 날짜 YYYY-MM-DD뿐이다
    expect(cell.closest('[title]')).toHaveAttribute('title', '2030-06-12')
  })
})
