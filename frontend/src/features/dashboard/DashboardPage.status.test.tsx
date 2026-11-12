import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatWon } from '../../shared/model/money'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { link, mockSummary, NOT_LOST_PARAM, NOW, OPEN_PARAM } from './testHelpers'

/** Status 탭: Forecast 타일, Status 표, 주의 필요 Deal 타일. 요약은 고정 값으로 바꿔 끼운다. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const won = (n: number) => formatWon(n)

describe('Forecast 타일', () => {
  // 테스트 코드: DSH-041
  it.each([
    ['Pipeline', 18, 320_000_000, '/deals?year=2026&forecast=pipeline'],
    ['Best', 6, 150_000_000, '/deals?year=2026&forecast=best'],
    ['Most Likely', 4, 90_000_000, '/deals?year=2026&forecast=most_likely'],
    ['Commit', 3, 70_000_000, '/deals?year=2026&forecast=commit'],
  ])('%s 타일은 건수와 원 금액을 보이고 해당 Deal 목록으로 연결된다', async (name, count, amount, href) => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: 2026년 Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const tile = await screen.findByRole('link', { name: new RegExp(name) })

    // then: 타일에 건수·금액이 있고 링크가 그 Forecast key 목록이다
    expect(tile).toHaveTextContent(`${count}건`)
    expect(tile).toHaveTextContent(won(amount))
    expect(tile).toHaveAttribute('href', href)
  })

  // 테스트 코드: DSH-041
  it('Open 합계 타일을 보인다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: 2026년 Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    // then: Open 합계 31건·원 금액이고 링크가 Open 집합 목록이다
    expect(tile).toHaveTextContent('31건')
    expect(tile).toHaveTextContent(won(630_000_000))
    expect(tile).toHaveAttribute('href', `/deals?year=2026&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-041
  it('Won 타일 제목에 기간을 붙인다: 연도, 또는 연도와 고른 분기', async () => {
    // given: 분기 없는 응답
    mockSummary(dashboardSummaryFixture())

    // when: 분기 없이 연다
    const first = await renderAt('/dashboard?status.year=2026')
    const tile = await screen.findByRole('link', { name: /Won/ })

    // then: "Won (2026)"이고 건수·금액이 있다
    expect(tile).toHaveTextContent('Won (2026)')
    expect(tile).toHaveTextContent('2건')
    expect(tile).toHaveTextContent(won(40_000_000))
    first.unmount()

    // given: Q3 응답
    mockSummary(dashboardSummaryFixture({ period: { year: 2026, quarter: 3, quarters: [3], from: '2026-07-01', to: '2026-09-30' } }))
    // when: Q3로 연다
    const second = await renderAt('/dashboard?status.year=2026&status.quarter=3')
    // then: "Won (2026 Q3)"이다
    expect(await screen.findByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026 Q3)')
    second.unmount()

    // given: Q1·Q3 응답
    mockSummary(dashboardSummaryFixture({ period: { year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' } }))
    // when: Q1·Q3로 연다
    await renderAt('/dashboard?status.year=2026&status.quarter=1%2C3')
    // then: "Won (2026 Q1, Q3)"이다
    expect(await screen.findByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026 Q1, Q3)')
  })

  // 테스트 코드: DSH-041
  it('서버가 분기 없음으로 답하면(넷 다 선택) Won 제목에 연도만 쓴다', async () => {
    // given: 분기 없는 응답
    mockSummary(dashboardSummaryFixture())

    // when: 넷 다 누른 주소로 연다
    await renderAt('/dashboard?status.year=2026&status.quarter=1%2C2%2C3%2C4')

    // then: "Won (2026)"이다
    expect(await screen.findByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026)')
  })

  // 테스트 코드: DSH-041
  it('Lost 타일은 없다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('link', { name: /Open 합계/ })

    // then: Lost 링크가 없다
    expect(screen.queryByRole('link', { name: /Lost/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-041
  it('타일을 Forecast 코드 순서로, 마지막에 Won을 보인다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('link', { name: /Open 합계/ })

    // then: 타일 위치가 코드 순서이고 key가 pipeline…won 순서다
    const tiles = [/Pipeline/, /Best/, /Most Likely/, /Commit/, /^Won/]
    const keys = tiles.map((name) => new URLSearchParams((screen.getByRole('link', { name }).getAttribute('href') ?? '').split('?')[1] ?? '').get('forecast'))
    const positions = tiles.map((name) => screen.getAllByRole('link').indexOf(screen.getByRole('link', { name })))
    expect(positions).toEqual([...positions].sort((a, b) => a - b))

    expect(keys).toEqual(['pipeline', 'best', 'most_likely', 'commit', 'won'])
  })

  // 테스트 코드: DSH-041
  it('admin이 추가한 Forecast 코드는 코드 이름의 타일이 된다', async () => {
    // given: Verbal 코드가 열에 추가된 응답
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

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const tile = await screen.findByRole('link', { name: /Verbal/ })

    // then: Verbal 타일에 건수·금액·링크가 있다
    expect(tile).toHaveTextContent('5건')
    expect(tile).toHaveTextContent(won(55_000_000))
    expect(tile).toHaveAttribute('href', '/deals?year=2026&forecast=verbal')
  })

  // 테스트 코드: DSH-041
  it('이름을 바꾼 코드는 새 이름으로 보이고 링크에는 key를 쓴다', async () => {
    // given: Commit 코드 이름이 "확정"으로 바뀐 응답
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      forecast: { ...base.forecast, columns: base.forecast.columns.map((c) => (c.key === 'commit' ? { ...c, name: '확정' } : c)) },
    })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const tile = await screen.findByRole('link', { name: /확정/ })

    // then: 타일 링크가 commit key를 쓴다
    expect(tile).toHaveAttribute('href', '/deals?year=2026&forecast=commit')
  })

  // 테스트 코드: DSH-048
  it('분기·담당자·Vendor가 모든 타일 링크에 실린다', async () => {
    // given: 고정 값의 요약 응답과 Okta Vendor id
    mockSummary(dashboardSummaryFixture())
    const vendor = seedVendorId('Okta')

    // when: 2026년 Q3·김영업·Okta 조건으로 연다
    await renderAt(`/dashboard?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`)
    const tile = await screen.findByRole('link', { name: /Pipeline/ })

    // then: Pipeline 타일과 Open 합계 링크에 조건이 실린다
    expect(tile).toHaveAttribute('href', `/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}&forecast=pipeline`)
    expect(screen.getByRole('link', { name: /Open 합계/ })).toHaveAttribute(
      'href',
      `/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${OPEN_PARAM}`,
    )
  })

  // 테스트 코드: DSH-048
  it('admin이 추가한 Open 코드는 Won 타일이 아니라 Open 합계 링크에 든다', async () => {
    // given: Verbal Open 코드가 열에 추가된 응답
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      forecast: {
        ...base.forecast,
        columns: [...base.forecast.columns.slice(0, 3), { key: 'verbal', name: 'Verbal', outcome: 'open', order: 35 }, ...base.forecast.columns.slice(3)],
        cells: { ...base.forecast.cells, verbal: { count: 5, amount: 55_000_000 } },
      },
    })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const href = (await screen.findByRole('link', { name: /Open 합계/ })).getAttribute('href') ?? ''

    // then: Open 합계 링크의 forecast 집합에 verbal이 있다
    expect(new URLSearchParams(href.split('?')[1]).get('forecast')?.split(',')).toEqual(['best', 'commit', 'most_likely', 'pipeline', 'verbal'])
  })

  // 테스트 코드: DSH-049
  it('Open Forecast 코드가 없으면 Open 합계는 링크가 아니라 글자로 보인다', async () => {
    // given: Won 열만 있는 응답
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      forecast: { columns: [{ key: 'won', name: 'Won', outcome: 'won', order: 5 }], cells: { won: { count: 2, amount: 40_000_000 } }, openTotal: { count: 0, amount: 0 } },
    })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('link', { name: /Won/ })

    // then: Open 합계 링크는 없고 글자만 있다
    expect(screen.queryByRole('link', { name: /Open 합계/ })).not.toBeInTheDocument()
    expect(screen.getAllByText('Open 합계').length).toBeGreaterThan(0)
  })
})

describe('Status 표', () => {
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

  // 테스트 코드: DSH-042
  it('표의 열은 Status·건수·금액(단위:원)이다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const table = await screen.findByRole('table')
    const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent ?? '')

    // then: 열 머리글이 문서와 같다
    expect(headers[0]).toBe('Status')
    expect(headers[1]).toBe('건수')
    expect(headers[2]).toContain('금액')
    expect(headers[2]).toBe('금액(단위:원)')
  })

  // 테스트 코드: DSH-042
  it.each(ITEMS)('%s 행은 %i건과 원 금액을 보이고 해당 Status 목록으로 연결된다', async (name, count, amount, key) => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')
    const row = screen.getByRole('row', { name: new RegExp(name) })
    const cells = cellsOf(row)

    // then: 건수·원 금액이 있고 링크가 status와 Lost 제외 집합을 담는다
    expect(cells.at(-2)).toMatch(new RegExp(`^${count}건?$`))
    expect(cells.at(-1)).toBe(won(amount))
    expect(within(row).getByRole('link')).toHaveAttribute('href', `/deals?year=2026&status=${key}&forecast=${NOT_LOST_PARAM}`)
  })

  // 테스트 코드: DSH-042
  it('Status를 코드 순서로 나열하고 합계 행이 맨 아래다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)

    // then: 7개 Status 행 뒤에 합계 행이 있다
    expect(rows).toHaveLength(8)
    expect(rows.map((r) => r.textContent ?? '').map((text, i) => (i < 7 ? text.includes(ITEMS[i]?.[0] ?? '?') : text.includes('합계')))).toEqual(Array(8).fill(true))
  })

  // 테스트 코드: DSH-042
  it('합계 행은 응답의 합계이자 행 합계와 같다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')
    const totalRow = screen.getByRole('row', { name: /합계/ })
    const cells = cellsOf(totalRow)

    // then: 33건·670,000,000원이고 행 합과 같으며 링크가 Lost 제외 집합이다
    expect(cells.at(-2)).toMatch(/^33건?$/)
    expect(cells.at(-1)).toBe(won(670_000_000))
    expect(ITEMS.reduce((sum, item) => sum + item[1], 0)).toBe(33)
    expect(ITEMS.reduce((sum, item) => sum + item[2], 0)).toBe(670_000_000)
    expect(within(totalRow).getByRole('link')).toHaveAttribute('href', `/deals?year=2026&forecast=${NOT_LOST_PARAM}`)
  })

  // 테스트 코드: DSH-042
  it('Deal이 없는 Status도 0으로 표에 남는다', async () => {
    // given: 기술평가가 0건인 응답
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'technical_evaluation' ? { ...i, count: 0, amount: 0 } : i)) },
    })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')
    const cells = cellsOf(screen.getByRole('row', { name: /기술평가/ }))

    // then: 기술평가 행이 0건·0이다
    expect(cells.at(-2)).toMatch(/^0건?$/)
    expect(cells.at(-1)).toBe('0')
  })

  // 테스트 코드: DSH-042
  it('이름을 바꾼 Status 코드를 따른다', async () => {
    // given: introduction 코드 이름이 "소개"로 바뀐 응답
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'introduction' ? { ...i, name: '소개' } : i)) },
    })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    // then: "소개" 행이 보이고 링크는 introduction key를 쓴다
    expect(within(screen.getByRole('row', { name: /소개/ })).getByRole('link')).toHaveAttribute('href', `/deals?year=2026&status=introduction&forecast=${NOT_LOST_PARAM}`)
  })
})

describe('주의 필요 Deal 타일', () => {
  // 테스트 코드: DSH-044
  it('기한초과·미업데이트·이번 분기 타일이 건수와 링크를 보인다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: 2026년 Q2 조건으로 Status 탭을 연다
    await renderAt('/dashboard?year=2026&quarter=2')
    const overdue = await screen.findByRole('link', { name: /기한초과\D*4/ })
    const stale = screen.getByRole('link', { name: /14일 이상 미업데이트\D*5/ })
    const closing = screen.getByRole('link', { name: /이번 분기.*2026 Q4.*Expected Close\s*7/ })

    // then: 건수와 링크가 응답 그대로다(이번 분기 링크는 고른 Q2가 아니라 응답의 Q4)
    expect(overdue).toHaveAttribute('href', '/deals?overdue=1')
    expect(stale).toHaveAttribute('href', '/deals?stale=1')
    expect(closing).toHaveAttribute('href', `/deals?year=2026&quarter=4&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-044
  it('미업데이트 타일에 고정 15가 아니라 경고 기준일을 보인다', async () => {
    // given: 경고 기준 30일·미업데이트 9건인 응답
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, staleDays: 30, stale: 9 } })

    // when: Status 탭을 연다
    await renderAt('/dashboard')

    // then: "30일 이상 미업데이트 9건"이 보이고 15일 타일은 없다
    expect(await screen.findByRole('link', { name: /30일 이상 미업데이트\D*9/ })).toBeVisible()
    expect(screen.queryByRole('link', { name: /15일/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-048
  it('주의 타일 링크에는 담당자·Vendor만 싣고 기간은 싣지 않는다', async () => {
    // given: 고정 값의 요약 응답과 Okta Vendor id
    mockSummary(dashboardSummaryFixture())
    const vendor = seedVendorId('Okta')

    // when: 2026년 Q2·김영업·Okta 조건으로 연다
    await renderAt(`/dashboard?year=2026&quarter=2&owner=${USER_ID.kim}&vendor=${vendor}`)

    // then: 기한초과·미업데이트 링크는 담당자·Vendor만, 이번 분기는 응답의 연·분기와 Open 집합을 담는다
    expect(await screen.findByRole('link', { name: /기한초과/ })).toHaveAttribute('href', `/deals?owner=${USER_ID.kim}&vendor=${vendor}&overdue=1`)
    expect(screen.getByRole('link', { name: /미업데이트/ })).toHaveAttribute('href', `/deals?owner=${USER_ID.kim}&vendor=${vendor}&stale=1`)
    expect(screen.getByRole('link', { name: /이번 분기/ })).toHaveAttribute(
      'href',
      `/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${OPEN_PARAM}`,
    )
  })

  // 테스트 코드: DSH-044
  it('이번 분기는 브라우저 날짜가 아니라 서버 응답에서 가져온다', async () => {
    // given: 이번 분기가 2027 Q1·3건인 응답
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, closingThisQuarter: { year: 2027, quarter: 1, count: 3 } } })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    const closing = await screen.findByRole('link', { name: /이번 분기.*2027 Q1/ })

    // then: 응답의 연·분기·건수와 링크다
    expect(closing).toHaveTextContent('3')
    expect(closing).toHaveAttribute('href', `/deals?year=2027&quarter=1&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-044
  it('0건도 타일로 보인다', async () => {
    // given: 기한초과·미업데이트가 0건인 응답
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, overdue: 0, stale: 0 } })

    // when: Status 탭을 연다
    await renderAt('/dashboard')

    // then: 0건 타일이 링크로 보인다
    expect(await screen.findByRole('link', { name: /기한초과\D*0/ })).toBeVisible()
    expect(link(/미업데이트\D*0/)).toBeVisible()
  })

  // 테스트 코드: DSH-044
  it('Status 탭에는 Forecast 탭의 이번 달 타일이 없다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard')
    await screen.findByRole('link', { name: /기한초과/ })

    // then: 이번 달 링크가 없다
    expect(screen.queryByRole('link', { name: /이번 달/ })).not.toBeInTheDocument()
  })
})
