import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { clearQuarter, dataRows, describedText, openQuarterPanel, quarterButton, toggleQuarter } from './testHelpers'

/**
 * 목록 Quarter 다중 선택(Quarter 다중 선택 AC-22~27, U4~U6). 체크할 때마다 바로 조회하고 선택은 URL `quarter`
 * (오름차순·중복 제거·콤마 → `%2C`)가 정본이다. 기준일 2026-10-15(올해 2026).
 */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>
const monthNames = () => within(screen.getByLabelText('월')).getAllByRole('option').map((o) => o.textContent)
const quarterOfDate = (date: string) => Math.floor((Number(date.slice(5, 7)) - 1) / 3) + 1

describe('여러 Quarter 선택 (AC-22·23)', () => {
  it('lists the deals of any checked quarter and puts the ascending list in the URL', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    await toggleQuarter(user, 'Q3')
    await toggleQuarter(user, 'Q1')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1%2C3'))
    expect(quarterButton('Q1, Q3')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [1, 3] }))
    const expected = await gateway.deals.list({ year: 2026, quarters: [1, 3], limit: 100 })
    expect(expected.total).toBeGreaterThan(0)
    for (const item of expected.items) expect([1, 3]).toContain(quarterOfDate(item.revenueDate))
    await waitFor(() => expect(dataRows()).toHaveLength(Math.min(expected.total, 20)))
    expect(await screen.findByText(`총 ${expected.total}건`)).toBeVisible()
  })

  it('writes one quarter as a plain value', async () => {
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    await toggleQuarter(user, 'Q2')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=2'))
    expect(quarterButton('Q2')).toBeInTheDocument()
  })

  it('removes a quarter again and keeps the others', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3')
    await screen.findByRole('button', { name: 'Quarter Q1, Q3' })

    await toggleQuarter(user, 'Q1')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3'))
  })

  it('goes back to page 1 when the selection changes', async () => {
    const { user, location } = await renderAt('/deals?year=all&sort=revenueAmount&order=desc&page=2')
    await screen.findByRole('button', { name: '이전' })

    await toggleQuarter(user, 'Q4')

    await waitFor(() => expect(location()).toBe('/deals?year=all&sort=revenueAmount&order=desc&quarter=4'))
  })

  it('shows Q1 to Q4 as checkboxes of the Quarter group with the all button', async () => {
    const { user } = await renderAt('/deals?year=2026&quarter=2')
    await screen.findByRole('search', { name: 'Deal 필터' })

    const panel = await openQuarterPanel(user)

    expect(panel.getAllByRole('checkbox').map((c) => c.closest('label')?.textContent)).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    expect(panel.getByRole('checkbox', { name: 'Q2' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Q1' })).not.toBeChecked()
    expect(panel.getByRole('button', { name: '전체' })).toBeVisible()
  })

  it('clears every quarter with the all button', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3')
    await screen.findByRole('search', { name: 'Deal 필터' })

    await clearQuarter(user)

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(quarterButton('전체')).toBeInTheDocument()
  })

  it('opens an old single-quarter address as that one quarter', async () => {
    await renderAt('/deals?year=2026&quarter=4')

    expect(await screen.findByRole('button', { name: 'Quarter Q4' })).toBeVisible()
  })

  it('drops quarter items in the wrong format from the address', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=9%2C2%2Cx')
    await screen.findByRole('button', { name: 'Quarter Q2' })

    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [2] }))
  })
})

describe('Quarter에 따른 월 선택지 (AC-24·25)', () => {
  it('offers the months of the chosen quarters', async () => {
    await renderAt('/deals?year=2026&quarter=1%2C3')
    await screen.findByLabelText('월')

    expect(monthNames()).toEqual(['전체', '1월', '2월', '3월', '7월', '8월', '9월'])
  })

  it('keeps the month while the new quarters contain it and clears it when they do not', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3&month=8')
    await screen.findByLabelText('월')
    expect(screen.getByLabelText('월')).toHaveDisplayValue('8월')

    await toggleQuarter(user, 'Q1') // Q3만 남는다: 8월 유지
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3&month=8'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('8월')

    await toggleQuarter(user, 'Q1') // Q1·Q3
    await toggleQuarter(user, 'Q3') // Q1만 남는다: 8월은 선택지에 없다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
  })

  it('keeps the visible month when the all button clears the quarters', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3&month=8')
    await screen.findByLabelText('월')

    await clearQuarter(user)

    await waitFor(() => expect(location()).toBe('/deals?year=2026&month=8'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('8월')
  })

  it('sends only the month when it belongs to one of the chosen quarters (AC-26)', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=1%2C3&month=8')
    await screen.findByText(/총 \d+건/)

    expect(lastQuery(list)).toMatchObject({ year: 2026, month: 8 })
    expect(lastQuery(list)).not.toHaveProperty('quarters')
  })

  it('sends the quarters when the month is not in them (AC-26)', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=1%2C3&month=5')
    await screen.findByText(/총 \d+건/)

    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
    expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [1, 3] })
    expect(lastQuery(list)).not.toHaveProperty('month')
  })
})

describe('넷 다 체크하면 전체와 같다 (AC-22, U6)', () => {
  it('shows 전체, keeps the four checked and in the URL, but sends no quarter', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    for (const name of ['Q1', 'Q2', 'Q3', 'Q4']) await toggleQuarter(user, name)

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1%2C2%2C3%2C4'))
    expect(quarterButton('전체')).toBeInTheDocument()
    const panel = await openQuarterPanel(user)
    for (const name of ['Q1', 'Q2', 'Q3', 'Q4']) expect(panel.getByRole('checkbox', { name })).toBeChecked()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026 }))
    expect(lastQuery(list)).not.toHaveProperty('quarters')
    expect(monthNames()).toHaveLength(13)
  })

  it('lists the whole year for the four quarters', async () => {
    await renderAt('/deals?year=2026&quarter=1%2C2%2C3%2C4')
    const all = await gateway.deals.list({ year: 2026, limit: 1 })

    expect(await screen.findByText(`총 ${all.total}건`)).toBeVisible()
  })
})

describe('연도가 전체일 때 안내 (AC-27)', () => {
  it('tells that all years means this year once a quarter is checked', async () => {
    const { user } = await renderAt('/deals?year=all')
    await screen.findByRole('search', { name: 'Deal 필터' })
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()

    await toggleQuarter(user, 'Q2')

    expect(screen.getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(describedText(quarterButton('Q2'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')
  })
})
