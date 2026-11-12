import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { clickBar, clickEmptyArea, lastChart, renderedCharts } from '../../test/chartMock'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { canvases, mockSummary, NOT_LOST_PARAM, NOW } from './testHelpers'

/**
 * Status 막대 차트. react-chartjs-2는 setup.ts의 전역 mock(test/chartMock)이 바꿔 끼워 받은 data·options를 기록한다.
 * 막대 높이는 금액(원), 건수는 축 라벨 `이름 (N건)`에 둔다. 막대를 누르면 표의 행 링크와 같은 곳으로 이동한다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const STATUS_LABELS = [
  '기회발굴 (14건)',
  '제품소개 (6건)',
  'POC준비 (4건)',
  'POC완료 (3건)',
  '기술평가 (2건)',
  '가격협상 (2건)',
  '계약완료 (2건)',
]
const AMOUNTS = [250_000_000, 110_000_000, 80_000_000, 70_000_000, 60_000_000, 60_000_000, 40_000_000]

async function openStatusTab(url = '/dashboard?year=2026') {
  mockSummary(dashboardSummaryFixture())
  const view = await renderAt(url)
  await screen.findByRole('table')
  return view
}

describe('차트 데이터', () => {
  // 테스트 코드: DSH-043
  it('Status마다 코드 순서로 막대 하나이고 라벨은 이름과 건수다', async () => {
    // when: Status 탭을 연다
    await openStatusTab()

    // then: 라벨이 "이름 (N건)" 코드 순서다
    expect(lastChart().data.labels).toEqual(STATUS_LABELS)
  })

  // 테스트 코드: DSH-043
  it('막대 높이는 원 금액이고 데이터셋은 하나다', async () => {
    // when: Status 탭을 연다
    await openStatusTab()
    const { datasets } = lastChart().data

    // then: 데이터셋 하나의 값이 원 금액이다
    expect(datasets).toHaveLength(1)
    expect(datasets[0]?.data).toEqual(AMOUNTS)
  })

  // 테스트 코드: DSH-043
  it('Deal이 없는 Status는 높이 0 막대로 보인다', async () => {
    // given: POC완료가 0건인 응답
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'poc_completed' ? { ...i, count: 0, amount: 0 } : i)) },
    })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    // then: POC완료 막대의 라벨은 0건이고 값은 0이다
    expect(lastChart().data.labels?.[3]).toBe('POC완료 (0건)')
    expect(lastChart().data.datasets[0]?.data[3]).toBe(0)
  })

  // 테스트 코드: DSH-043
  it('이름을 바꾼 Status 코드를 라벨에 따른다', async () => {
    // given: prospecting 코드 이름이 "발굴"로 바뀐 응답
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'prospecting' ? { ...i, name: '발굴' } : i)) },
    })

    // when: Status 탭을 연다
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    // then: 첫 라벨이 "발굴 (14건)"이다
    expect(lastChart().data.labels?.[0]).toBe('발굴 (14건)')
  })

  // 테스트 코드: DSH-043
  it('Forecast 탭에는 그리지 않는다', async () => {
    // given: 고정 값의 요약 응답
    mockSummary(dashboardSummaryFixture())

    // when: Forecast 탭을 연다
    await renderAt('/dashboard?tab=forecast&year=2026')
    await screen.findByRole('table')

    // then: Status 라벨의 차트가 없다
    expect(renderedCharts().every((chart) => chart.data.labels?.[0] !== STATUS_LABELS[0])).toBe(true)
  })
})

describe('막대 클릭은 Deal 목록으로 이동한다', () => {
  // 테스트 코드: DSH-054
  it('누른 Status를 Lost 제외로 연다', async () => {
    // given: Status 차트가 그려진 화면
    const { location } = await openStatusTab()

    // when: 세 번째 막대(POC준비)를 누른다
    clickBar(lastChart(), { index: 2 })

    // then: 그 Status와 Lost 제외 집합의 목록으로 간다
    await waitFor(() => expect(location()).toBe(`/deals?year=2026&status=poc_preparation&forecast=${NOT_LOST_PARAM}`))
  })

  // 테스트 코드: DSH-054
  it.each([
    [0, 'prospecting'],
    [3, 'poc_completed'],
    [6, 'contract_completed'],
  ])('막대 %i은 Status %s 목록을 연다', async (index, key) => {
    // given: Status 차트가 그려진 화면
    const { location } = await openStatusTab()

    // when: 해당 막대를 누른다
    clickBar(lastChart(), { index })

    // then: 그 Status 목록으로 간다
    await waitFor(() => expect(location()).toBe(`/deals?year=2026&status=${key}&forecast=${NOT_LOST_PARAM}`))
  })

  // 테스트 코드: DSH-054
  it('Dashboard의 분기·담당자·Vendor를 함께 싣는다', async () => {
    // given: Q3·김영업·Okta 조건의 Status 차트
    const vendor = seedVendorId('Okta')
    const { location } = await openStatusTab(`/dashboard?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`)

    // when: POC완료 막대를 누른다
    clickBar(lastChart(), { index: 3 })

    // then: 조건이 모두 실린 목록으로 간다
    await waitFor(() => expect(location()).toBe(`/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}&status=poc_completed&forecast=${NOT_LOST_PARAM}`))
  })

  // 테스트 코드: DSH-054
  it('막대가 아닌 곳을 누르면 아무 일도 없다', async () => {
    // given: Status 차트가 그려진 화면
    const { location } = await openStatusTab()

    // when: 막대가 아닌 빈 곳을 누른다
    clickEmptyArea(lastChart())

    // then: 주소가 그대로다
    expect(location()).toBe('/dashboard?year=2026')
  })

  // 테스트 코드: DSH-054
  it('그 표 행의 링크와 같은 곳으로 간다', async () => {
    // given: Status 차트와 POC완료 표 행 링크
    const { location } = await openStatusTab()
    const href = within(screen.getByRole('row', { name: /POC완료/ })).getByRole('link').getAttribute('href')

    // when: POC완료 막대를 누른다
    clickBar(lastChart(), { index: 3 })

    // then: 표 링크와 같은 주소로 간다
    await waitFor(() => expect(location()).toBe(href))
  })

  // 테스트 코드: DSH-054
  it('막대 위에서만 손가락 커서를 보인다', async () => {
    // given: Status 차트의 hover 처리
    await openStatusTab()
    const { onHover } = lastChart().options
    const target = document.createElement('canvas')
    const event = { native: { target } } as never

    // when: 막대 위로 올린다
    onHover?.(event, [{ index: 0, datasetIndex: 0 }] as never, {} as never)

    // then: 손가락 커서다
    expect(target.style.cursor).toBe('pointer')

    // when: 막대가 아닌 곳으로 올린다
    onHover?.(event, [] as never, {} as never)

    // then: 손가락 커서가 아니다
    expect(target.style.cursor).not.toBe('pointer')
  })
})

describe('접근성', () => {
  // 테스트 코드: DSH-043
  it('차트 영역에 이미지 역할과 요약 이름을 준다', async () => {
    // when: Status 탭을 연다
    await openStatusTab()
    const charts = canvases()
    // then: 차트 하나가 접근성 이름을 가진다
    expect(charts).toHaveLength(1)
    expect(charts[0]).toHaveAccessibleName(/.+/)
  })

  // 테스트 코드: DSH-054
  it('막대마다 있는 표 행 링크를 키보드로 쓸 수 있다', async () => {
    // given: 가격협상 행 링크에 포커스를 둔다
    const { user, location } = await openStatusTab()
    const rowLink = within(screen.getByRole('row', { name: /가격협상/ })).getByRole('link')
    rowLink.focus()
    expect(rowLink).toHaveFocus()

    // when: Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 가격협상 목록으로 간다
    await waitFor(() => expect(location()).toBe(`/deals?year=2026&status=price_negotiation&forecast=${NOT_LOST_PARAM}`))
  })

  // 테스트 코드: DSH-054
  it('Tab으로 모든 행 링크와 합계 링크에 닿는다', async () => {
    // given: 표의 링크 8개와 첫 링크의 포커스
    const { user } = await openStatusTab()
    const table = screen.getByRole('table')
    const links = within(table).getAllByRole('link')
    expect(links).toHaveLength(8)
    links[0]?.focus()

    // when·then: Tab을 누를 때마다 다음 링크가 포커스를 받는다
    for (const next of links.slice(1)) {
      await user.tab()
      expect(next).toHaveFocus()
    }
  })
})
