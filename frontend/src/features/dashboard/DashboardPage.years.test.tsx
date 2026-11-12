import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { NOW } from './testHelpers'

/** Dashboard 연도 선택지: 가장 이른 Expected Close 연도(없으면 올해) ~ 내년 연속. '전체'는 없다. 기준일 2026-10-15. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const failure = () =>
  new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: '연도 목록을 불러오지 못했습니다.' })
const yearsOf = async () => screen.findByLabelText('연도')

describe('Dashboard 연도 선택지', () => {
  // 테스트 코드: DSH-033
  it.each(['status', 'forecast'])('%s 탭 연도 선택지는 가장 이른 Expected Close 연도부터 내년까지다', async (tab) => {
    // given: 가장 이른 Expected Close 연도가 2023이다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })

    // when: 탭을 연다
    await renderAt(`/dashboard?tab=${tab}&year=2026`)
    const year = await yearsOf()

    // then: 2023~2027이 연속으로 있고 2026이 선택되어 있다
    await waitFor(() => expect(optionNames(year)).toEqual(['2023', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  // 테스트 코드: DSH-033
  it('전체 항목과 내후년(2028)이 없다', async () => {
    // given: 가장 이른 Expected Close 연도가 2023이다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })

    // when: /dashboard를 연다
    await renderAt('/dashboard?year=2026')
    const year = await yearsOf()

    // then: 선택지에 전체와 2028이 없다
    await waitFor(() => expect(optionNames(year)).toContain('2023'))
    expect(optionNames(year)).not.toContain('전체')
    expect(optionNames(year)).not.toContain('2028')
  })

  // 테스트 코드: DSH-033
  it('Deal이 없으면 올해와 내년만 보인다', async () => {
    // given: Deal이 없어 가장 이른 연도가 없다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: null })

    // when: /dashboard를 연다
    await renderAt('/dashboard?year=2026')
    const year = await yearsOf()

    // then: 2026·2027뿐이다
    await waitFor(() => expect(gateway.deals.years).toHaveBeenCalled())
    expect(optionNames(year)).toEqual(['2026', '2027'])
  })

  // 테스트 코드: DSH-033
  it('범위 밖 URL 연도는 선택지에 더해 선택된 채 둔다', async () => {
    // given: 가장 이른 Expected Close 연도가 2024이다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2024 })

    // when: URL 연도 2020으로 연다
    await renderAt('/dashboard?year=2020')
    const year = await yearsOf()

    // then: 2020이 선택지에 더해져 선택되어 있다
    await waitFor(() => expect(optionNames(year)).toEqual(['2020', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2020')
  })

  // 테스트 코드: DSH-033
  it('읽는 동안은 올해와 내년이고 읽은 뒤 넓어진다', async () => {
    // given: 끝나지 않는 연도 조회
    let finish: (value: { earliestYear: number | null }) => void = () => undefined
    vi.spyOn(gateway.deals, 'years').mockReturnValue(new Promise((resolve) => (finish = resolve)))

    // when: 화면을 연다
    await renderAt('/dashboard?year=2026')
    const year = await yearsOf()

    // then: 읽는 동안 선택지는 올해와 내년이다
    expect(optionNames(year)).toEqual(['2026', '2027'])

    // when: 가장 이른 연도 2024가 도착한다
    finish({ earliestYear: 2024 })

    // then: 2024부터 내년까지로 넓어지고 2026이 선택되어 있다
    await waitFor(() => expect(optionNames(year)).toEqual(['2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  // 테스트 코드: DSH-033
  it('연도 조회가 실패하면 올해·내년과 필터 안 오류 배너를 보인다', async () => {
    // given: 연도 조회가 실패한다
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(failure())

    // when: /dashboard를 연다
    await renderAt('/dashboard?year=2026')
    const filters = within(await screen.findByRole('form', { name: 'Dashboard 필터' }))

    // then: 필터 안에 오류 배너가 있고 선택지는 올해·내년이다
    expect(await filters.findByRole('alert')).toHaveTextContent('연도 목록을 불러오지 못했습니다.')
    expect(optionNames(filters.getByLabelText('연도'))).toEqual(['2026', '2027'])
  })
})
