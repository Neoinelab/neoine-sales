import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

/**
 * Deals 목록 연도 선택지(R2): '전체' + min(가장 이른 Expected Close 연도, 올해) ~ 내년 연속.
 * Dashboard Drill-down(`/deals?year=…`)의 범위 밖 연도는 선택지에 더해 '전체'로 보이지 않는다 (,).
 * 기준일 2026-10-15(올해 2026).
 */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const yearsFailure = () =>
  new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: '연도 목록을 불러오지 못했습니다.' })

describe('Deal 목록 연도 선택지에 URL 연도 포함', () => {
  // 선택지 밖 URL 연도는 선택된 항목으로 더해 보인다
  // 테스트 코드: DL-080
  it('shows an out-of-range year from the URL as the selected option', async () => {
    // given: 선택지 밖 연도가 든 주소
    await renderAt('/deals?year=2024')

    // when: 그 주소를 연다
    const year = await screen.findByLabelText('Close 연도')
    // then: 그 연도가 선택된 상태로 선택지에 있다
    expect(year).toHaveDisplayValue('2024')
    expect(optionNames(year)).toContain('2024')
  })

  // 이미 있는 URL 연도는 한 번만 보인다
  // 테스트 코드: DL-080
  it('adds the url year only once when it is already offered', async () => {
    // given: 선택지에 있는 연도가 든 주소
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2024 })
    await renderAt('/deals?year=2026')

    // when: 그 주소를 연다
    const year = await screen.findByLabelText('Close 연도')
    // then: 그 연도가 한 번만 있다
    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })
})

describe('연도 선택지 규칙 (R2)', () => {
  // 전체 + 가장 이른 연도~내년을 보인다
  // 테스트 코드: DL-080
  it('offers 전체 and every year from the earliest Expected Close to next year', async () => {
    // given: 여러 해에 걸친 Deal
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    await renderAt('/deals?year=2026')

    // when: 목록을 연다
    const year = await screen.findByLabelText('Close 연도')

    // then: 전체와 연속 연도가 오름차순이다
    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2023', '2024', '2025', '2026', '2027']))
  })

  // 올해+2년은 선택지에 없다
  // 테스트 코드: DL-080
  it('has no this year + 2 any more', async () => {
    // given: 시드 목록
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    await renderAt('/deals?year=2026')

    // when: 연도 선택지를 본다
    const year = await screen.findByLabelText('Close 연도')

    // then: 내년까지다
    await waitFor(() => expect(optionNames(year)).toContain('2023'))
    expect(optionNames(year)).not.toContain('2028')
  })

  // Deal이 없으면 올해·내년만 보인다
  // 테스트 코드: DL-080
  it('offers only this and next year (plus 전체) when there are no deals', async () => {
    // given: Deal이 없는 Fake
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: null })
    await renderAt('/deals?year=2026')

    // when: 목록을 연다
    const year = await screen.findByLabelText('Close 연도')

    // then: 전체·올해·내년뿐이다
    await waitFor(() => expect(gateway.deals.years).toHaveBeenCalled())
    expect(optionNames(year)).toEqual(['전체', '2026', '2027'])
  })

  // 내년보다 뒤 연도는 Deal이 있어도 없다
  // 테스트 코드: DL-080
  it('does not offer years after next year even when a deal closes then', async () => {
    // given: 먼 미래 Deal이 있는 Fake
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2029 })
    await renderAt('/deals?year=2026')

    // when: 목록을 연다
    const year = await screen.findByLabelText('Close 연도')

    // then: 내년 이후 연도는 없다
    await waitFor(() => expect(gateway.deals.years).toHaveBeenCalled())
    expect(optionNames(year)).toEqual(['전체', '2026', '2027'])
  })

  // year=all이면 전체가 첫 항목으로 선택된다
  // 테스트 코드: DL-082
  it('keeps 전체 first and selected for year=all', async () => {
    // given: year=all 주소
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2024 })
    await renderAt('/deals?year=all')

    // when: 그 주소를 연다
    const year = await screen.findByLabelText('Close 연도')

    // then: 전체가 첫 항목이고 선택돼 있다
    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('전체')
  })

  // 모든 역할이 연도 기준을 읽는다
  // 테스트 코드: DL-080
  it('reads the earliest year from the gateway of the signed-in user (every role)', async () => {
    // given: 역할별 로그인
    const years = vi.spyOn(gateway.deals, 'years')
    await renderAt('/deals?year=2026', { role: 'user' })

    // when: 목록을 연다
    await screen.findByLabelText('Close 연도')

    // then: 가장 이른 연도부터 선택지가 만들어진다
    await waitFor(() => expect(years).toHaveBeenCalled())
  })
})

describe('연도 목록을 받는 동안·받지 못했을 때 (R2)', () => {
  // 읽는 동안은 올해·내년만 보이고 끝나면 선택을 바꾸지 않고 넓힌다
  // 테스트 코드: DL-081
  it('offers this and next year while loading, then widens without changing the selection', async () => {
    // given: 연도 기준 응답이 늦는 Fake
    let finish: (value: { earliestYear: number | null }) => void = () => undefined
    vi.spyOn(gateway.deals, 'years').mockReturnValue(new Promise((resolve) => (finish = resolve)))
    await renderAt('/deals?year=2026')
    // when: 목록을 연다
    const year = await screen.findByLabelText('Close 연도')

    // then: 처음엔 올해·내년, 응답 뒤 선택지가 넓어지고 선택은 그대로다
    expect(optionNames(year)).toEqual(['전체', '2026', '2027'])

    finish({ earliestYear: 2023 })

    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2023', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  // 실패하면 올해·내년만 보이고 오류 배너를 보인다
  // 테스트 코드: DL-081
  it('falls back to this and next year and shows an error banner when the list fails', async () => {
    // given: 연도 기준 조회가 실패하는 Fake
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(yearsFailure())
    await renderAt('/deals?year=2026')

    // when: 목록을 연다
    const bar = within(await screen.findByRole('search', { name: 'Deal 필터' }))

    // then: 올해·내년 선택지와 오류 배너
    expect(await bar.findByRole('alert')).toHaveTextContent('연도 목록을 불러오지 못했습니다.')
    expect(optionNames(bar.getByLabelText('Close 연도'))).toEqual(['전체', '2026', '2027'])
  })

  // 연도 기준이 실패해도 목록은 나온다
  // 테스트 코드: DL-081
  it('still lists the deals when the year list fails', async () => {
    // given: 연도 기준 조회가 실패하는 Fake
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(yearsFailure())
    // when: 목록을 연다
    await renderAt('/deals?year=2026')

    // then: Deal 행이 보인다
    expect(await screen.findByRole('row', { name: /ITDR/ })).toBeInTheDocument()
  })
})
