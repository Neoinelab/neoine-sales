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
 * Drill-down으로 연 Deal 목록. Fake 게이트웨이의 실제 계산을 쓰고 화면을 끝까지 따라간다.
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

describe('이동과 목록 조건', () => {
  // 테스트 코드: DSH-050
  it('누른 조건만으로 Deals 목록을 열고 기억해 둔 정렬·페이지는 버린다', async () => {
    // given: 목록 기억에 예전 정렬·페이지가 있고 /dashboard?year=2026을 연 화면
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await screen.findByRole('link', { name: /Pipeline/ })

    // when: Pipeline 타일을 누른다
    await view.user.click(screen.getByRole('link', { name: /Pipeline/ }))

    // then: 주소와 목록 기억이 누른 조건뿐이다
    await waitFor(() => expect(view.location()).toBe('/deals?year=2026&forecast=pipeline'))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=2026&forecast=pipeline')
  })

  // 테스트 코드: DSH-050
  it('목록 필터 바에 같은 값을 보인다', async () => {
    // given: 2026년 Q4·김영업 조건의 Dashboard
    const view = await renderAt(`/dashboard?year=2026&quarter=4&owner=${USER_ID.kim}`)
    const row = await screen.findByRole('row', { name: /기회발굴/ })

    // when: 기회발굴 행 링크를 누른다
    await view.user.click(within(row).getByRole('link'))

    // then: 필터 바에 기회발굴·2026·Q4·김영업 (kim)이 보이고 Forecast 구분 칸은 없다
    expect(await screen.findByLabelText('Status')).toHaveDisplayValue('기회발굴')
    expect(screen.queryByLabelText('Forecast 구분')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Close 연도')).toHaveDisplayValue('2026')
    expect(screen.getByRole('button', { name: 'Quarter Q4' })).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('담당자')).toHaveValue('김영업 (kim)'))
  })

  // 테스트 코드: DSH-050
  it('다른 화면을 거쳐도 상단 메뉴 Deals가 Drill-down 조건을 다시 연다', async () => {
    // given: 목록 기억에 예전 조건이 있고 Open 합계를 눌러 목록에 간 화면
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))
    await screen.findByLabelText('Status')

    // when: Forecast 화면을 거쳐 상단 메뉴 Deals를 누른다
    await view.user.click(mainMenu(view).getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })
    await view.user.click(mainMenu(view).getByRole('link', { name: 'Deals' }))

    // then: 누른 Open 합계 조건의 주소가 열린다
    await waitFor(() => expect(view.location()).toBe(`/deals?year=2026&forecast=${OPEN_PARAM}`))
  })

  // 테스트 코드: DSH-053
  it('뒤로 가기는 같은 탭·조건의 Dashboard로 돌아온다', async () => {
    // given: Forecast 탭 Q3·Q4 조건에서 Q4 행 링크를 눌러 목록에 간 화면
    const start = '/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3%2C4'
    const view = await renderAt(start)
    const row = await screen.findByRole('row', { name: /Q4/ })
    await view.user.click(within(row).getAllByRole('link')[0] as HTMLElement)
    await screen.findByLabelText('Status')

    // when: 브라우저 뒤로 가기를 한다
    view.goTo(-1)

    // then: 같은 주소의 Forecast 탭이고 Q3가 눌려 있다
    await waitFor(() => expect(view.location()).toBe(start))
    expect(await screen.findByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'true')
    expect(within(await screen.findByRole('group', { name: 'Quarter' })).getByRole('button', { name: 'Q3' })).toHaveAttribute('aria-pressed', 'true')
  })

  // 테스트 코드: DSH-053
  it('Dashboard를 보기만 해서는 목록 기억이 바뀌지 않는다', async () => {
    // when: 조건이 있는 Dashboard를 열어 보기만 한다(전제: 목록 기억 없음)
    const view = await renderAt(`/dashboard?year=2026&quarter=2&owner=${USER_ID.park}`)
    await screen.findByRole('link', { name: /Pipeline/ })

    // then: 목록 기억이 비어 있다
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBeNull()

    // when: 아무것도 누르지 않고 상단 메뉴 Deals를 누른다
    await view.user.click(mainMenu(view).getByRole('link', { name: 'Deals' }))

    // then: 기본 Deals 목록 주소로 간다
    await waitFor(() => expect(view.location()).toBe(defaultDealsUrl(NOW)))
  })

  // 테스트 코드: DSH-054
  it('차트 막대로도 표 링크와 같은 방식으로 목록을 연다', async () => {
    // given: 목록 기억에 예전 조건이 있고 Status 차트가 그려진 화면
    const view = await renderAt('/dashboard?year=2026')
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), STALE_MEMORY)
    await screen.findByRole('table')

    // when: POC완료 막대(네 번째)를 누른다
    clickBar(lastChart(), { index: 3 })

    // then: POC완료 조건의 주소로 가고 목록 기억도 그 조건이다
    const expected = `year=2026&status=poc_completed&forecast=${NOT_LOST_PARAM}`
    await waitFor(() => expect(view.location()).toBe(`/deals?${expected}`))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe(expected)
  })
})

describe('목록의 건수가 누른 숫자와 같다', () => {
  // 테스트 코드: DSH-051
  it('Forecast 타일: Deal이 있는 Forecast 코드의 건수', async () => {
    // given: Deal이 있는 Forecast 코드가 있는 Dashboard
    const view = await renderAt('/dashboard?year=2026')
    const { forecast } = await summaryOf({ year: 2026 })
    const column = forecast.columns.find((c) => (forecast.cells[c.key]?.count ?? 0) > 0)
    if (!column) throw new Error('건수가 있는 Forecast가 없습니다(시드 Deal 필요).')

    // when: 그 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: new RegExp(column.name) }))

    // then: 목록 총 건수가 타일 건수와 같다
    await listCount(view, forecast.cells[column.key]?.count ?? -1)
  })

  // 테스트 코드: DSH-051
  it('Open 합계 타일은 요약의 Open 합계와 같다', async () => {
    // given: Open Deal이 있는 Dashboard
    const view = await renderAt('/dashboard?year=2026')
    const open = (await summaryOf({ year: 2026 })).forecast.openTotal.count
    expect(open).toBeGreaterThan(0)

    // when: Open 합계 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))

    // then: 목록 총 건수가 Open 합계와 같다
    await listCount(view, open)
    expect(view.location()).toBe(`/deals?year=2026&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-051
  it('Status 표 행은 그 건수와, 합계 행은 Lost 제외 합계와 같다', async () => {
    // given: Deal이 있는 Status가 있는 Dashboard
    const view = await renderAt('/dashboard?year=2026')
    const { statuses } = await summaryOf({ year: 2026 })
    const first = statuses.items.find((item) => item.count > 0)
    if (!first) throw new Error('건수가 있는 Status가 없습니다(시드 Deal 필요).')

    // when: 그 Status 행 링크를 누른다
    await view.user.click(within(await screen.findByRole('row', { name: new RegExp(first.name) })).getByRole('link'))

    // then: 목록 총 건수가 행 건수와 같다
    await listCount(view, first.count)
    expect(view.location()).toBe(`/deals?year=2026&status=${first.key}&forecast=${NOT_LOST_PARAM}`)

    // when: 뒤로 가서 합계 행 링크를 누른다
    view.goTo(-1)
    expect(statuses.total.count).toBeGreaterThan(0)
    await view.user.click(within(await screen.findByRole('row', { name: /합계/ })).getByRole('link'))

    // then: 목록 총 건수가 합계와 같다
    await listCount(view, statuses.total.count)
    expect(view.location()).toBe(`/deals?year=2026&forecast=${NOT_LOST_PARAM}`)
  })

  // 테스트 코드: DSH-051
  it('모든 Status 행의 건수가 목록과 같다(그 Status의 Lost Deal은 목록에 없다)', async () => {
    // given: 요약의 Status 항목
    const { statuses } = await summaryOf({ year: 2026 })

    // when·then: 항목마다 같은 조건 Deal 목록 total이 항목 건수와 같다
    for (const item of statuses.items) {
      expect(await dealsTotal({ year: 2026, statusKey: item.key, forecastKeys: NOT_LOST_PARAM.split('%2C') })).toBe(item.count)
    }
  })

  // 테스트 코드: DSH-051
  it('기한초과·미업데이트 타일은 기간을 무시한다', async () => {
    // given: Q1을 고른 Dashboard
    const view = await renderAt('/dashboard?year=2026&quarter=1')
    const { attention } = await summaryOf({ year: 2026, quarters: [1] })
    expect(attention.overdue).toBeGreaterThan(0)

    // when: 기한초과 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: /기한초과/ }))

    // then: 기간 없는 주소이고 목록 총 건수가 기한초과 수와 같다
    await listCount(view, attention.overdue)
    expect(view.location()).toBe('/deals?overdue=1')

    // when: 뒤로 가서 미업데이트 타일을 누른다
    view.goTo(-1)
    await view.user.click(await screen.findByRole('link', { name: /미업데이트/ }))

    // then: 목록 건수가 미업데이트 수와 같다(0이면 빈 상태 문구)
    if (attention.stale === 0) await screen.findByText('조건에 맞는 Deal이 없습니다.')
    else await listCount(view, attention.stale)
  })

  // 테스트 코드: DSH-051
  it('이번 분기 타일은 서버 분기의 Open Deal 목록을 열고 건수가 같다', async () => {
    // given: 연도를 2020으로 본 Dashboard(이번 분기는 기간과 무관)
    const view = await renderAt('/dashboard?year=2020')
    const { attention } = await summaryOf({ year: 2020 })
    expect(attention.closingThisQuarter.count).toBeGreaterThan(0)

    // when: 이번 분기 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: /이번 분기/ }))

    // then: 서버 연·분기의 Open 목록이고 총 건수가 같다
    const { year, quarter } = attention.closingThisQuarter
    await listCount(view, attention.closingThisQuarter.count)
    expect(view.location()).toBe(`/deals?year=${year}&quarter=${quarter}&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-051
  it('Forecast 탭의 이번 달 타일은 그 건수와 같다', async () => {
    // given: Forecast 탭 Dashboard
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { attention } = await summaryOf({ year: 2026 })
    expect(attention.closingThisMonth.count).toBeGreaterThan(0)

    // when: 이번 달 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: /이번 달/ }))

    // then: 서버 연·월의 Open 목록이고 총 건수가 같다
    const { year, month } = attention.closingThisMonth
    await listCount(view, attention.closingThisMonth.count)
    expect(view.location()).toBe(`/deals?year=${year}&month=${month}&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-051
  it('Forecast 탭 분기 합계 칸은 그 분기의 합계와 같다', async () => {
    // given: Deal이 있는 분기가 있는 Forecast 탭
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { quarters } = await summaryOf({ year: 2026 })
    const target = quarters.find((q) => q.total.count > 0)
    if (!target) throw new Error('건수가 있는 분기가 없습니다(시드 Deal 필요).')

    // when: 그 분기 행의 합계 칸을 누른다
    const row = await screen.findByRole('row', { name: new RegExp(`Q${target.quarter}`) })
    const totalLink = within(row).getAllByRole('link').at(-1)
    if (!totalLink) throw new Error('분기 합계 링크가 없습니다.')
    await view.user.click(totalLink)

    // then: 목록 총 건수가 분기 합계와 같다
    await listCount(view, target.total.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=${target.quarter}&forecast=${NOT_LOST_PARAM}`)
  })

  // 테스트 코드: DSH-051
  it('Forecast 탭 분기 Open 합계 칸은 그 분기의 Open 합계와 같다', async () => {
    // given: Open Deal이 있는 분기가 있는 Forecast 탭
    const view = await renderAt('/dashboard?tab=forecast&year=2026')
    const { quarters } = await summaryOf({ year: 2026 })
    const target = quarters.find((q) => q.openTotal.count > 0)
    if (!target) throw new Error('Open 건수가 있는 분기가 없습니다(시드 Deal 필요).')

    // when: 그 분기 행의 Open 합계 칸을 누른다
    const row = await screen.findByRole('row', { name: new RegExp(`Q${target.quarter}`) })
    const links = within(row).getAllByRole('link')
    await view.user.click(links.at(-2) as HTMLElement)

    // then: 목록 총 건수가 분기 Open 합계와 같다
    await listCount(view, target.openTotal.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=${target.quarter}&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-051
  it('admin이 추가한 Open Forecast 코드가 Open 합계 링크에 들고 목록 건수가 타일과 같다', async () => {
    // given: admin이 Verbal Open 코드와 그 Deal을 추가했다
    const view = await renderAt('/deals?year=all', { role: 'admin' })
    await screen.findByRole('search', { name: 'Deal 필터' })
    const verbal = await gateway.codes.create({ kind: 'forecast', name: 'Verbal' })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Verbal 건', forecastKey: verbal.key, revenueDate: '2026-11-20' }))
    const { forecast, statuses } = await summaryOf({ year: 2026 })
    expect(forecast.columns.map((c) => c.key)).toContain(verbal.key)

    // when: Dashboard의 Open 합계 타일을 누른다
    view.goTo('/dashboard?year=2026')
    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    // then: 링크의 Open 집합에 Verbal이 있고(오름차순) 목록 건수가 Open 합계와 같다
    const keys = new URLSearchParams((tile.getAttribute('href') ?? '').split('?')[1]).get('forecast')?.split(',')
    expect(keys).toContain(verbal.key)
    expect(keys).toEqual([...(keys ?? [])].sort())
    await view.user.click(tile)
    await listCount(view, forecast.openTotal.count)

    // when: 뒤로 가서 Status 합계 행을 누른다
    view.goTo(-1)
    await view.user.click(within(await screen.findByRole('row', { name: /합계/ })).getByRole('link'))

    // then: Lost 제외 집합에도 Verbal이 있고 목록 건수가 Status 합계와 같다
    await listCount(view, statuses.total.count)
    expect(view.location().split('forecast=')[1]).toContain(encodeURIComponent(verbal.key))
  })
})

describe('고른 분기의 Drill-down은 목록 건수와 같다', () => {
  const SEVERAL = '/dashboard?tab=status&status.year=2026&status.quarter=1%2C3&forecast.year=2026'

  // 테스트 코드: DSH-052
  it('여러 분기의 Forecast 타일은 같은 분기 목록을 같은 건수로 연다', async () => {
    // given: Q1·Q3를 고른 Dashboard
    const view = await renderAt(SEVERAL)
    const { forecast } = await summaryOf({ year: 2026, quarters: [1, 3] })
    const column = forecast.columns.find((c) => (forecast.cells[c.key]?.count ?? 0) > 0)
    if (!column) throw new Error('Q1·Q3에 건수가 있는 Forecast가 없습니다(시드 Deal 필요).')

    // when: Deal이 있는 Forecast 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: new RegExp(column.name) }))

    // then: Q1·Q3 목록이고 총 건수가 타일과 같다
    await listCount(view, forecast.cells[column.key]?.count ?? -1)
    expect(view.location()).toBe(`/deals?year=2026&quarter=1%2C3&forecast=${column.key}`)
  })

  // 테스트 코드: DSH-052
  it('여러 분기의 Open 합계 타일은 목록 총 건수와 같다', async () => {
    // given: Q1·Q3를 고른 Dashboard와 Q1의 Open Deal
    const view = await renderAt(SEVERAL)
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Q1 Open Deal', forecastKey: 'pipeline', revenueDate: '2026-02-10' }))
    await view.client.invalidateQueries()
    const open = (await summaryOf({ year: 2026, quarters: [1, 3] })).forecast.openTotal.count
    expect(open).toBeGreaterThan(0)

    // when: Open 합계 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))

    // then: Q1·Q3 Open 목록이고 총 건수가 같다
    await listCount(view, open)
    expect(view.location()).toBe(`/deals?year=2026&quarter=1%2C3&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-052
  it('여러 분기의 Status 행과 합계 행은 목록 총 건수와 같다', async () => {
    // given: Q1·Q3를 고른 Dashboard
    const view = await renderAt(SEVERAL)
    const { statuses } = await summaryOf({ year: 2026, quarters: [1, 3] })
    const first = statuses.items.find((item) => item.count > 0)
    if (!first) throw new Error('Q1·Q3에 건수가 있는 Status가 없습니다(시드 Deal 필요).')

    // when: Deal이 있는 Status 행을 누른다
    await view.user.click(within(await screen.findByRole('row', { name: new RegExp(first.name) })).getByRole('link'))

    // then: Q1·Q3 목록이고 총 건수가 행 건수와 같다
    await listCount(view, first.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=1%2C3&status=${first.key}&forecast=${NOT_LOST_PARAM}`)

    // when: 뒤로 가서 합계 행을 누른다
    view.goTo(-1)
    await view.user.click(within(await screen.findByRole('row', { name: /합계/ })).getByRole('link'))

    // then: Q1·Q3 목록이고 총 건수가 합계와 같다
    await listCount(view, statuses.total.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=1%2C3&forecast=${NOT_LOST_PARAM}`)
  })

  // 테스트 코드: DSH-035
  it('넷 다 눌러도 링크에 분기 키가 없어 연도 전체를 연다', async () => {
    // given: 넷 다 누른 Status 탭
    const view = await renderAt('/dashboard?status.year=2026&status.quarter=1%2C2%2C3%2C4')

    // when: Open 합계 타일을 누른다
    await view.user.click(await screen.findByRole('link', { name: /Open 합계/ }))

    // then: 분기 없이 연도 전체의 Open 목록으로 간다
    await waitFor(() => expect(view.location()).toBe(`/deals?year=2026&forecast=${OPEN_PARAM}`))
  })

  // 테스트 코드: DSH-052
  it('분기 칸은 어느 분기를 골랐든 그 분기 하나만 연다', async () => {
    // given: Q1·Q3를 고른 Forecast 탭
    const view = await renderAt('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')
    const { quarters } = await summaryOf({ year: 2026, quarters: [1, 3] })
    const target = quarters.find((q) => q.quarter === 3 && q.total.count > 0)
    if (!target) throw new Error('Q3에 건수가 있는 분기가 없습니다(시드 Deal 필요).')

    // when: Q3 행의 합계 칸을 누른다
    const row = await screen.findByRole('row', { name: /Q3/ })
    await view.user.click(within(row).getAllByRole('link').at(-1) as HTMLElement)

    // then: Q3 하나의 목록이고 총 건수가 같다
    await listCount(view, target.total.count)
    expect(view.location()).toBe(`/deals?year=2026&quarter=3&forecast=${NOT_LOST_PARAM}`)
  })

  // 테스트 코드: DSH-052
  it('이번 분기·기한초과 타일 주소는 어느 분기를 골랐든 같다', async () => {
    // when: Q1·Q3를 고른 Status 탭을 연다
    await renderAt(SEVERAL)

    // then: 이번 분기와 기한초과 링크가 분기를 고르지 않았을 때와 같다
    expect(await screen.findByRole('link', { name: /이번 분기/ })).toHaveAttribute('href', `/deals?year=2026&quarter=4&forecast=${OPEN_PARAM}`)
    expect(screen.getByRole('link', { name: /기한초과/ })).toHaveAttribute('href', '/deals?overdue=1')
  })

  // 테스트 코드: DSH-048
  it('링크와 Vendor 판정에는 활성 탭의 조건만 쓴다', async () => {
    // when: Status 탭에 담당자·다른 연도가 있는 주소로 Forecast 탭을 연다
    await renderAt(`/dashboard?tab=forecast&status.year=2025&status.owner=${USER_ID.kim}&forecast.year=2026`)
    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    // then: Open 합계 링크가 Forecast 탭 조건(2026)만 담는다
    expect(tile).toHaveAttribute('href', `/deals?year=2026&forecast=${OPEN_PARAM}`)
  })
})
