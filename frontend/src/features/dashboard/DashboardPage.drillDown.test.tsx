import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { listMemoryKey } from '../../shared/model/dealListMemory'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { clickBar, lastChart } from '../../test/chartMock'
import { defaultDealsUrl } from '../../test/dealsUrl'
import { dealInput } from '../../test/fake/testing'
import { renderAt } from '../../test/mockApp'
import { NOT_LOST_PARAM, NOW, OPEN_PARAM } from './testHelpers'

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

/** 같은 조건의 Deal 목록 건수(링크가 싣지 않는 조건 비교용). */
async function dealsTotal(query: Parameters<typeof gateway.deals.list>[0]) {
  return (await gateway.deals.list({ ...query, limit: 1 })).total
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
    expect(screen.queryByLabelText('Forecast 구분')).not.toBeInTheDocument()
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('2026')
    expect(screen.getByLabelText('Quarter')).toHaveDisplayValue('Q4')
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
  })

  it('restores the drill-down condition from the Deals menu on other screens', async () => {
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))
    await screen.findByLabelText('Status')

    await view.user.click(mainMenu(view).getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })
    await view.user.click(mainMenu(view).getByRole('link', { name: 'Deals' }))

    await waitFor(() => expect(view.location()).toBe(`/deals?year=2026&forecast=${OPEN_PARAM}`))
  })

  it('goes back to the Dashboard with the same tab and filters', async () => {
    const start = '/dashboard?tab=forecast&year=2026&quarter=3'
    const view = await renderAt(start)
    const row = await screen.findByRole('row', { name: /Q4/ })
    await view.user.click(within(row).getAllByRole('link')[0] as HTMLElement)
    await screen.findByLabelText('Status')

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
    await waitFor(() => expect(view.location()).toBe(defaultDealsUrl(NOW)))
  })

  it('opens the list from a chart bar the same way as from the table link', async () => {
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await screen.findByRole('table')

    clickBar(lastChart(), { index: 3 })

    const expected = `year=2026&status=poc_completed&forecast=${NOT_LOST_PARAM}`
    await waitFor(() => expect(view.location()).toBe(`/deals?${expected}`))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe(expected)
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

  it('Open total tile equals the Open total of the summary', async () => {
    const view = await renderAt('/dashboard?year=2026')
    const open = (await summaryOf({ year: 2026 })).forecast.openTotal.count
    expect(open).toBeGreaterThan(0)

    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))

    await listCount(view, open)
    expect(view.location()).toBe(`/deals?year=2026&forecast=${OPEN_PARAM}`)
  })

  it('Status table row equals its count and the total row equals the Lost-excluded total', async () => {
    const view = await renderAt('/dashboard?year=2026')
    const { statuses } = await summaryOf({ year: 2026 })
    const first = statuses.items.find((item) => item.count > 0)
    if (!first) throw new Error('건수가 있는 Status가 없습니다(시드 Deal 필요).')

    await view.user.click(within(await screen.findByRole('row', { name: new RegExp(first.name) })).getByRole('link'))
    await listCount(view, first.count)
    expect(view.location()).toBe(`/deals?year=2026&status=${first.key}&forecast=${NOT_LOST_PARAM}`)

    view.goTo(-1)
    expect(statuses.total.count).toBeGreaterThan(0)
    await view.user.click(within(await screen.findByRole('row', { name: /합계/ })).getByRole('link'))
    await listCount(view, statuses.total.count)
    expect(view.location()).toBe(`/deals?year=2026&forecast=${NOT_LOST_PARAM}`)
  })

  it('every status row equals its count (Lost deals of the status are not listed)', async () => {
    const { statuses } = await summaryOf({ year: 2026 })

    for (const item of statuses.items) {
      expect(await dealsTotal({ year: 2026, statusKey: item.key, forecastKeys: NOT_LOST_PARAM.split('%2C') })).toBe(item.count)
    }
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

  it('this quarter tile opens the open deals of the server quarter and equals its count', async () => {
    const view = await renderAt('/dashboard?year=2020')
    const { attention } = await summaryOf({ year: 2020 })
    expect(attention.closingThisQuarter.count).toBeGreaterThan(0)

    await view.user.click(await screen.findByRole('link', { name: /이번 분기/ }))

    const { year, quarter } = attention.closingThisQuarter
    await listCount(view, attention.closingThisQuarter.count)
    expect(view.location()).toBe(`/deals?year=${year}&quarter=${quarter}&forecast=${OPEN_PARAM}`)
  })

  it('this month tile on the Forecast tab equals its count', async () => {
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { attention } = await summaryOf({ year: 2026 })
    expect(attention.closingThisMonth.count).toBeGreaterThan(0)

    await view.user.click(await screen.findByRole('link', { name: /이번 달/ }))

    const { year, month } = attention.closingThisMonth
    await listCount(view, attention.closingThisMonth.count)
    expect(view.location()).toBe(`/deals?year=${year}&month=${month}&forecast=${OPEN_PARAM}`)
  })

  it('a quarter total row on the Forecast tab equals the total of the quarter', async () => {
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { quarters } = await summaryOf({ year: 2026 })
    const target = quarters.find((q) => q.total.count > 0)
    if (!target) throw new Error('건수가 있는 분기가 없습니다(시드 Deal 필요).')

    const row = await screen.findByRole('row', { name: new RegExp(`Q${target.quarter}`) })
    const totalLink = within(row).getAllByRole('link').at(-1)
    if (!totalLink) throw new Error('분기 합계 링크가 없습니다.')
    await view.user.click(totalLink)

    await listCount(view, target.total.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=${target.quarter}&forecast=${NOT_LOST_PARAM}`)
  })

  it('a quarter Open total cell on the Forecast tab equals the Open total of the quarter', async () => {
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { quarters } = await summaryOf({ year: 2026 })
    const target = quarters.find((q) => q.openTotal.count > 0)
    if (!target) throw new Error('Open 건수가 있는 분기가 없습니다(시드 Deal 필요).')

    const row = await screen.findByRole('row', { name: new RegExp(`Q${target.quarter}`) })
    const links = within(row).getAllByRole('link')
    await view.user.click(links.at(-2) as HTMLElement)

    await listCount(view, target.openTotal.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=${target.quarter}&forecast=${OPEN_PARAM}`)
  })

  it('the Selected Quarter Open total and total tiles equal the quarter numbers', async () => {
    const view = await renderAt('/dashboard?tab=forecast&year=2026&sq=3')
    const { quarters } = await summaryOf({ year: 2026 })
    const q3 = quarters.find((q) => q.quarter === 3)
    if (!q3) throw new Error('Q3가 없습니다.')
    const bottom = async () => within(await screen.findByRole('region', { name: 'Selected Quarter 구분별 금액(단위:천원)' }))

    await view.user.click(await (await bottom()).findByRole('link', { name: /Open 합계/ }))
    await listCount(view, q3.openTotal.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=3&forecast=${OPEN_PARAM}`)

    view.goTo(-1)
    await view.user.click(await (await bottom()).findByRole('link', { name: /^합계/ }))
    await listCount(view, q3.total.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=3&forecast=${NOT_LOST_PARAM}`)
  })

  it('an open forecast code added by the admin is in the Open total link and the list count equals the tile (AC-14·16)', async () => {
    const view = await renderAt('/deals?year=all', { role: 'admin' })
    await screen.findByRole('search', { name: 'Deal 필터' })
    const verbal = await gateway.codes.create({ kind: 'forecast', name: 'Verbal' })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Verbal 건', forecastKey: verbal.key, revenueDate: '2026-11-20' }))
    const { forecast, statuses } = await summaryOf({ year: 2026 })
    expect(forecast.columns.map((c) => c.key)).toContain(verbal.key)

    view.goTo('/dashboard?year=2026')
    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    const keys = new URLSearchParams((tile.getAttribute('href') ?? '').split('?')[1]).get('forecast')?.split(',')
    expect(keys).toContain(verbal.key)
    expect(keys).toEqual([...(keys ?? [])].sort())
    await view.user.click(tile)
    await listCount(view, forecast.openTotal.count)

    view.goTo(-1)
    await view.user.click(within(await screen.findByRole('row', { name: /합계/ })).getByRole('link'))
    await listCount(view, statuses.total.count)
    expect(view.location().split('forecast=')[1]).toContain(encodeURIComponent(verbal.key))
  })
})
