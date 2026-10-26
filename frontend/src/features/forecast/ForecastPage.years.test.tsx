import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { SNAPSHOT_PERIOD } from '../../test/fixtures/forecastSnapshot'
import { renderAt } from '../../test/mockApp'

/** Forecast 연도 선택지(R2): 가장 이른 Expected Close 연도(없으면 올해) ~ 내년 연속. 스냅숏 모드여도 같은 규칙. 기준일 2026-10-15. */
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

describe('Forecast 연도 선택지 (R2)', () => {
  it('offers every year from the earliest Expected Close to next year', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    await renderAt('/forecast?year=2026')

    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toEqual(['2023', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  it('has no 전체 option and no this year + 2', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    await renderAt('/forecast?year=2026')

    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toContain('2023'))
    expect(optionNames(year)).not.toContain('전체')
    expect(optionNames(year)).not.toContain('2028')
  })

  it('offers this and next year when there are no deals', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: null })
    await renderAt('/forecast?year=2026')

    const year = await yearsOf()

    await waitFor(() => expect(gateway.deals.years).toHaveBeenCalled())
    expect(optionNames(year)).toEqual(['2026', '2027'])
  })

  it('adds a url year outside the range and keeps it selected', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2024 })
    await renderAt('/forecast?year=2031')

    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toEqual(['2024', '2025', '2026', '2027', '2031']))
    expect(year).toHaveDisplayValue('2031')
  })

  it('keeps the same options in snapshot mode', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    await renderAt(`/forecast?year=2026&quarter=3&snap=${SNAPSHOT_PERIOD}`)

    const year = await yearsOf()

    await waitFor(() => expect(optionNames(year)).toEqual(['2023', '2024', '2025', '2026', '2027']))
  })

  it('offers this and next year while loading and widens afterwards', async () => {
    let finish: (value: { earliestYear: number | null }) => void = () => undefined
    vi.spyOn(gateway.deals, 'years').mockReturnValue(new Promise((resolve) => (finish = resolve)))
    await renderAt('/forecast?year=2026')
    const year = await yearsOf()

    expect(optionNames(year)).toEqual(['2026', '2027'])

    finish({ earliestYear: 2024 })

    await waitFor(() => expect(optionNames(year)).toEqual(['2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  it('falls back to this and next year and shows an error banner in the filters when the list fails', async () => {
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(failure())
    await renderAt('/forecast?year=2026')

    const filters = within(await screen.findByRole('form', { name: 'Forecast 필터' }))

    expect(await filters.findByRole('alert')).toHaveTextContent('연도 목록을 불러오지 못했습니다.')
    expect(optionNames(filters.getByLabelText('연도'))).toEqual(['2026', '2027'])
  })
})
