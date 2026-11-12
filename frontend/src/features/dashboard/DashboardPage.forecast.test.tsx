import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatWon } from '../../shared/model/money'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture, emptyDashboardSummary } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { mockSummary, NOT_LOST_PARAM, NOW, OPEN_PARAM } from './testHelpers'

/** Forecast 탭: Forecast 타일, 분기 표(고른 분기 행), Closing Attention 타일. Selected Quarter는 폐지됐다. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const won = (n: number) => formatWon(n)
const hrefsOf = (row: HTMLElement) => within(row).getAllByRole('link').map((a) => a.getAttribute('href'))

async function openForecastTab(url = '/dashboard?tab=forecast&forecast.year=2026', summary = dashboardSummaryFixture()) {
  mockSummary(summary)
  const view = await renderAt(url)
  await screen.findByRole('table')
  return view
}

describe('Forecast 탭의 Forecast 타일', () => {
  // 테스트 코드: DSH-041
  it('Status 탭과 같은 타일을 보인다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()
    const top = within(screen.getByRole('region', { name: 'Forecast 구분별 금액(단위:원)' }))
    const tile = top.getByRole('link', { name: /Pipeline/ })

    // then: Pipeline·Open 합계·Won 타일이 있고 Lost 타일은 없다
    expect(tile).toHaveTextContent('18건')
    expect(tile).toHaveTextContent(won(320_000_000))
    expect(top.getByRole('link', { name: /Open 합계/ })).toHaveTextContent('31건')
    expect(top.getByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026)')
    expect(screen.queryByRole('link', { name: /Lost/ })).not.toBeInTheDocument()
  })
})

describe('분기 표', () => {
  // 테스트 코드: DSH-045
  it('머리글 아래에 Q1~Q4 네 행이 있다', async () => {
    // when: 분기 없이 Forecast 탭을 연다
    await openForecastTab()
    const rows = within(screen.getByRole('table')).getAllByRole('row')

    // then: 머리글 + Q1~Q4 다섯 행이다
    expect(rows).toHaveLength(5)
    ;['Q1', 'Q2', 'Q3', 'Q4'].forEach((quarter, i) => expect(rows[i + 1]).toHaveTextContent(quarter))
  })

  // 테스트 코드: DSH-045
  it('분기마다 Forecast 열 금액·Open 합계·합계(Open + Won)를 보인다', async () => {
    // when: 분기 없이 Forecast 탭을 연다
    await openForecastTab()
    const q1 = screen.getByRole('row', { name: /Q1/ })

    // then: Q1·Q3 행에 각 열 금액과 합계가 있다
    for (const amount of [40_000_000, 20_000_000, 10_000_000, 100_000_000, 110_000_000]) {
      expect(q1).toHaveTextContent(won(amount))
    }
    const q3 = screen.getByRole('row', { name: /Q3/ })
    for (const amount of [100_000_000, 50_000_000, 30_000_000, 20_000_000, 200_000_000, 230_000_000]) {
      expect(q3).toHaveTextContent(won(amount))
    }
  })

  // 테스트 코드: DSH-045
  it('머리글에 Lost 없이 Forecast 열을 코드 순서로 보인다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()
    const header = within(screen.getByRole('table')).getAllByRole('columnheader').map((h) => h.textContent ?? '')

    // then: Lost가 없고 열 이름이 코드 순서다
    expect(header.join('|')).not.toContain('Lost')
    const positions = ['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won'].map((name) => header.findIndex((text) => text.includes(name)))
    expect(positions.every((p) => p >= 0)).toBe(true)
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
  })

  // 테스트 코드: DSH-048
  it('분기의 칸과 합계가 그 분기 Deal 목록으로 연결된다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()
    const hrefs = hrefsOf(screen.getByRole('row', { name: /Q2/ }))

    // then: Q2 행 링크가 그 분기 하나와 Forecast key·Open 집합·Lost 제외 집합을 담는다
    expect(hrefs).toContain('/deals?year=2026&quarter=2&forecast=pipeline')
    expect(hrefs).toContain('/deals?year=2026&quarter=2&forecast=best')
    expect(hrefs).toContain(`/deals?year=2026&quarter=2&forecast=${OPEN_PARAM}`)
    expect(hrefs).toContain(`/deals?year=2026&quarter=2&forecast=${NOT_LOST_PARAM}`)
    expect(hrefs).not.toContain('/deals?year=2026&quarter=2')
  })

  // 테스트 코드: DSH-052
  it('분기 칸 링크에는 담당자·Vendor만 싣고 고른 분기는 따르지 않는다', async () => {
    // given: Q3·Q4와 담당자·Okta를 고른 Forecast 탭
    const vendor = seedVendorId('Okta')

    // when: 열고 Q4 행의 링크를 읽는다
    await openForecastTab(`/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3%2C4&forecast.owner=${USER_ID.kim}&forecast.vendor=${vendor}`)
    const hrefs = hrefsOf(screen.getByRole('row', { name: /Q4/ }))

    // then: 링크가 분기 4 하나와 담당자·Vendor를 담는다
    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=pipeline`)
    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${OPEN_PARAM}`)
    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${NOT_LOST_PARAM}`)
  })

  // 테스트 코드: DSH-045
  it('분기를 고르지 않으면 네 분기를 모두 보인다', async () => {
    // when: 분기 없이 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026')

    // then: 머리글 + 네 행이다
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(5)
  })

  // 테스트 코드: DSH-045
  it('넷 다 고르면 네 분기를 모두 보이고 버튼은 눌린 채 남는다', async () => {
    // when: 넷 다 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C2%2C3%2C4')

    // then: 네 행이고 네 버튼이 눌려 있다
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(5)
    for (const n of [1, 2, 3, 4]) expect(within(screen.getByRole('group', { name: 'Quarter' })).getByRole('button', { name: `Q${n}` })).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('고른 분기만 보이는 Quarter Closing Forecast', () => {
  // 테스트 코드: DSH-045
  it('고른 분기 행만 오름차순으로 보인다', async () => {
    // when: Q3·Q1을 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3%2C1')
    const rows = within(screen.getByRole('table')).getAllByRole('row')

    // then: Q1, Q3 두 행뿐이다
    expect(rows).toHaveLength(3)
    expect(rows[1]).toHaveTextContent('Q1')
    expect(rows[2]).toHaveTextContent('Q3')
    expect(screen.queryByRole('row', { name: /Q2/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /Q4/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-045
  it('분기 하나를 고르면 한 행만 보인다', async () => {
    // when: Q4를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=4')

    // then: Q4 한 행이다
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(2)
    expect(screen.getByRole('row', { name: /Q4/ })).toBeVisible()
  })

  // 테스트 코드: DSH-045
  it('어느 행도 현재·선택으로 표시하지 않는다', async () => {
    // when: Q1·Q3를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')

    // then: aria-current가 붙은 행이 없다
    const marked = within(screen.getByRole('table'))
      .getAllByRole('row')
      .filter((row) => row.hasAttribute('aria-current'))
    expect(marked).toHaveLength(0)
  })

  // 테스트 코드: DSH-045
  it('Selected Quarter 영역이 없다(제목·묶음·문구 모두)', async () => {
    // when: Q1·Q3를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')

    // then: Selected Quarter 관련 요소가 없다
    expect(screen.queryByRole('group', { name: 'Selected Quarter' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Selected Quarter/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/Selected Quarter/)).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-030
  it('예전 sq 키는 무시한다', async () => {
    // when: 예전 sq가 붙은 Forecast 탭 주소를 연다
    const { user, location } = await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&sq=3')

    // then: 네 분기를 모두 보이고 Selected Quarter가 없다
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(5)
    expect(screen.queryByText(/Selected Quarter/)).not.toBeInTheDocument()

    // when: Q2를 누른다
    await user.click(within(screen.getByRole('group', { name: 'Quarter' })).getByRole('button', { name: 'Q2' }))

    // then: forecast.quarter=2만 쓰이고 sq는 쓰이지 않는다
    await waitFor(() => expect(location()).toContain('forecast.quarter=2'))
    expect(location()).not.toContain('sq=')
  })

  // 테스트 코드: DSH-041
  it('고른 분기의 타일을 서버가 답한 그대로 보인다', async () => {
    // given: Q1·Q3를 고른 응답(타일 값은 서버가 정한 값)
    const base = dashboardSummaryFixture()
    const [q1, , q3] = base.quarters
    const sum = (pick: (q: NonNullable<typeof q1>) => { count: number; amount: number }) =>
      [q1, q3].reduce((t, q) => ({ count: t.count + pick(q as NonNullable<typeof q1>).count, amount: t.amount + pick(q as NonNullable<typeof q1>).amount }), { count: 0, amount: 0 })
    const pipeline = sum((q) => q.cells.pipeline ?? { count: 0, amount: 0 })
    const summary = dashboardSummaryFixture({
      period: { year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' },
      forecast: { ...base.forecast, cells: { ...base.forecast.cells, pipeline } },
    })

    // when: Q1·Q3를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3', summary)
    const top = within(screen.getByRole('region', { name: 'Forecast 구분별 금액(단위:원)' }))

    // then: Pipeline 타일이 응답 값이고 Won 제목에 고른 분기가 붙는다
    expect(top.getByRole('link', { name: /Pipeline/ })).toHaveTextContent(`${pipeline.count}건`)
    expect(top.getByRole('link', { name: /Pipeline/ })).toHaveTextContent(won(pipeline.amount))
    expect(top.getByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026 Q1, Q3)')
  })

  // 테스트 코드: DSH-040
  it('보이는 분기 행에 Deal이 없으면 빈 상태 문구를 보인다', async () => {
    // given: 보이지 않는 Q2·Q4 행에만 값이 있는 응답
    const empty = emptyDashboardSummary()
    const full = dashboardSummaryFixture()
    const summary = { ...empty, quarters: empty.quarters.map((q) => (q.quarter === 2 || q.quarter === 4 ? (full.quarters[q.quarter - 1] ?? q) : q)) }

    // when: Q1·Q3를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3', summary)

    // then: 빈 상태 문구가 보인다
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })

  // 테스트 코드: DSH-040
  it('보이는 분기 행에 Deal이 있으면 빈 상태 문구가 없다', async () => {
    // when: Q1·Q3를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')

    // then: 빈 상태 문구가 없다
    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()
  })
})

describe('Closing Attention 타일', () => {
  // 테스트 코드: DSH-047
  it('이번 달·이번 분기·미업데이트 타일을 보인다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()

    // then: 세 타일이 건수와 링크를 가진다
    expect(screen.getByRole('link', { name: /이번 달.*10월.*Expected Close\s*4/ })).toHaveAttribute('href', `/deals?year=2026&month=10&forecast=${OPEN_PARAM}`)
    expect(screen.getByRole('link', { name: /이번 분기.*Expected Close\s*7/ })).toHaveAttribute('href', `/deals?year=2026&quarter=4&forecast=${OPEN_PARAM}`)
    expect(screen.getByRole('link', { name: /14일 이상 미업데이트\D*5/ })).toHaveAttribute('href', '/deals?stale=1')
  })

  // 테스트 코드: DSH-047
  it('기한초과 타일은 없다(Status 탭 몫이다)', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()

    // then: 기한초과 링크가 없다
    expect(screen.queryByRole('link', { name: /기한초과/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-048
  it('담당자·Vendor만 싣고 이번 달은 서버가 준 달을 쓴다', async () => {
    // given: 이번 달이 2027-01·2건인 응답
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, closingThisMonth: { year: 2027, month: 1, count: 2 } } })

    // when: 2026년 Q2·김영업 조건으로 Forecast 탭을 연다
    await renderAt(`/dashboard?tab=forecast&year=2026&quarter=2&owner=${USER_ID.kim}`)
    const tile = await screen.findByRole('link', { name: /이번 달.*1월/ })

    // then: 링크가 응답의 연·월과 담당자, Open 집합을 담는다
    expect(tile).toHaveAttribute('href', `/deals?year=2027&month=1&owner=${USER_ID.kim}&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-047
  it('미업데이트 타일에 경고 기준일을 보인다', async () => {
    // given: 경고 기준 21일·미업데이트 1건인 응답
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, staleDays: 21, stale: 1 } })

    // when: Forecast 탭을 연다
    await renderAt('/dashboard?tab=forecast&year=2026')

    // then: "21일 이상 미업데이트 1건"이 보인다
    expect(await screen.findByRole('link', { name: /21일 이상 미업데이트\D*1/ })).toBeVisible()
  })
})
