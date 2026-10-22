import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatThousandWon } from '../../shared/model/money'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { mockSummary, NOW } from './testHelpers'

/** Forecast 탭(슬라이드 9): Forecast 타일, 분기 표(Q1~Q4), 선택 Quarter 강조, Closing Attention 타일. AC-15. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const won = (n: number) => formatThousandWon(n)
const hrefsOf = (row: HTMLElement) => within(row).getAllByRole('link').map((a) => a.getAttribute('href'))

async function openForecastTab(url = '/dashboard?tab=forecast&year=2026') {
  mockSummary(dashboardSummaryFixture())
  const view = await renderAt(url)
  await screen.findByRole('table')
  return view
}

describe('Forecast 탭의 Forecast 타일', () => {
  it('shows the same tiles as the Status tab', async () => {
    await openForecastTab()
    // 하단 Selected Quarter 타일도 같은 제목을 쓰므로 상단(연간) 타일 영역으로 한정한다.
    const top = within(screen.getByRole('region', { name: 'Forecast 구분별 금액(단위:천원)' }))

    const tile = top.getByRole('link', { name: /Pipeline/ })

    expect(tile).toHaveTextContent('18건')
    expect(tile).toHaveTextContent(won(320_000_000))
    expect(top.getByRole('link', { name: /Open 합계/ })).toHaveTextContent('31건')
    expect(top.getByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026)')
    expect(screen.queryByRole('link', { name: /Lost/ })).not.toBeInTheDocument()
  })
})

describe('분기 표 (AC-15)', () => {
  it('has the four quarters as rows under the header', async () => {
    await openForecastTab()

    const rows = within(screen.getByRole('table')).getAllByRole('row')

    expect(rows).toHaveLength(5)
    ;['Q1', 'Q2', 'Q3', 'Q4'].forEach((quarter, i) => expect(rows[i + 1]).toHaveTextContent(quarter))
  })

  it('shows the amount of each forecast code, the open total and the total (open + won) of a quarter', async () => {
    await openForecastTab()

    const q1 = screen.getByRole('row', { name: /Q1/ })

    for (const amount of [40_000_000, 20_000_000, 10_000_000, 100_000_000, 110_000_000]) {
      expect(q1).toHaveTextContent(won(amount))
    }
    const q3 = screen.getByRole('row', { name: /Q3/ })
    for (const amount of [100_000_000, 50_000_000, 30_000_000, 20_000_000, 200_000_000, 230_000_000]) {
      expect(q3).toHaveTextContent(won(amount))
    }
  })

  it('shows the forecast columns without Lost in the header, in code order', async () => {
    await openForecastTab()

    const header = within(screen.getByRole('table')).getAllByRole('columnheader').map((h) => h.textContent ?? '')

    expect(header.join('|')).not.toContain('Lost')
    const positions = ['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won'].map((name) => header.findIndex((text) => text.includes(name)))
    expect(positions.every((p) => p >= 0)).toBe(true)
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
  })

  it('links the cells and the total of a quarter to its deals', async () => {
    await openForecastTab()

    const hrefs = hrefsOf(screen.getByRole('row', { name: /Q2/ }))

    expect(hrefs).toContain('/deals?year=2026&quarter=2&forecast=pipeline')
    expect(hrefs).toContain('/deals?year=2026&quarter=2&forecast=best')
    expect(hrefs).toContain('/deals?year=2026&quarter=2&outcome=not_lost')
  })

  it('carries only the owner and vendor into the quarter links, never the chosen quarter', async () => {
    const vendor = seedVendorId('Okta')
    await openForecastTab(`/dashboard?tab=forecast&year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`)

    const hrefs = hrefsOf(screen.getByRole('row', { name: /Q4/ }))

    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=pipeline`)
    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&outcome=not_lost`)
  })

  it('shows all four quarters whatever the URL quarter or sq is', async () => {
    await openForecastTab('/dashboard?tab=forecast&year=2026&quarter=3&sq=2')

    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(5)
  })
})

/**
 * 계약 변경(2026-10-23): 선택 분기는 상단 Quarter 필터(`quarter`)가 아니라 하단 Selected Quarter(`sq`)가 정한다.
 * 항상 한 분기가 선택되므로(기본: 올해면 오늘 분기, 아니면 Q1) '아무것도 강조하지 않음' 기대는 폐기했다.
 * 세부 시나리오는 DashboardPage.selectedQuarter.test.tsx.
 */
describe('선택한 Quarter 강조 (AC-15, AC6)', () => {
  it('marks the sq quarter row and says which quarter is selected in the heading', async () => {
    await openForecastTab('/dashboard?tab=forecast&year=2026&sq=3')

    expect(screen.getByRole('heading', { level: 2, name: 'Selected Quarter : Q3' })).toBeVisible()
    expect(screen.getByRole('row', { name: /Q3/ })).toHaveAttribute('aria-current', 'true')
    for (const other of [/Q1/, /Q2/, /Q4/]) expect(screen.getByRole('row', { name: other })).not.toHaveAttribute('aria-current', 'true')
  })

  it('marks exactly one row by default (the quarter of today)', async () => {
    await openForecastTab()

    const marked = within(screen.getByRole('table'))
      .getAllByRole('row')
      .filter((row) => row.getAttribute('aria-current') === 'true')
    expect(marked).toHaveLength(1)
    expect(marked[0]).toHaveTextContent('Q4')
  })

  it('ignores the Quarter filter of the Status tab for the highlight', async () => {
    await openForecastTab('/dashboard?tab=forecast&year=2026&quarter=3')

    expect(screen.getByRole('row', { name: /Q4/ })).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('row', { name: /Q3/ })).not.toHaveAttribute('aria-current', 'true')
  })
})

describe('Closing Attention 타일 (AC-15)', () => {
  it('shows this month, this quarter and the stale tiles', async () => {
    await openForecastTab()

    expect(screen.getByRole('link', { name: /이번 달.*10월.*Expected Close\s*4/ })).toHaveAttribute('href', '/deals?year=2026&month=10&outcome=open')
    expect(screen.getByRole('link', { name: /이번 분기.*Expected Close\s*7/ })).toHaveAttribute('href', '/deals?year=2026&quarter=4&outcome=open')
    expect(screen.getByRole('link', { name: /14일 이상 미업데이트\D*5/ })).toHaveAttribute('href', '/deals?stale=1')
  })

  it('does not show the overdue tile (it belongs to the Status tab)', async () => {
    await openForecastTab()

    expect(screen.queryByRole('link', { name: /기한초과/ })).not.toBeInTheDocument()
  })

  it('applies only the owner and vendor and uses the server month', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, closingThisMonth: { year: 2027, month: 1, count: 2 } } })
    await renderAt(`/dashboard?tab=forecast&year=2026&quarter=2&owner=${USER_ID.kim}`)

    const tile = await screen.findByRole('link', { name: /이번 달.*1월/ })

    expect(tile).toHaveAttribute('href', `/deals?year=2027&month=1&owner=${USER_ID.kim}&outcome=open`)
  })

  it('shows the alert setting as the stale days', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, staleDays: 21, stale: 1 } })
    await renderAt('/dashboard?tab=forecast&year=2026')

    expect(await screen.findByRole('link', { name: /21일 이상 미업데이트\D*1/ })).toBeVisible()
  })
})
