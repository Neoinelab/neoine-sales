import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { listMemoryKey } from '../../shared/model/dealListMemory'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { clickBar, lastChart } from '../../test/chartMock'
import { renderAt } from '../../test/mockApp'
import { NOW } from './testHelpers'

/**
 * Drill-down으로 연 Deal 목록(Dashboard AC-17·18). Fake 게이트웨이의 실제 계산을 쓰고 화면을 끝까지 따라간다.
 * 이전에 기억한 목록 조건은 남지 않고(병합 없음), 필터 바에 같은 값이 보이며, 목록의 "총 N건"이 누른 숫자와 같다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

type View = Awaited<ReturnType<typeof renderAt>>

const STALE_MEMORY = 'status=prospecting&sort=owner&order=asc&page=3&q=old'

function mainMenu(view: View) {
  return within(view.getAllByRole('navigation', { name: '주 메뉴' })[0] as HTMLElement)
}

async function summaryOf(query: Parameters<typeof gateway.dashboard.summary>[0]) {
  return gateway.dashboard.summary(query)
}

async function listCount(view: View, count: number) {
  await view.findByText(`총 ${count}건`)
}

describe('이동과 목록 조건 (AC-17)', () => {
  it('opens the Deals list with only the clicked condition, dropping the remembered sort and page', async () => {
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await screen.findByRole('link', { name: /Pipeline/ })

    await view.user.click(screen.getByRole('link', { name: /Pipeline/ }))

    await waitFor(() => expect(view.location()).toBe('/deals?year=2026&forecast=pipeline'))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=2026&forecast=pipeline')
  })

  it('shows the same values in the list filter bar', async () => {
    const view = await renderAt(`/dashboard?year=2026&quarter=4&owner=${USER_ID.kim}`)
    const row = await screen.findByRole('row', { name: /기회발굴/ })

    await view.user.click(within(row).getByRole('link'))

    expect(await screen.findByLabelText('Status')).toHaveDisplayValue('기회발굴')
    expect(screen.getByLabelText('Forecast 구분')).toHaveDisplayValue('Lost 제외')
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('2026')
    expect(screen.getByLabelText('Quarter')).toHaveDisplayValue('Q4')
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
  })

  it('restores the drill-down condition from the Deals menu on other screens', async () => {
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))
    await screen.findByLabelText('Forecast 구분')

    await view.user.click(mainMenu(view).getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })
    await view.user.click(mainMenu(view).getByRole('link', { name: 'Deals' }))

    await waitFor(() => expect(view.location()).toBe('/deals?year=2026&outcome=open'))
  })

  it('goes back to the Dashboard with the same tab and filters', async () => {
    const start = '/dashboard?tab=forecast&year=2026&quarter=3'
    const view = await renderAt(start)
    const row = await screen.findByRole('row', { name: /Q4/ })
    await view.user.click(within(row).getAllByRole('link')[0] as HTMLElement)
    await screen.findByLabelText('Forecast 구분')

    view.goTo(-1)

    await waitFor(() => expect(view.location()).toBe(start))
    expect(await screen.findByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByLabelText('Quarter')).not.toBeInTheDocument()
  })

  it('does not store the Dashboard condition as the remembered list condition', async () => {
    const view = await renderAt(`/dashboard?year=2026&quarter=2&owner=${USER_ID.park}`)
    await screen.findByRole('link', { name: /Pipeline/ })

    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBeNull()
    await view.user.click(mainMenu(view).getByRole('link', { name: 'Deals' }))
    await waitFor(() => expect(view.location()).toBe('/deals'))
  })

  it('opens the list from a chart bar the same way as from the table link', async () => {
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await screen.findByRole('table')

    clickBar(lastChart(), { index: 3 })

    await waitFor(() => expect(view.location()).toBe('/deals?year=2026&status=poc_completed&outcome=not_lost'))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=2026&status=poc_completed&outcome=not_lost')
  })
})

describe('목록의 건수가 누른 숫자와 같다 (AC-18)', () => {
  it('Forecast tile: the count of a forecast code that has deals', async () => {
    const view = await renderAt('/dashboard?year=2026')
    const { forecast } = await summaryOf({ year: 2026 })
    const column = forecast.columns.find((c) => (forecast.cells[c.key]?.count ?? 0) > 0)
    if (!column) throw new Error('건수가 있는 Forecast가 없습니다(시드 Deal 필요).')

    await view.user.click(await screen.findByRole('link', { name: new RegExp(column.name) }))

    await listCount(view, forecast.cells[column.key]?.count ?? -1)
  })

  it('Open total tile', async () => {
    const view = await renderAt('/dashboard?year=2026')
    const expected = (await summaryOf({ year: 2026 })).forecast.openTotal.count
    expect(expected).toBeGreaterThan(0)

    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))

    await listCount(view, expected)
  })

  it('Status table row and its total row', async () => {
    const view = await renderAt('/dashboard?year=2026')
    const { statuses } = await summaryOf({ year: 2026 })
    const first = statuses.items.find((item) => item.count > 0)
    if (!first) throw new Error('건수가 있는 Status가 없습니다(시드 Deal 필요).')

    await view.user.click(within(await screen.findByRole('row', { name: new RegExp(first.name) })).getByRole('link'))
    await listCount(view, first.count)

    view.goTo(-1)
    await view.user.click(within(await screen.findByRole('row', { name: /합계/ })).getByRole('link'))
    await listCount(view, statuses.total.count)
  })

  it('overdue and stale tiles ignore the period', async () => {
    const view = await renderAt('/dashboard?year=2026&quarter=1')
    const { attention } = await summaryOf({ year: 2026, quarter: 1 })
    expect(attention.overdue).toBeGreaterThan(0)

    await view.user.click(await screen.findByRole('link', { name: /기한초과/ }))
    await listCount(view, attention.overdue)
    expect(view.location()).toBe('/deals?overdue=1')

    view.goTo(-1)
    await view.user.click(await screen.findByRole('link', { name: /미업데이트/ }))
    if (attention.stale === 0) await screen.findByText('조건에 맞는 Deal이 없습니다.')
    else await listCount(view, attention.stale)
  })

  it('this quarter tile counts the open deals of the server quarter', async () => {
    const view = await renderAt('/dashboard?year=2020')
    const { attention } = await summaryOf({ year: 2020 })
    expect(attention.closingThisQuarter.count).toBeGreaterThan(0)

    await view.user.click(await screen.findByRole('link', { name: /이번 분기/ }))

    await listCount(view, attention.closingThisQuarter.count)
    expect(view.location()).toBe(`/deals?year=${attention.closingThisQuarter.year}&quarter=${attention.closingThisQuarter.quarter}&outcome=open`)
  })

  it('this month tile on the Forecast tab', async () => {
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { attention } = await summaryOf({ year: 2026 })
    expect(attention.closingThisMonth.count).toBeGreaterThan(0)

    await view.user.click(await screen.findByRole('link', { name: /이번 달/ }))

    await listCount(view, attention.closingThisMonth.count)
  })

  it('a quarter total row on the Forecast tab', async () => {
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { quarters } = await summaryOf({ year: 2026 })
    const target = quarters.find((q) => q.total.count > 0)
    if (!target) throw new Error('건수가 있는 분기가 없습니다(시드 Deal 필요).')

    const row = await screen.findByRole('row', { name: new RegExp(`Q${target.quarter}`) })
    const totalLink = within(row)
      .getAllByRole('link')
      .find((a) => a.getAttribute('href')?.includes('outcome=not_lost'))
    if (!totalLink) throw new Error('분기 합계 링크가 없습니다.')
    await view.user.click(totalLink)

    await listCount(view, target.total.count)
  })
})
