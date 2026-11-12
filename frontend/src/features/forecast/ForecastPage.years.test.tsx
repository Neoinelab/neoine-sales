import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { SNAPSHOT_PERIOD } from '../../test/fixtures/forecastSnapshot'
import { renderAt } from '../../test/mockApp'

/** Forecast 연도 선택지: 가장 이른 Expected Close 연도(없으면 올해) ~ 내년 연속. 스냅숏 모드여도 같은 규칙. 기준일 2026-10-15. */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const failure = () =>
  new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: '연도 목록을 불러오지 못했습니다.' })
const yearsOf = async () => screen.findByLabelText('연도')

describe('Forecast 연도 선택지', () => {
  // 테스트 코드: FC-063
  it('가장 이른 Expected Close 연도부터 내년까지 모든 연도를 보인다', async () => {
    // given: 가장 이른 연도가 2023인 연도 기준
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')

    // then: 2023~2027이 보이고 2026이 선택돼 있다
    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toEqual(['2023', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  // 테스트 코드: FC-063
  it('"전체"와 올해+2는 선택지에 없다', async () => {
    // given: 가장 이른 연도가 2023인 연도 기준
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')

    // then: 선택지에 "전체"와 2028이 없다
    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toContain('2023'))
    expect(optionNames(year)).not.toContain('전체')
    expect(optionNames(year)).not.toContain('2028')
  })

  // 테스트 코드: FC-064
  it('Deal이 없으면 올해와 내년만 보인다', async () => {
    // given: 가장 이른 연도가 없는(Deal 없음) 연도 기준
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: null })
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')

    // then: 2026, 2027만 보인다
    const year = await yearsOf()

    await waitFor(() => expect(gateway.deals.years).toHaveBeenCalled())
    expect(optionNames(year)).toEqual(['2026', '2027'])
  })

  // 테스트 코드: FC-063
  it('범위 밖 URL 연도는 선택지에 더해 선택된 상태로 둔다', async () => {
    // given: 가장 이른 연도가 2024인 연도 기준
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2024 })
    // when: 범위 밖 year=2031로 화면을 연다
    await renderAt('/forecast?year=2031')

    // then: 2031이 선택지에 더해지고 선택돼 있다
    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toEqual(['2024', '2025', '2026', '2027', '2031']))
    expect(year).toHaveDisplayValue('2031')
  })

  // 테스트 코드: FC-063
  it('스냅숏 모드에서도 연도 선택지가 같다', async () => {
    // given: 가장 이른 연도가 2023인 연도 기준
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    // when: 스냅숏을 고른 화면을 연다
    await renderAt(`/forecast?year=2026&quarter=3&snap=${SNAPSHOT_PERIOD}`)

    // then: 같은 연도 선택지가 보인다
    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toEqual(['2023', '2024', '2025', '2026', '2027']))
  })

  // 테스트 코드: FC-064
  it('읽는 동안은 올해·내년만 보이고 읽은 뒤 넓어진다', async () => {
    // given: 끝나지 않는 연도 기준 조회
    let finish: (value: { earliestYear: number | null }) => void = () => undefined
    vi.spyOn(gateway.deals, 'years').mockReturnValue(new Promise((resolve) => (finish = resolve)))
    await renderAt('/forecast?year=2026')
    // when: 2026 화면을 연다
    const year = await yearsOf()

    // then: 읽는 동안 2026, 2027만 보인다
    expect(optionNames(year)).toEqual(['2026', '2027'])

    // when: 연도 기준 조회가 끝난다
    finish({ earliestYear: 2024 })

    // then: 2024~2027로 넓어지고 2026이 선택돼 있다
    await waitFor(() => expect(optionNames(year)).toEqual(['2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  // 테스트 코드: FC-064
  it('연도 기준을 읽지 못하면 올해·내년만 보이고 필터 안에 오류 배너를 보인다', async () => {
    // given: 실패하는 연도 기준 조회
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(failure())
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')

    // then: 필터 안에 서버 문구의 배너가 있고 선택지는 2026, 2027이다
    const filters = within(await screen.findByRole('form', { name: 'Forecast 필터' }))

    expect(await filters.findByRole('alert')).toHaveTextContent('연도 목록을 불러오지 못했습니다.')
    expect(optionNames(filters.getByLabelText('연도'))).toEqual(['2026', '2027'])
  })
})
