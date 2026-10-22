import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { listMemoryKey } from '../../shared/model/dealListMemory'
import { formatThousandWon } from '../../shared/model/money'
import { listQueryFromParams } from '../deals/list/listQuery'
import { lastChart } from '../../test/chartMock'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { lastQuery, mockSummary, NOW } from './testHelpers'

/**
 * Forecast 탭의 하단 Selected Quarter (AC2~AC7, 2026-10-23 개편).
 *
 * UI 계약:
 * - 버튼 그룹: role=group, 이름 "Selected Quarter". 버튼 이름 "Q1"~"Q4", 선택 버튼만 aria-pressed="true"(나머지 "false").
 * - 섹션 제목(h2): "Selected Quarter : Q3". 하단 타일 영역: role=region(section aria-label) "Selected Quarter 구분별 금액(단위:천원)".
 *   상단(연간) 타일 영역은 기존 이름 "Forecast 구분별 금액(단위:천원)"을 유지한다.
 * - 하단 타일은 상단 ForecastTiles와 같은 형식: 열린 구분 → "Open 합계" → Won(제목 "Won (2026 Q3)") → "합계"(Open + Won, Lost 제외).
 *   링크 접근 이름은 "<제목> <N>건 <금액>" 형태(제목 + 건수 + 금액이 이어진 텍스트)다.
 * - URL 키 `sq`(1~4). 기본값: 선택 연도가 올해(useToday)면 오늘이 속한 분기, 아니면 Q1. 잘못된 값도 기본값.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const won = (n: number) => formatThousandWon(n)
const BOTTOM = 'Selected Quarter 구분별 금액(단위:천원)'
const TOP = 'Forecast 구분별 금액(단위:천원)'
const bottom = () => within(screen.getByRole('region', { name: BOTTOM }))
const top = () => within(screen.getByRole('region', { name: TOP }))
const quarterButton = (q: number) => within(screen.getByRole('group', { name: 'Selected Quarter' })).getByRole('button', { name: `Q${q}` })

async function open(url: string, now?: string) {
  if (now) resetMock({ now })
  // 기본 분기는 서버 업무 날짜(응답 today) 기준이라, 시계를 바꾸면 응답 today도 같은 날짜로 맞춘다.
  const spy = mockSummary(dashboardSummaryFixture(now ? { asOf: now, today: now.slice(0, 10) } : {}))
  const view = await renderAt(url)
  await screen.findByRole('group', { name: 'Selected Quarter' })
  return { ...view, spy }
}

function expectPressed(q: number) {
  for (const n of [1, 2, 3, 4]) expect(quarterButton(n)).toHaveAttribute('aria-pressed', n === q ? 'true' : 'false')
}

describe('Selected Quarter 버튼 (AC3)', () => {
  it('has the four quarter buttons in order under the group', async () => {
    await open('/dashboard?tab=forecast&year=2026')

    const names = within(screen.getByRole('group', { name: 'Selected Quarter' }))
      .getAllByRole('button')
      .map((b) => b.textContent)
    expect(names).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  it('shows the heading with the selected quarter', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=3')

    expect(screen.getByRole('heading', { level: 2, name: 'Selected Quarter : Q3' })).toBeVisible()
  })

  it('presses only the quarter in sq', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=2')

    expectPressed(2)
  })

  it('puts the clicked quarter in the URL as sq and keeps the other conditions', async () => {
    const { user, location } = await open(`/dashboard?tab=forecast&year=2026&owner=${USER_ID.kim}&quarter=3`)

    await user.click(quarterButton(2))

    await waitFor(() => expect(location()).toContain('sq=2'))
    for (const kept of ['tab=forecast', 'year=2026', `owner=${USER_ID.kim}`, 'quarter=3']) expect(location()).toContain(kept)
    expectPressed(2)
  })

  it('changes the lower tiles to the clicked quarter values', async () => {
    const { user } = await open('/dashboard?tab=forecast&year=2026&sq=4')
    expect(bottom().getByRole('link', { name: /Pipeline/ })).toHaveTextContent('7건')

    await user.click(quarterButton(3))

    const tile = bottom().getByRole('link', { name: /Pipeline/ })
    await waitFor(() => expect(tile).toHaveTextContent('5건'))
    expect(tile).toHaveTextContent(won(100_000_000))
    expect(screen.getByRole('heading', { level: 2, name: 'Selected Quarter : Q3' })).toBeVisible()
  })

  it('does not fetch again when the quarter is clicked (the same response is used)', async () => {
    const { user, spy } = await open('/dashboard?tab=forecast&year=2026')
    const calls = spy.mock.calls.length

    await user.click(quarterButton(1))
    await waitFor(() => expectPressed(1))

    expect(spy.mock.calls.length).toBe(calls)
  })

  it('does not show the Selected Quarter buttons on the Status tab', async () => {
    await renderAt('/dashboard?tab=status&year=2026&sq=3')
    await screen.findByRole('table')

    expect(screen.queryByRole('group', { name: 'Selected Quarter' })).not.toBeInTheDocument()
  })
})

describe('sq 기본값 (AC4)', () => {
  it('selects the quarter of today when the year is this year', async () => {
    await open('/dashboard?tab=forecast&year=2026')

    expectPressed(4)
  })

  it('follows the business date for this year (May is Q2)', async () => {
    await open('/dashboard?tab=forecast&year=2026', '2026-05-10T09:00:00+09:00')

    expectPressed(2)
  })

  it('uses this year when the URL has no year', async () => {
    await open('/dashboard?tab=forecast', '2026-08-10T09:00:00+09:00')

    expectPressed(3)
  })

  it.each([2025, 2027])('selects Q1 for another year %i', async (year) => {
    await open(`/dashboard?tab=forecast&year=${year}`)

    expectPressed(1)
  })

  it.each(['5', '0', 'x', '', '2.5', '02'])('falls back to the default for the broken sq %j', async (raw) => {
    await open(`/dashboard?tab=forecast&year=2026&sq=${encodeURIComponent(raw)}`)

    expectPressed(4)
  })

  it('falls back to Q1 for a broken sq of another year', async () => {
    await open('/dashboard?tab=forecast&year=2025&sq=9')

    expectPressed(1)
  })

  it('does not write sq to the URL by default', async () => {
    const { location } = await open('/dashboard?tab=forecast&year=2026')

    expect(location()).toBe('/dashboard?tab=forecast&year=2026')
  })

  it('keeps an explicit sq even when the year is changed', async () => {
    const { user, location } = await open('/dashboard?tab=forecast&year=2026&sq=2')

    await user.selectOptions(screen.getByLabelText('연도'), '2027')

    await waitFor(() => expect(location()).toContain('year=2027'))
    expect(location()).toContain('sq=2')
    expectPressed(2)
  })
})

describe('연간 상단 타일 (AC2)', () => {
  it('requests the summary without quarter even when the URL has quarter', async () => {
    const { spy } = await open('/dashboard?tab=forecast&year=2026&quarter=3')

    expect(lastQuery(spy)).toEqual({ year: 2026 })
  })

  it('keeps the owner and vendor in the request and drops only quarter', async () => {
    const vendor = seedVendorId('Okta')
    const { spy } = await open(`/dashboard?tab=forecast&year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`)

    expect(lastQuery(spy)).toEqual({ year: 2026, ownerId: USER_ID.kim, vendorId: vendor })
  })

  it('still sends quarter on the Status tab', async () => {
    const spy = mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?tab=status&year=2026&quarter=3')
    await screen.findByRole('table')

    expect(lastQuery(spy)).toEqual({ year: 2026, quarter: 3 })
  })

  it('links the upper tiles to the year without quarter', async () => {
    await open('/dashboard?tab=forecast&year=2026&quarter=3&sq=2')

    expect(top().getByRole('link', { name: /Pipeline/ })).toHaveAttribute('href', '/deals?year=2026&forecast=pipeline')
    expect(top().getByRole('link', { name: /Open 합계/ })).toHaveAttribute('href', '/deals?year=2026&outcome=open')
  })

  it('shows the yearly values on the upper tiles whatever sq is', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=1')

    expect(top().getByRole('link', { name: /Pipeline/ })).toHaveTextContent('18건')
    expect(top().getByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026)')
  })
})

describe('하단 타일 값 (AC3)', () => {
  it('shows the open codes, the open total, Won and the total of the selected quarter in that order', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=3')

    const titles = bottom()
      .getAllByRole('link')
      .map((a) => a.querySelector('.db-tile-title')?.textContent)
    expect(titles).toEqual(['Pipeline', 'Best', 'Most Likely', 'Commit', 'Open 합계', 'Won (2026 Q3)', '합계'])
    expect(bottom().queryByRole('link', { name: /Lost/ })).not.toBeInTheDocument()
  })

  it('shows count and amount of Q3 from the quarter data', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=3')

    const expected: [RegExp, string, number][] = [
      [/Pipeline/, '5건', 100_000_000],
      [/Best/, '2건', 50_000_000],
      [/Most Likely/, '1건', 30_000_000],
      [/Commit/, '1건', 20_000_000],
      [/Open 합계/, '9건', 200_000_000],
      [/Won/, '1건', 30_000_000],
      [/^합계/, '10건', 230_000_000],
    ]
    for (const [name, count, amount] of expected) {
      const tile = bottom().getByRole('link', { name })
      expect(tile).toHaveTextContent(count)
      expect(tile).toHaveTextContent(won(amount))
    }
  })

  it('shows 0건 for a code without deals in the quarter', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=2')

    expect(bottom().getByRole('link', { name: /Commit/ })).toHaveTextContent('0건')
  })
})

describe('하단 타일 Drill-down (AC5)', () => {
  const vendor = seedVendorId('Okta')
  const url = `/dashboard?tab=forecast&year=2026&quarter=1&sq=3&owner=${USER_ID.kim}&vendor=${vendor}`
  const base = `/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`

  it('links a code tile to the selected quarter, owner, vendor and the code', async () => {
    await open(url)

    expect(bottom().getByRole('link', { name: /Pipeline/ })).toHaveAttribute('href', `${base}&forecast=pipeline`)
    expect(bottom().getByRole('link', { name: /Won/ })).toHaveAttribute('href', `${base}&forecast=won`)
  })

  it('links the open total with outcome=open and the total with outcome=not_lost', async () => {
    await open(url)

    expect(bottom().getByRole('link', { name: /Open 합계/ })).toHaveAttribute('href', `${base}&outcome=open`)
    expect(bottom().getByRole('link', { name: /^합계/ })).toHaveAttribute('href', `${base}&outcome=not_lost`)
  })

  it('uses the default quarter in the links when sq is not in the URL', async () => {
    await open('/dashboard?tab=forecast&year=2026')

    expect(bottom().getByRole('link', { name: /Best/ })).toHaveAttribute('href', '/deals?year=2026&quarter=4&forecast=best')
  })

  it('never puts sq in a link of the Forecast tab', async () => {
    await open(`${url}`)

    const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href') ?? '')
    expect(hrefs.filter((h) => h.startsWith('/deals')).length).toBeGreaterThan(0)
    for (const href of hrefs) expect(href).not.toMatch(/[?&]sq=/)
  })

  it('is read back by the Deals list as the same condition', async () => {
    await open(url)
    const query = (name: RegExp) => listQueryFromParams(new URLSearchParams((bottom().getByRole('link', { name }).getAttribute('href') ?? '').split('?')[1]))
    const common = { offset: 0, limit: 20, year: 2026, quarter: 3, ownerId: USER_ID.kim, vendorId: vendor }

    expect(query(/Commit/)).toEqual({ ...common, forecastKey: 'commit' })
    expect(query(/Open 합계/)).toEqual({ ...common, forecastOutcome: 'open' })
    expect(query(/^합계/)).toEqual({ ...common, forecastOutcome: 'not_lost' })
  })

  it('opens the Deals list from a lower tile and stores only the list condition in the memory', async () => {
    const { user, location } = await open('/dashboard?tab=forecast&year=2026&sq=2')

    await user.click(bottom().getByRole('link', { name: /Pipeline/ }))

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=2&forecast=pipeline'))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=2026&quarter=2&forecast=pipeline')
  })

  it('comes back from the list with the same sq', async () => {
    const start = '/dashboard?tab=forecast&year=2026&sq=2'
    const view = await open(start)
    await view.user.click(bottom().getByRole('link', { name: /Best/ }))
    await screen.findByLabelText('Forecast 구분')

    view.goTo(-1)

    await waitFor(() => expect(view.location()).toBe(start))
    expect(await screen.findByRole('group', { name: 'Selected Quarter' })).toBeVisible()
    expectPressed(2)
  })
})

describe('선택 분기 강조 (AC6)', () => {
  it('marks the sq row of the table with aria-current and no other row', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=3')

    expect(screen.getByRole('row', { name: /Q3/ })).toHaveAttribute('aria-current', 'true')
    for (const other of [/Q1/, /Q2/, /Q4/]) expect(screen.getByRole('row', { name: other })).not.toHaveAttribute('aria-current', 'true')
  })

  it('marks the default quarter row when sq is not given', async () => {
    await open('/dashboard?tab=forecast&year=2026')

    expect(screen.getByRole('row', { name: /Q4/ })).toHaveAttribute('aria-current', 'true')
  })

  it('does not follow the quarter filter of the Status tab', async () => {
    await open('/dashboard?tab=forecast&year=2026&quarter=1&sq=3')

    expect(screen.getByRole('row', { name: /Q3/ })).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('row', { name: /Q1/ })).not.toHaveAttribute('aria-current', 'true')
  })

  it('does not say Selected Quarter as a note under the chart any more (the heading below says it)', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=3')

    expect(screen.queryByText('Selected Quarter: Q3')).not.toBeInTheDocument()
  })

  it('keeps the bars of the sq quarter solid and dims the others', async () => {
    await open('/dashboard?tab=forecast&year=2026&sq=3')

    for (const dataset of lastChart().data.datasets) {
      const colours = dataset.backgroundColor as string[]
      expect(Array.isArray(colours)).toBe(true)
      const solid = colours[2] as string
      expect(solid).toMatch(/^#[0-9a-f]{6}$/i)
      for (const index of [0, 1, 3]) expect(colours[index]).toBe(`${solid}55`)
    }
  })

  it('moves the dimming when another quarter is clicked', async () => {
    const { user } = await open('/dashboard?tab=forecast&year=2026&sq=3')

    await user.click(quarterButton(1))

    await waitFor(() => {
      const colours = lastChart().data.datasets[0]?.backgroundColor as string[]
      expect(colours[0]).toMatch(/^#[0-9a-f]{6}$/i)
      expect(colours[2]).toMatch(/55$/)
    })
  })

  it('does not dim by the quarter filter of the URL', async () => {
    await open('/dashboard?tab=forecast&year=2026&quarter=1&sq=3')

    const colours = lastChart().data.datasets[0]?.backgroundColor as string[]
    expect(colours[0]).toMatch(/55$/)
    expect(colours[2]).toMatch(/^#[0-9a-f]{6}$/i)
  })
})

describe('탭 전환과 URL (AC7)', () => {
  it('keeps sq and quarter in the URL when going to the Status tab and back', async () => {
    const { user, location } = await open('/dashboard?tab=forecast&year=2026&quarter=3&sq=2')

    await user.click(screen.getByRole('tab', { name: 'Status' }))
    await waitFor(() => expect(location()).toContain('tab=status'))
    expect(location()).toContain('quarter=3')
    expect(location()).toContain('sq=2')
    expect(screen.getByLabelText('Quarter')).toHaveDisplayValue('Q3')

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('group', { name: 'Selected Quarter' })
    expect(location()).toContain('quarter=3')
    expect(location()).toContain('sq=2')
    expectPressed(2)
  })

  it('does not add sq or quarter to the URL on a tab switch when they were not set', async () => {
    const { user, location } = await open('/dashboard?tab=forecast&year=2026')

    await user.click(screen.getByRole('tab', { name: 'Status' }))

    await waitFor(() => expect(location()).toBe('/dashboard?tab=status&year=2026'))
  })

  it('does not send a new request for the quarter filter when only sq changes', async () => {
    const spy = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard?tab=forecast&year=2026')
    await screen.findByRole('group', { name: 'Selected Quarter' })
    const calls = spy.mock.calls.length

    await user.click(quarterButton(2))
    await waitFor(() => expectPressed(2))

    expect(spy.mock.calls.length).toBe(calls)
  })
})
