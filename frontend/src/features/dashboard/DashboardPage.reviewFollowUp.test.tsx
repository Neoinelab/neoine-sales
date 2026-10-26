import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { renderAt } from '../../test/mockApp'
import { mockSummary, NOW } from './testHelpers'

/**
 * 리뷰 후속(artifacts/final/review-report.md Minor 1·2).
 *
 * Minor 1 계약: 조건이 바뀐 뒤 새 응답이 오기 전(이전 응답을 placeholder로 보이는 동안)에는
 * - "불러오는 중…" status가 보이고,
 * - 탭 패널(role=tabpanel) 안에 role=link인 Drill-down이 하나도 없다(숫자만 보이거나 비활성이어도 링크 역할은 없어야 한다).
 * Minor 2 계약(2026-10-23 시간 기준 서버 통일로 변경): Selected Quarter 기본값은 앱 시계(`useToday`, 서버 동기 시계) 기준이다.
 * 요약 응답의 `today`는 "기준일" 안내 문구에만 쓰고 기본값 계산에 섞지 않는다(기본 연도와 같은 시계).
 */

beforeEach(() => resetMock({ now: NOW })) // 클라이언트 오늘 2026-10-15 (Q4)
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const panelLinks = () => within(screen.getByRole('tabpanel')).queryAllByRole('link')
/** 영영 끝나지 않는 응답: 새 조건의 응답이 아직 오지 않은 상태. */
const hang = (spy: ReturnType<typeof mockSummary>) => spy.mockImplementation(() => new Promise(() => {}))

describe('이전 응답을 보이는 동안 Drill-down 차단 (Minor 1)', () => {
  it('shows loading and no drill-down links after switching from Status quarter=3 to Forecast', async () => {
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=status&year=2026&quarter=3')
    await screen.findByText(/기준일 2026-10-15/)
    expect(panelLinks().length).toBeGreaterThan(0) // 전제: 응답이 온 뒤에는 링크가 있다
    hang(spy)

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    expect(await screen.findByRole('status')).toHaveTextContent('불러오는 중…')
    expect(panelLinks()).toHaveLength(0)
  })

  it('shows loading and no drill-down links after switching from Forecast to Status with quarter=3', async () => {
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=forecast&year=2026&quarter=3')
    await screen.findByText(/기준일 2026-10-15/)
    expect(panelLinks().length).toBeGreaterThan(0)
    hang(spy)

    await user.click(screen.getByRole('tab', { name: 'Status' }))

    expect(await screen.findByRole('status')).toHaveTextContent('불러오는 중…')
    expect(panelLinks()).toHaveLength(0)
  })

  it('shows loading and no drill-down links after changing the year', async () => {
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=forecast&year=2026')
    await screen.findByText(/기준일 2026-10-15/)
    expect(panelLinks().length).toBeGreaterThan(0)
    hang(spy)

    await user.selectOptions(screen.getByLabelText('연도'), '2027')

    expect(await screen.findByRole('status')).toHaveTextContent('불러오는 중…')
    expect(panelLinks()).toHaveLength(0)
  })

  it('brings the drill-down links back once the new response arrives', async () => {
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=status&year=2026&quarter=3')
    await screen.findByText(/기준일 2026-10-15/)
    spy.mockResolvedValue(dashboardSummaryFixture())

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    await waitFor(() => expect(panelLinks().length).toBeGreaterThan(0))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('Selected Quarter 기본값은 앱 시계 기준 (Minor 2, 서버 시간 통일 AC5)', () => {
  it.each([
    ['2026-07-01', 4],
    ['2026-04-01', 4],
  ])('ignores the response today %s and selects the quarter of the app clock (Q%i)', async (responseToday, quarter) => {
    mockSummary(dashboardSummaryFixture({ today: responseToday }))
    await renderAt('/dashboard?tab=forecast&year=2026')

    const group = await screen.findByRole('group', { name: 'Selected Quarter' })

    for (const n of [1, 2, 3, 4]) expect(within(group).getByRole('button', { name: `Q${n}` })).toHaveAttribute('aria-pressed', n === quarter ? 'true' : 'false')
    expect(screen.getByRole('heading', { level: 2, name: `Selected Quarter : Q${quarter}` })).toBeVisible()
  })

  it('still shows the response today in the notice', async () => {
    mockSummary(dashboardSummaryFixture({ today: '2026-07-01' }))
    await renderAt('/dashboard?tab=forecast&year=2026')

    expect(await screen.findByText(/기준일 2026-07-01/)).toBeVisible()
  })

  it('still lets an explicit sq win over the app clock', async () => {
    mockSummary(dashboardSummaryFixture({ today: '2026-07-01' }))
    await renderAt('/dashboard?tab=forecast&year=2026&sq=1')

    const group = await screen.findByRole('group', { name: 'Selected Quarter' })

    expect(within(group).getByRole('button', { name: 'Q1' })).toHaveAttribute('aria-pressed', 'true')
  })
})
