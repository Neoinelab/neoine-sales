import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

/**
 * Deals 목록 연도 선택지(R2): '전체' + min(가장 이른 Expected Close 연도, 올해) ~ 내년 연속.
 * Dashboard Drill-down(`/deals?year=…`)의 범위 밖 연도는 선택지에 더해 '전체'로 보이지 않는다(AC-17, AC2-3).
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

describe('Deal 목록 연도 선택지에 URL 연도 포함 (AC-17)', () => {
  it('shows an out-of-range year from the URL as the selected option', async () => {
    await renderAt('/deals?year=2024')

    const year = await screen.findByLabelText('연도')
    expect(year).toHaveDisplayValue('2024')
    expect(optionNames(year)).toContain('2024')
  })

  it('adds the url year only once when it is already offered', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2024 })
    await renderAt('/deals?year=2026')

    const year = await screen.findByLabelText('연도')
    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })
})

describe('연도 선택지 규칙 (R2 AC2-2·2-4·2-7)', () => {
  it('offers 전체 and every year from the earliest Expected Close to next year', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    await renderAt('/deals?year=2026')

    const year = await screen.findByLabelText('연도')

    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2023', '2024', '2025', '2026', '2027']))
  })

  it('has no this year + 2 any more', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    await renderAt('/deals?year=2026')

    const year = await screen.findByLabelText('연도')

    await waitFor(() => expect(optionNames(year)).toContain('2023'))
    expect(optionNames(year)).not.toContain('2028')
  })

  it('offers only this and next year (plus 전체) when there are no deals', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: null })
    await renderAt('/deals?year=2026')

    const year = await screen.findByLabelText('연도')

    await waitFor(() => expect(gateway.deals.years).toHaveBeenCalled())
    expect(optionNames(year)).toEqual(['전체', '2026', '2027'])
  })

  it('does not offer years after next year even when a deal closes then', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2029 })
    await renderAt('/deals?year=2026')

    const year = await screen.findByLabelText('연도')

    await waitFor(() => expect(gateway.deals.years).toHaveBeenCalled())
    expect(optionNames(year)).toEqual(['전체', '2026', '2027'])
  })

  it('keeps 전체 first and selected for year=all', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2024 })
    await renderAt('/deals?year=all')

    const year = await screen.findByLabelText('연도')

    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('전체')
  })

  it('reads the earliest year from the gateway of the signed-in user (every role)', async () => {
    const years = vi.spyOn(gateway.deals, 'years')
    await renderAt('/deals?year=2026', { role: 'user' })

    await screen.findByLabelText('연도')

    await waitFor(() => expect(years).toHaveBeenCalled())
  })
})

describe('연도 목록을 받는 동안·받지 못했을 때 (R2 AC2-5)', () => {
  it('offers this and next year while loading, then widens without changing the selection', async () => {
    let finish: (value: { earliestYear: number | null }) => void = () => undefined
    vi.spyOn(gateway.deals, 'years').mockReturnValue(new Promise((resolve) => (finish = resolve)))
    await renderAt('/deals?year=2026')
    const year = await screen.findByLabelText('연도')

    expect(optionNames(year)).toEqual(['전체', '2026', '2027'])

    finish({ earliestYear: 2023 })

    await waitFor(() => expect(optionNames(year)).toEqual(['전체', '2023', '2024', '2025', '2026', '2027']))
    expect(year).toHaveDisplayValue('2026')
  })

  it('falls back to this and next year and shows an error banner when the list fails', async () => {
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(yearsFailure())
    await renderAt('/deals?year=2026')

    const bar = within(await screen.findByRole('search', { name: 'Deal 필터' }))

    expect(await bar.findByRole('alert')).toHaveTextContent('연도 목록을 불러오지 못했습니다.')
    expect(optionNames(bar.getByLabelText('연도'))).toEqual(['전체', '2026', '2027'])
  })

  it('still lists the deals when the year list fails', async () => {
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(yearsFailure())
    await renderAt('/deals?year=2026')

    expect(await screen.findByRole('row', { name: /ITDR/ })).toBeInTheDocument()
  })
})
