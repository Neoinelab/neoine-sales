import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { renderAt } from '../../test/mockApp'
import { mockSummary, NOW } from './testHelpers'

/**
 * 계약 1: 조건이 바뀐 뒤 새 응답이 오기 전(이전 응답을 placeholder로 보이는 동안)에는
 * - "불러오는 중…" status가 보이고,
 * - 탭 패널(role=tabpanel) 안에 role=link인 Drill-down이 하나도 없다(숫자만 보이거나 비활성이어도 링크 역할은 없어야 한다).
 * 계약 2: 요약 응답의 `today`는 "기준일" 안내 문구에만 쓰고 기본값 계산에 섞지 않는다(기본 연도는 앱 시계 `useToday`).
 * Selected Quarter는 폐지됐다(Quarter 다중 선택으로 대체).
 */

beforeEach(() => resetMock({ now: NOW })) // 클라이언트 오늘 2026-10-15 (Q4)
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const panelLinks = () => within(screen.getByRole('tabpanel')).queryAllByRole('link')
/** 영영 끝나지 않는 응답: 새 조건의 응답이 아직 오지 않은 상태. */
const hang = (spy: ReturnType<typeof mockSummary>) => spy.mockImplementation(() => new Promise(() => {}))

describe('이전 응답을 보이는 동안 Drill-down 차단', () => {
  // 테스트 코드: DSH-038
  it('Status Q3에서 Forecast 탭으로 바꾸면 불러오는 중이고 Drill-down 링크가 없다', async () => {
    // given: 응답이 온 Status 탭(Q3)과 다음 응답이 오지 않는 요약 조회
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=3')
    await screen.findByText(/기준일 2026-10-15/)
    expect(panelLinks().length).toBeGreaterThan(0) // 전제: 응답이 온 뒤에는 링크가 있다
    hang(spy)

    // when: Forecast 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    // then: "불러오는 중…"이 보이고 패널에 링크가 없다
    expect(await screen.findByRole('status')).toHaveTextContent('불러오는 중…')
    expect(panelLinks()).toHaveLength(0)
  })

  // 테스트 코드: DSH-038
  it('Forecast에서 Status 탭으로 바꾸면 불러오는 중이고 Drill-down 링크가 없다', async () => {
    // given: 응답이 온 Forecast 탭(Q3)과 다음 응답이 오지 않는 요약 조회
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3')
    await screen.findByText(/기준일 2026-10-15/)
    expect(panelLinks().length).toBeGreaterThan(0)
    hang(spy)

    // when: Status 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Status' }))

    // then: "불러오는 중…"이 보이고 패널에 링크가 없다
    expect(await screen.findByRole('status')).toHaveTextContent('불러오는 중…')
    expect(panelLinks()).toHaveLength(0)
  })

  // 테스트 코드: DSH-038
  it('연도를 바꾸면 불러오는 중이고 Drill-down 링크가 없다', async () => {
    // given: 응답이 온 Forecast 탭과 다음 응답이 오지 않는 요약 조회
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=forecast&forecast.year=2026')
    await screen.findByText(/기준일 2026-10-15/)
    expect(panelLinks().length).toBeGreaterThan(0)
    hang(spy)

    // when: 연도를 2027로 바꾼다
    await user.selectOptions(screen.getByLabelText('연도'), '2027')

    // then: "불러오는 중…"이 보이고 패널에 링크가 없다
    expect(await screen.findByRole('status')).toHaveTextContent('불러오는 중…')
    expect(panelLinks()).toHaveLength(0)
  })

  // 테스트 코드: DSH-038
  it('새 응답이 오면 Drill-down 링크가 돌아온다', async () => {
    // given: 응답이 온 Status 탭(Q3)과 곧 도착할 다음 응답
    const spy = mockSummary(dashboardSummaryFixture())
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=3')
    await screen.findByText(/기준일 2026-10-15/)
    spy.mockResolvedValue(dashboardSummaryFixture())

    // when: Forecast 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    // then: 응답이 오면 링크가 돌아오고 불러오는 중 표시는 사라진다
    await waitFor(() => expect(panelLinks().length).toBeGreaterThan(0))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('기준일 안내와 기본값은 앱 시계 기준', () => {
  // 테스트 코드: DSH-040
  it('안내 줄에는 응답의 기준일을 그대로 보인다', async () => {
    // given: 응답 today가 2026-07-01이다
    mockSummary(dashboardSummaryFixture({ today: '2026-07-01' }))

    // when: Forecast 탭을 연다
    await renderAt('/dashboard?tab=forecast&forecast.year=2026')

    // then: 안내에 기준일 2026-07-01이 보인다
    expect(await screen.findByText(/기준일 2026-07-01/)).toBeVisible()
  })

  // 테스트 코드: DSH-027
  it.each(['2026-07-01', '2026-04-01'])('응답 today %s로 분기를 고르지 않는다(기본은 분기 없음)', async (responseToday) => {
    // given: 응답 today가 올해의 다른 분기다
    mockSummary(dashboardSummaryFixture({ today: responseToday }))

    // when: Forecast 탭을 연다
    await renderAt('/dashboard?tab=forecast&forecast.year=2026')
    const group = await screen.findByRole('group', { name: 'Quarter' })

    // then: Quarter 버튼이 모두 눌리지 않았고 Selected Quarter 영역은 없다
    for (const n of [1, 2, 3, 4]) expect(within(group).getByRole('button', { name: `Q${n}` })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('group', { name: 'Selected Quarter' })).not.toBeInTheDocument()
  })
})
