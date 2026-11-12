import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { clickBar, clickEmptyArea, lastChart } from '../../test/chartMock'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { canvases, mockSummary, NOW } from './testHelpers'

/**
 * 분기별 Closing Forecast 누적 막대. 데이터셋 하나가 Forecast 열 하나(Lost 없음)이고 x축은 Q1~Q4다.
 * 막대 조각을 누르면(분기 = index, Forecast = datasetIndex) 그 분기·Forecast의 Deal 목록으로 이동한다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

async function openForecastTab(url = '/dashboard?tab=forecast&forecast.year=2026', summary = dashboardSummaryFixture()) {
  mockSummary(summary)
  const view = await renderAt(url)
  await screen.findByRole('table')
  return view
}

describe('차트 데이터', () => {
  // 테스트 코드: DSH-046
  it('가로축에 Q1~Q4가 있다', async () => {
    // when: 분기 없이 Forecast 탭을 연다
    await openForecastTab()

    // then: 가로축이 Q1~Q4다
    expect(lastChart().data.labels).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  // 테스트 코드: DSH-046
  it('Forecast 열마다 코드 순서로 데이터셋 하나이고 Lost는 없으며 이름은 코드 이름이다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()

    // then: 데이터셋 이름이 코드 순서의 열 이름이다
    expect(lastChart().data.datasets.map((d) => d.label)).toEqual(['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won'])
  })

  // 테스트 코드: DSH-046
  it('모든 데이터셋이 분기별 원 금액을 담는다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()
    const [pipeline, best, mostLikely, commit, closed] = lastChart().data.datasets.map((d) => d.data)

    // then: 열마다 Q1~Q4 금액이 응답 값이다
    expect(pipeline).toEqual([40_000_000, 60_000_000, 100_000_000, 120_000_000])
    expect(best).toEqual([20_000_000, 30_000_000, 50_000_000, 50_000_000])
    expect(mostLikely).toEqual([0, 30_000_000, 30_000_000, 30_000_000])
    expect(commit).toEqual([40_000_000, 0, 20_000_000, 10_000_000])
    expect(closed).toEqual([10_000_000, 0, 30_000_000, 0])
  })

  // 테스트 코드: DSH-046
  it('두 축 모두 누적한다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()
    const scales = lastChart().options.scales as { x?: { stacked?: boolean }; y?: { stacked?: boolean } }
    // then: 가로·세로 모두 stacked다
    expect(scales.x?.stacked).toBe(true)
    expect(scales.y?.stacked).toBe(true)
  })

  // 테스트 코드: DSH-046
  it('열마다 다른 색을 준다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()
    const colours = lastChart().data.datasets.map((d) => String(d.backgroundColor))

    // then: 색이 서로 다르다
    expect(new Set(colours).size).toBe(colours.length)
  })

  // 테스트 코드: DSH-046
  it('admin이 추가한 Forecast 코드는 코드 순서에 맞게 데이터셋이 추가된다', async () => {
    // given: 코드 순서 중간에 Verbal 열이 추가된 응답
    const base = dashboardSummaryFixture()
    const verbal = { key: 'verbal', name: 'Verbal', outcome: 'open' as const, order: 35 }

    // when: Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026', {
      ...base,
      forecast: { ...base.forecast, columns: [...base.forecast.columns.slice(0, 3), verbal, ...base.forecast.columns.slice(3)] },
      quarters: base.quarters.map((q) => ({ ...q, cells: { ...q.cells, verbal: { count: 1, amount: 7_000_000 } } })),
    })

    // then: Verbal 데이터셋이 네 번째에 있고 값이 분기별 7백만이다
    expect(lastChart().data.datasets.map((d) => d.label)).toEqual(['Pipeline', 'Best', 'Most Likely', 'Verbal', 'Commit', 'Won'])
    expect(lastChart().data.datasets[3]?.data).toEqual([7_000_000, 7_000_000, 7_000_000, 7_000_000])
  })

  // 테스트 코드: DSH-030
  it('주소에 sq가 있어도 네 분기를 모두 둔다(sq 무시)', async () => {
    // when: 예전 sq가 붙은 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&sq=3')

    // then: 가로축이 Q1~Q4다
    expect(lastChart().data.labels).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  // 테스트 코드: DSH-046
  it('고른 분기만 오름차순으로 가로축에 둔다', async () => {
    // when: Q3·Q1을 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3%2C1')

    // then: 가로축이 Q1, Q3다
    expect(lastChart().data.labels).toEqual(['Q1', 'Q3'])
  })

  // 테스트 코드: DSH-046
  it('고른 분기의 금액만 담는다', async () => {
    // when: Q1·Q3를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')
    const [pipeline, best] = lastChart().data.datasets.map((d) => d.data)

    // then: Q1·Q3 금액뿐이다
    expect(pipeline).toEqual([40_000_000, 100_000_000])
    expect(best).toEqual([20_000_000, 50_000_000])
  })

  // 테스트 코드: DSH-046
  it('분기 하나를 고르면 가로축에 그 분기 하나만 둔다', async () => {
    // when: Q2를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=2')

    // then: 가로축이 Q2뿐이다
    expect(lastChart().data.labels).toEqual(['Q2'])
  })

  // 테스트 코드: DSH-046
  it('넷 다 고르면 네 분기를 모두 둔다', async () => {
    // when: 넷 다 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C2%2C3%2C4')

    // then: 가로축이 Q1~Q4다
    expect(lastChart().data.labels).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  // 테스트 코드: DSH-046
  it('어떤 막대도 흐리게 하지 않는다(Selected Quarter 강조가 없다)', async () => {
    // when: Q1·Q3를 고른 Forecast 탭을 연다
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')

    // then: 데이터셋마다 막대 색이 하나뿐이다
    for (const dataset of lastChart().data.datasets) {
      const colours = [dataset.backgroundColor].flat().map(String)
      expect(new Set(colours).size, String(dataset.label)).toBe(1)
    }
  })
})

describe('조각 클릭은 Deal 목록으로 이동한다', () => {
  // 테스트 코드: DSH-054
  it('누른 분기와 Forecast 코드를 연다', async () => {
    // given: 분기 누적 차트가 그려진 Forecast 탭
    const { location } = await openForecastTab()

    // when: Q2의 Commit 조각을 누른다
    clickBar(lastChart(), { index: 1, datasetIndex: 3 })

    // then: Q2·commit 목록으로 간다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=2&forecast=commit'))
  })

  // 테스트 코드: DSH-054
  it.each([
    [0, 0, 1, 'pipeline'],
    [3, 4, 4, 'won'],
    [2, 2, 3, 'most_likely'],
  ])('조각 index %i·데이터셋 %i은 Q%i %s 목록을 연다', async (index, datasetIndex, quarter, key) => {
    // given: 분기 누적 차트가 그려진 Forecast 탭
    const { location } = await openForecastTab()

    // when: 해당 조각을 누른다
    clickBar(lastChart(), { index, datasetIndex })

    // then: 그 분기·Forecast 목록으로 간다
    await waitFor(() => expect(location()).toBe(`/deals?year=2026&quarter=${quarter}&forecast=${key}`))
  })

  // 테스트 코드: DSH-054
  it('코드가 중간에 추가되어도 데이터셋을 그 코드 key로 연결한다', async () => {
    // given: 코드 순서 중간에 Verbal 열이 추가된 Forecast 탭
    const base = dashboardSummaryFixture()
    const verbal = { key: 'verbal', name: 'Verbal', outcome: 'open' as const, order: 35 }
    const { location } = await openForecastTab('/dashboard?tab=forecast&forecast.year=2026', {
      ...base,
      forecast: { ...base.forecast, columns: [...base.forecast.columns.slice(0, 3), verbal, ...base.forecast.columns.slice(3)] },
      quarters: base.quarters.map((q) => ({ ...q, cells: { ...q.cells, verbal: { count: 1, amount: 7_000_000 } } })),
    })

    // when: Q1의 네 번째 데이터셋(Verbal) 조각을 누른다
    clickBar(lastChart(), { index: 0, datasetIndex: 3 })

    // then: Q1·verbal 목록으로 간다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1&forecast=verbal'))
  })

  // 테스트 코드: DSH-054
  it('고른 분기가 아니라 누른 분기 하나만 열고 담당자·Vendor는 유지한다', async () => {
    // given: Q1·Q3와 담당자·Okta를 고른 Forecast 탭
    const vendor = seedVendorId('Okta')
    const { location } = await openForecastTab(`/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3&forecast.owner=${USER_ID.kim}&forecast.vendor=${vendor}`)

    // when: Best 조각의 두 번째 막대를 누른다 (축은 Q1, Q3이므로 index 1 = Q3)
    clickBar(lastChart(), { index: 1, datasetIndex: 1 })

    // then: Q3 하나와 담당자·Vendor, best를 담은 목록으로 간다
    await waitFor(() => expect(location()).toBe(`/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}&forecast=best`))
  })

  // 테스트 코드: DSH-054
  it('index를 보이는 행의 분기로 바꿔 연결한다', async () => {
    // given: Q2·Q4를 고른 Forecast 탭
    const { location } = await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=2%2C4')

    // when: 첫 막대(Q2)의 Pipeline 조각을 누른다
    clickBar(lastChart(), { index: 0, datasetIndex: 0 })

    // then: Q2·pipeline 목록으로 간다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=2&forecast=pipeline'))
  })

  // 테스트 코드: DSH-054
  it('조각이 아닌 곳을 누르면 아무 일도 없다', async () => {
    // given: 분기 누적 차트가 그려진 Forecast 탭
    const { location } = await openForecastTab()

    // when: 빈 곳을 누른다
    clickEmptyArea(lastChart())

    // then: 주소가 그대로다
    expect(location()).toBe('/dashboard?tab=forecast&forecast.year=2026')
  })

  // 테스트 코드: DSH-054
  it('그 분기·코드의 표 칸 링크와 같은 곳으로 간다', async () => {
    // given: 분기 누적 차트와 Q3 행의 링크들
    const { location } = await openForecastTab()
    const links = within(screen.getByRole('row', { name: /Q3/ })).getAllByRole('link').map((a) => a.getAttribute('href'))

    // when: Q3의 Best 조각을 누른다
    clickBar(lastChart(), { index: 2, datasetIndex: 1 })

    // then: Q3 행 링크 중 하나와 같은 주소로 간다
    await waitFor(() => expect(links).toContain(location()))
  })
})

describe('접근성', () => {
  // 테스트 코드: DSH-046
  it('차트 영역에 이미지 역할과 요약 이름을 준다', async () => {
    // when: Forecast 탭을 연다
    await openForecastTab()
    const charts = canvases()

    // then: 차트 하나가 접근성 이름을 가진다
    expect(charts).toHaveLength(1)
    expect(charts[0]).toHaveAccessibleName(/.+/)
  })

  // 테스트 코드: DSH-054
  it('표 링크를 키보드로 쓸 수 있다', async () => {
    // given: Q2 행의 첫 링크에 포커스를 둔다
    const { user, location } = await openForecastTab()
    const link = within(screen.getByRole('row', { name: /Q2/ })).getAllByRole('link')[0]
    if (!link) throw new Error('Q2 행에 링크가 없습니다.')
    const href = link.getAttribute('href')
    link.focus()
    expect(link).toHaveFocus()

    // when: Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 그 링크 주소로 간다
    await waitFor(() => expect(location()).toBe(href))
  })
})
