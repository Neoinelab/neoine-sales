import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { lastQuery, NOW } from './testHelpers'

/**
 * Dashboard Quarter 토글(Quarter 다중 선택 AC-12~15·19): 두 탭 모두 연도 select 바로 다음에 Q1~Q4 토글 묶음이 있고,
 * 누를 때마다 켜고 꺼지며 활성 탭의 URL 키(`<탭>.quarter`)와 조회가 바뀐다. 넷 다 누르면 누른 채 보이지만 조회·Drill-down은 전체와 같다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)
const group = () => screen.getByRole('group', { name: 'Quarter' })
const button = (n: number) => within(group()).getByRole('button', { name: `Q${n}` })
const pressed = () => [1, 2, 3, 4].filter((n) => button(n).getAttribute('aria-pressed') === 'true')

describe('Quarter 토글의 위치 (AC-12)', () => {
  it.each(['status', 'forecast'])('puts the Quarter group right after the year select on the %s tab', async (tab) => {
    await renderAt(`/dashboard?tab=${tab}`)

    const form = within(await screen.findByRole('tabpanel')).getByRole('form', { name: 'Dashboard 필터' })
    const year = within(form).getByLabelText('연도')
    const owner = within(form).getByLabelText('담당자')

    expect(follows(year, group())).toBe(true)
    expect(follows(group(), owner)).toBe(true)
    expect(within(group()).getAllByRole('button').map((b) => b.textContent)).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  it.each(['status', 'forecast'])('has no Quarter select (combobox) on the %s tab', async (tab) => {
    await renderAt(`/dashboard?tab=${tab}`)
    await screen.findByRole('group', { name: 'Quarter' })

    expect(screen.queryByRole('combobox', { name: 'Quarter' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Quarter', { selector: 'select' })).not.toBeInTheDocument()
  })

  it('presses nothing by default', async () => {
    await renderAt('/dashboard')
    await screen.findByRole('group', { name: 'Quarter' })

    expect(pressed()).toEqual([])
  })
})

describe('토글 동작 (AC-13·30)', () => {
  it('turns quarters on and off on the active tab only, updating the URL and the request', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(button(1))
    await user.click(button(3))

    await waitFor(() => expect(location()).toContain('status.quarter=1%2C3'))
    expect(pressed()).toEqual([1, 3])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [1, 3] }))
    expect(location()).not.toContain('forecast.quarter')

    await user.click(button(1))
    await waitFor(() => expect(location()).toContain('status.quarter=3'))
    expect(location()).not.toContain('status.quarter=1')
    expect(pressed()).toEqual([3])

    await user.click(button(3))
    await waitFor(() => expect(location()).not.toContain('status.quarter'))
    expect(pressed()).toEqual([])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
  })

  it('writes the quarters ascending whatever the click order', async () => {
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(button(4))
    await user.click(button(2))

    await waitFor(() => expect(location()).toContain('status.quarter=2%2C4'))
  })

  it('works the same on the Forecast tab with its own key', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=forecast')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(button(2))

    await waitFor(() => expect(location()).toContain('forecast.quarter=2'))
    expect(location()).not.toContain('status.quarter')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
  })

  it('marks a pressed quarter with aria-pressed and keeps the other quarters unpressed', async () => {
    const { user } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(button(2))

    await waitFor(() => expect(button(2)).toHaveAttribute('aria-pressed', 'true'))
    for (const n of [1, 3, 4]) expect(button(n)).toHaveAttribute('aria-pressed', 'false')
  })

  it('reads the quarters of the address into pressed buttons', async () => {
    await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=4%2C1')
    await screen.findByRole('group', { name: 'Quarter' })

    expect(pressed()).toEqual([1, 4])
  })

  it('drops quarter items in the wrong format from the address', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=5%2Cx%2C2')
    await screen.findByRole('group', { name: 'Quarter' })

    expect(pressed()).toEqual([2])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
  })
})

describe('넷 다 누르면 전체와 같다 (AC-14, U6)', () => {
  it('keeps all four pressed and in the URL, but sends and links no quarter', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    for (const n of [1, 2, 3, 4]) await user.click(button(n))

    await waitFor(() => expect(location()).toContain('status.quarter=1%2C2%2C3%2C4'))
    expect(pressed()).toEqual([1, 2, 3, 4])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
    const tile = await screen.findByRole('link', { name: /Pipeline/ })
    expect(tile.getAttribute('href')).not.toContain('quarter')
  })

  it('shows the same numbers as with no quarter', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })
    const none = await gateway.dashboard.summary({ year: 2026 })

    for (const n of [1, 2, 3, 4]) await user.click(button(n))

    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
    const tile = await screen.findByRole('link', { name: /Open 합계/ })
    expect(tile).toHaveTextContent(`${none.forecast.openTotal.count}건`)
  })

  it('turning one of the four off sends the other three', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=1%2C2%2C3%2C4')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(button(4))

    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [1, 2, 3] }))
    expect(pressed()).toEqual([1, 2, 3])
  })
})

describe('sq는 무시한다 (AC-15, Selected Quarter 폐지)', () => {
  it('shows no Selected Quarter and leaves sq out of the next address', async () => {
    const { user, location } = await renderAt('/dashboard?tab=forecast&forecast.year=2026&sq=3')
    await screen.findByRole('group', { name: 'Quarter' })

    expect(screen.queryByText(/Selected Quarter/)).not.toBeInTheDocument()
    await user.click(button(1))

    await waitFor(() => expect(location()).toContain('forecast.quarter=1'))
    expect(location()).not.toContain('sq=')
    expect(pressed()).toEqual([1])
  })
})

describe('Status 탭 주의 필요 Deal은 분기와 무관하다 (AC-07)', () => {
  it('keeps the overdue and stale tile numbers and links when quarters are pressed', async () => {
    const { user } = await renderAt('/dashboard?tab=status')
    const overdue = await screen.findByRole('link', { name: /기한초과/ })
    const before = { text: overdue.textContent, href: overdue.getAttribute('href') }
    const stale = screen.getByRole('link', { name: /미업데이트/ })
    const staleBefore = { text: stale.textContent, href: stale.getAttribute('href') }

    await user.click(button(1))
    await user.click(button(3))

    await waitFor(() => expect(pressed()).toEqual([1, 3]))
    const after = await screen.findByRole('link', { name: /기한초과/ })
    expect({ text: after.textContent, href: after.getAttribute('href') }).toEqual(before)
    const staleAfter = screen.getByRole('link', { name: /미업데이트/ })
    expect({ text: staleAfter.textContent, href: staleAfter.getAttribute('href') }).toEqual(staleBefore)
  })
})
