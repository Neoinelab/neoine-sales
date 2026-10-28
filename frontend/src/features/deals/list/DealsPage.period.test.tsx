import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { clearQuarter, dataRows, describedText, quarterButton, toggleQuarter } from './testHelpers'

/** Quarter와 월(2026-10-26 개편, AC-10~14). 기준일 2026-10-15(올해 2026). */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('분기 안의 월만 선택 (AC-10)', () => {
  it('offers only the months of the chosen quarter', async () => {
    await renderAt('/deals?year=2026&quarter=2')
    await screen.findByLabelText('월')

    expect(optionNames(screen.getByLabelText('월'))).toEqual(['전체', '4월', '5월', '6월'])
  })

  it.each([
    [1, ['전체', '1월', '2월', '3월']],
    [3, ['전체', '7월', '8월', '9월']],
    [4, ['전체', '10월', '11월', '12월']],
  ])('offers the months of Q%i', async (quarter, names) => {
    await renderAt(`/deals?year=2026&quarter=${quarter}`)
    await screen.findByLabelText('월')

    expect(optionNames(screen.getByLabelText('월'))).toEqual(names)
  })

  it('offers all twelve months when the quarter is set to all', async () => {
    const { user } = await renderAt('/deals?year=2026&quarter=2')
    await screen.findByLabelText('월')

    await clearQuarter(user)

    expect(optionNames(screen.getByLabelText('월'))).toEqual(['전체', ...Array.from({ length: 12 }, (_, i) => `${i + 1}월`)])
  })
})

describe('월을 골라도 분기는 유지 (AC-11)', () => {
  it('keeps the quarter, sends only the month and lists that month', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByText(/총 \d+건/)

    await user.selectOptions(screen.getByLabelText('월'), '11월')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=4&month=11'))
    expect(quarterButton('Q4')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026, month: 11 }))
    expect(lastQuery(list)).not.toHaveProperty('quarters')

    const expected = await gateway.deals.list({ year: 2026, month: 11, limit: 100 })
    const quarter = await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })
    expect(expected.total).toBeGreaterThan(0)
    expect(expected.total).toBeLessThan(quarter.total)
    for (const item of expected.items) expect(item.revenueDate.startsWith('2026-11')).toBe(true)
    await waitFor(() => expect(dataRows()).toHaveLength(expected.total))
  })
})

describe('분기에 속하지 않는 월 (AC-12)', () => {
  it('shows all months and queries the quarter only', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=4&month=3')
    await screen.findByText(/총 \d+건/)

    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
    expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [4] })
    expect(lastQuery(list)).not.toHaveProperty('month')
  })

  it('shows the month that belongs to the quarter', async () => {
    await renderAt('/deals?year=2026&quarter=4&month=11')
    await screen.findByLabelText('월')

    expect(screen.getByLabelText('월')).toHaveDisplayValue('11월')
  })
})

describe('분기를 바꿀 때 월 (AC-13, Quarter 다중 선택 AC-25)', () => {
  it('keeps the month while a checked quarter set still contains it, and clears it once it does not', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=4&month=11')
    await screen.findByLabelText('월')

    await toggleQuarter(user, 'Q3') // Q3·Q4 → 7~12월에 11월이 있다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3%2C4&month=11'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('11월')

    await toggleQuarter(user, 'Q4') // Q3만 → 11월은 선택지에 없다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
  })

  it('keeps the visible month when the quarters are cleared with the all button', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=4&month=11')
    await screen.findByLabelText('월')

    await clearQuarter(user)

    await waitFor(() => expect(location()).toBe('/deals?year=2026&month=11'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('11월')
  })

  it('drops a month hidden by the quarter when the quarters are cleared', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=4&month=3')
    await screen.findByLabelText('월')

    await clearQuarter(user)

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })
})

describe('연도가 전체일 때 안내 (AC-14)', () => {
  it('tells that all years means this year and hides it when a year is chosen', async () => {
    const { user } = await renderAt('/deals?year=all&quarter=1')
    await screen.findByLabelText('Quarter')

    expect(describedText(quarterButton('Q1'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')
    expect(screen.getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(screen.queryByText(/연도를 고르지 않으면/)).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('연도'), '2027')

    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })

  it('shows the hint under the month when there is no quarter', async () => {
    await renderAt('/deals?year=all&month=3')
    await screen.findByLabelText('월')

    const label = screen.getByLabelText('월').closest('label') as HTMLElement
    expect(within(label).getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(screen.getAllByText(/연도가 전체이면/)).toHaveLength(1)
  })

  it('shows no hint when only the year is all', async () => {
    await renderAt('/deals?year=all')
    await screen.findByLabelText('월')

    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })
})
