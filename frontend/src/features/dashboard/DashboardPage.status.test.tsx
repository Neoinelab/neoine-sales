import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatThousandWon } from '../../shared/model/money'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { link, mockSummary, NOT_LOST_PARAM, NOW, OPEN_PARAM } from './testHelpers'

/** Status 탭(슬라이드 7): Forecast 타일, Status 표, 주의 필요 Deal 타일. AC-12·13·14. 요약은 고정 값으로 바꿔 끼운다. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const won = (n: number) => formatThousandWon(n)

describe('Forecast 타일 (AC-12)', () => {
  it.each([
    ['Pipeline', 18, 320_000_000, '/deals?year=2026&forecast=pipeline'],
    ['Best', 6, 150_000_000, '/deals?year=2026&forecast=best'],
    ['Most Likely', 4, 90_000_000, '/deals?year=2026&forecast=most_likely'],
    ['Commit', 3, 70_000_000, '/deals?year=2026&forecast=commit'],
  ])('shows the %s tile with its count and amount and links to its deals', async (name, count, amount, href) => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')

    const tile = await screen.findByRole('link', { name: new RegExp(name) })

    expect(tile).toHaveTextContent(`${count}건`)
    expect(tile).toHaveTextContent(won(amount))
    expect(tile).toHaveAttribute('href', href)
  })

  it('shows the Open total tile', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')

    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    expect(tile).toHaveTextContent('31건')
    expect(tile).toHaveTextContent(won(630_000_000))
    expect(tile).toHaveAttribute('href', `/deals?year=2026&forecast=${OPEN_PARAM}`)
  })

  it('puts the period in the Won tile title: the year, or the year and quarter', async () => {
    mockSummary(dashboardSummaryFixture())
    const first = await renderAt('/dashboard?year=2026')
    const tile = await screen.findByRole('link', { name: /Won/ })
    expect(tile).toHaveTextContent('Won (2026)')
    expect(tile).toHaveTextContent('2건')
    expect(tile).toHaveTextContent(won(40_000_000))
    first.unmount()

    mockSummary(dashboardSummaryFixture({ period: { year: 2026, quarter: 3, from: '2026-07-01', to: '2026-09-30' } }))
    await renderAt('/dashboard?year=2026&quarter=3')

    expect(await screen.findByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026 Q3)')
  })

  it('has no Lost tile', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('link', { name: /Open 합계/ })

    expect(screen.queryByRole('link', { name: /Lost/ })).not.toBeInTheDocument()
  })

  it('shows the tiles in forecast code order, then Won', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('link', { name: /Open 합계/ })

    const tiles = [/Pipeline/, /Best/, /Most Likely/, /Commit/, /^Won/]
    const keys = tiles.map((name) => new URLSearchParams((screen.getByRole('link', { name }).getAttribute('href') ?? '').split('?')[1] ?? '').get('forecast'))
    const positions = tiles.map((name) => screen.getAllByRole('link').indexOf(screen.getByRole('link', { name })))
    expect(positions).toEqual([...positions].sort((a, b) => a - b))

    expect(keys).toEqual(['pipeline', 'best', 'most_likely', 'commit', 'won'])
  })

  it('makes a tile for a forecast code the admin added, named after the code', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      forecast: {
        ...base.forecast,
        columns: [
          ...base.forecast.columns.slice(0, 3),
          { key: 'verbal', name: 'Verbal', outcome: 'open', order: 35 },
          ...base.forecast.columns.slice(3),
        ],
        cells: { ...base.forecast.cells, verbal: { count: 5, amount: 55_000_000 } },
      },
    })
    await renderAt('/dashboard?year=2026')

    const tile = await screen.findByRole('link', { name: /Verbal/ })

    expect(tile).toHaveTextContent('5건')
    expect(tile).toHaveTextContent(won(55_000_000))
    expect(tile).toHaveAttribute('href', '/deals?year=2026&forecast=verbal')
  })

  it('shows a renamed code by its new name and keeps the key in the link', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      forecast: { ...base.forecast, columns: base.forecast.columns.map((c) => (c.key === 'commit' ? { ...c, name: '확정' } : c)) },
    })
    await renderAt('/dashboard?year=2026')

    const tile = await screen.findByRole('link', { name: /확정/ })

    expect(tile).toHaveAttribute('href', '/deals?year=2026&forecast=commit')
  })

  it('carries the quarter, owner and vendor into every tile link', async () => {
    mockSummary(dashboardSummaryFixture())
    const vendor = seedVendorId('Okta')
    await renderAt(`/dashboard?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`)

    const tile = await screen.findByRole('link', { name: /Pipeline/ })

    expect(tile).toHaveAttribute('href', `/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}&forecast=pipeline`)
    expect(screen.getByRole('link', { name: /Open 합계/ })).toHaveAttribute(
      'href',
      `/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${OPEN_PARAM}`,
    )
  })

  it('puts an open code added by the admin into the Open total link, not into the Won tile', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      forecast: {
        ...base.forecast,
        columns: [...base.forecast.columns.slice(0, 3), { key: 'verbal', name: 'Verbal', outcome: 'open', order: 35 }, ...base.forecast.columns.slice(3)],
        cells: { ...base.forecast.cells, verbal: { count: 5, amount: 55_000_000 } },
      },
    })
    await renderAt('/dashboard?year=2026')

    const href = (await screen.findByRole('link', { name: /Open 합계/ })).getAttribute('href') ?? ''

    expect(new URLSearchParams(href.split('?')[1]).get('forecast')?.split(',')).toEqual(['best', 'commit', 'most_likely', 'pipeline', 'verbal'])
  })

  it('shows the Open total as plain text, not a link, when there is no open forecast code (AC-17)', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      forecast: { columns: [{ key: 'won', name: 'Won', outcome: 'won', order: 5 }], cells: { won: { count: 2, amount: 40_000_000 } }, openTotal: { count: 0, amount: 0 } },
    })
    await renderAt('/dashboard?year=2026')

    await screen.findByRole('link', { name: /Won/ })

    expect(screen.queryByRole('link', { name: /Open 합계/ })).not.toBeInTheDocument()
    expect(screen.getAllByText('Open 합계').length).toBeGreaterThan(0)
  })
})

describe('Status 표 (AC-13)', () => {
  const ITEMS = [
    ['기회발굴', 14, 250_000_000, 'prospecting'],
    ['제품소개', 6, 110_000_000, 'introduction'],
    ['POC준비', 4, 80_000_000, 'poc_preparation'],
    ['POC완료', 3, 70_000_000, 'poc_completed'],
    ['기술평가', 2, 60_000_000, 'technical_evaluation'],
    ['가격협상', 2, 60_000_000, 'price_negotiation'],
    ['계약완료', 2, 40_000_000, 'contract_completed'],
  ] as const

  function cellsOf(row: HTMLElement): string[] {
    return [...row.querySelectorAll('td')].map((td) => td.textContent?.trim() ?? '')
  }

  it('has the Status, count and amount columns', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')

    const table = await screen.findByRole('table')
    const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent ?? '')

    expect(headers[0]).toBe('Status')
    expect(headers[1]).toBe('건수')
    expect(headers[2]).toContain('금액')
    expect(headers[2]).toContain('천원')
  })

  it.each(ITEMS)('shows %s with %i deals and the amount in thousand won', async (name, count, amount, key) => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    const row = screen.getByRole('row', { name: new RegExp(name) })
    const cells = cellsOf(row)

    expect(cells.at(-2)).toMatch(new RegExp(`^${count}건?$`))
    expect(cells.at(-1)).toBe(won(amount))
    expect(within(row).getByRole('link')).toHaveAttribute('href', `/deals?year=2026&status=${key}&forecast=${NOT_LOST_PARAM}`)
  })

  it('lists the statuses in code order with the total row last', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')
    const table = await screen.findByRole('table')

    const rows = within(table).getAllByRole('row').slice(1)

    expect(rows).toHaveLength(8)
    expect(rows.map((r) => r.textContent ?? '').map((text, i) => (i < 7 ? text.includes(ITEMS[i]?.[0] ?? '?') : text.includes('합계')))).toEqual(Array(8).fill(true))
  })

  it('makes the total row equal the total of the response and the sum of the rows', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    const totalRow = screen.getByRole('row', { name: /합계/ })
    const cells = cellsOf(totalRow)

    expect(cells.at(-2)).toMatch(/^33건?$/)
    expect(cells.at(-1)).toBe(won(670_000_000))
    expect(ITEMS.reduce((sum, item) => sum + item[1], 0)).toBe(33)
    expect(ITEMS.reduce((sum, item) => sum + item[2], 0)).toBe(670_000_000)
    expect(within(totalRow).getByRole('link')).toHaveAttribute('href', `/deals?year=2026&forecast=${NOT_LOST_PARAM}`)
  })

  it('keeps a status with no deals in the table as zero', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'technical_evaluation' ? { ...i, count: 0, amount: 0 } : i)) },
    })
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    const cells = cellsOf(screen.getByRole('row', { name: /기술평가/ }))

    expect(cells.at(-2)).toMatch(/^0건?$/)
    expect(cells.at(-1)).toBe('0')
  })

  it('follows a renamed status code', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'introduction' ? { ...i, name: '소개' } : i)) },
    })
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    expect(within(screen.getByRole('row', { name: /소개/ })).getByRole('link')).toHaveAttribute('href', `/deals?year=2026&status=introduction&forecast=${NOT_LOST_PARAM}`)
  })
})

describe('주의 필요 Deal 타일 (AC-14)', () => {
  it('shows the overdue, stale and this quarter tiles with their counts and links', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?year=2026&quarter=2')

    const overdue = await screen.findByRole('link', { name: /기한초과\D*4/ })
    const stale = screen.getByRole('link', { name: /14일 이상 미업데이트\D*5/ })
    const closing = screen.getByRole('link', { name: /이번 분기.*2026 Q4.*Expected Close\s*7/ })

    expect(overdue).toHaveAttribute('href', '/deals?overdue=1')
    expect(stale).toHaveAttribute('href', '/deals?stale=1')
    expect(closing).toHaveAttribute('href', `/deals?year=2026&quarter=4&forecast=${OPEN_PARAM}`)
  })

  it('shows the alert setting as the stale days, not a fixed 15', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, staleDays: 30, stale: 9 } })
    await renderAt('/dashboard')

    expect(await screen.findByRole('link', { name: /30일 이상 미업데이트\D*9/ })).toBeVisible()
    expect(screen.queryByRole('link', { name: /15일/ })).not.toBeInTheDocument()
  })

  it('applies only the owner and vendor to the attention links, not the period', async () => {
    mockSummary(dashboardSummaryFixture())
    const vendor = seedVendorId('Okta')
    await renderAt(`/dashboard?year=2026&quarter=2&owner=${USER_ID.kim}&vendor=${vendor}`)

    expect(await screen.findByRole('link', { name: /기한초과/ })).toHaveAttribute('href', `/deals?owner=${USER_ID.kim}&vendor=${vendor}&overdue=1`)
    expect(screen.getByRole('link', { name: /미업데이트/ })).toHaveAttribute('href', `/deals?owner=${USER_ID.kim}&vendor=${vendor}&stale=1`)
    expect(screen.getByRole('link', { name: /이번 분기/ })).toHaveAttribute(
      'href',
      `/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${OPEN_PARAM}`,
    )
  })

  it('takes this quarter from the server answer, not from the browser date', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, closingThisQuarter: { year: 2027, quarter: 1, count: 3 } } })
    await renderAt('/dashboard?year=2026')

    const closing = await screen.findByRole('link', { name: /이번 분기.*2027 Q1/ })

    expect(closing).toHaveTextContent('3')
    expect(closing).toHaveAttribute('href', `/deals?year=2027&quarter=1&forecast=${OPEN_PARAM}`)
  })

  it('shows zero counts as tiles too', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, overdue: 0, stale: 0 } })
    await renderAt('/dashboard')

    expect(await screen.findByRole('link', { name: /기한초과\D*0/ })).toBeVisible()
    expect(link(/미업데이트\D*0/)).toBeVisible()
  })

  it('does not show the Forecast tab attention tiles on the Status tab', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard')
    await screen.findByRole('link', { name: /기한초과/ })

    expect(screen.queryByRole('link', { name: /이번 달/ })).not.toBeInTheDocument()
  })
})
