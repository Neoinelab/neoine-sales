import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture, emptyDashboardSummary } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { NO_SUCH_ID } from '../../test/fake/seed/ids'
import { lastQuery, mockSummary, NOW } from './testHelpers'

/** Dashboard 화면의 틀(탭·필터·URL·빈 상태·오류·이전 값 유지). */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const STATUS_HEADING = /전체 Status Pipeline/
const FORECAST_HEADING = /Quarter Closing Forecast/

/** 필터 줄의 Quarter 토글 묶음(Q1~Q4 버튼)과 그 버튼. */
const quarterGroup = () => screen.getByRole('group', { name: 'Quarter' })
const quarterButton = (n: number) => within(quarterGroup()).getByRole('button', { name: `Q${n}` })

describe('Dashboard 화면과 탭', () => {
  // 테스트 코드: DSH-025
  it('준비 중 화면 대신 Dashboard 제목과 Status·Forecast 두 탭을 보인다', async () => {
    // when: /dashboard를 연다
    await renderAt('/dashboard')

    // then: 제목과 두 탭이 보이고 준비 중 문구는 없다
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Status' })).toBeVisible()
    expect(screen.getByRole('tab', { name: 'Forecast' })).toBeVisible()
  })

  // 테스트 코드: DSH-025
  it('처음에는 Status 탭이 선택되어 있다', async () => {
    // when: 탭 조건 없이 /dashboard를 연다
    await renderAt('/dashboard')

    // then: Status 탭이 선택되고 전체 Status Pipeline 패널이 보인다
    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'false')
    expect(await screen.findByRole('heading', { name: STATUS_HEADING })).toBeVisible()
  })

  // 테스트 코드: DSH-026
  it('URL의 tab=forecast면 Forecast 탭을 연다', async () => {
    // when: /dashboard?tab=forecast를 연다
    await renderAt('/dashboard?tab=forecast')

    // then: Forecast 탭이 선택되고 Quarter Closing Forecast 패널이 보인다
    expect(await screen.findByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('heading', { name: FORECAST_HEADING })).toBeVisible()
  })

  // 테스트 코드: DSH-026
  it.each(['reports', 'FORECAST', ''])('모르는 tab 값 %j은 Status 탭으로 연다', async (value) => {
    // when: 모르는 tab 값으로 연다
    await renderAt(`/dashboard?tab=${encodeURIComponent(value)}`)

    // then: Status 탭이 선택된다
    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
  })

  // 테스트 코드: DSH-028
  it('탭을 바꾸면 URL에 tab을 쓰고 두 탭의 조건을 함께 가진다', async () => {
    // given: Status 탭 연도 2026·Q3 조건으로 연 화면
    const { user, location } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=3')
    await screen.findByRole('heading', { name: STATUS_HEADING })

    // when: Forecast 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    // then: URL에 tab=forecast와 두 탭의 연도, Status의 분기가 있다
    await waitFor(() => expect(location()).toContain('tab=forecast'))
    expect(location()).toContain('status.year=2026')
    expect(location()).toContain('status.quarter=3')
    expect(location()).toContain('forecast.year=2026')
    expect(await screen.findByRole('heading', { name: FORECAST_HEADING })).toBeVisible()
  })

  // 테스트 코드: DSH-037
  it('두 탭이 같은 조건이면 탭을 오가도 요청을 다시 보내지 않는다', async () => {
    // given: 요약 조회를 지켜보며 /dashboard를 열고 첫 응답을 기다린다
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await screen.findByRole('heading', { name: STATUS_HEADING })
    const calls = summary.mock.calls.length

    // when: Forecast 탭으로 갔다가 Status 탭으로 돌아온다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: FORECAST_HEADING })
    await user.click(screen.getByRole('tab', { name: 'Status' }))
    await screen.findByRole('heading', { name: STATUS_HEADING })

    // then: 요청 횟수가 그대로다(요청 여부가 결과인 케이스: 화면은 두 탭 모두 정상 표시)
    expect(summary.mock.calls.length).toBe(calls)
  })
})

describe('필터', () => {
  // 테스트 코드: DSH-027
  it('조건 없이 열면 올해·분기 없음·담당자와 Vendor 전체이고 연도만 조회한다', async () => {
    // given: 요약 조회를 지켜본다 (전제: 앱 시계 2026-10-15)
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 조건 없이 /dashboard를 연다
    await renderAt('/dashboard')

    // then: 연도 2026, Quarter 버튼은 모두 눌리지 않음, 담당자·Vendor는 전체이고 조회는 연도만이다
    expect(await screen.findByLabelText('연도')).toHaveValue('2026')
    for (const n of [1, 2, 3, 4]) expect(quarterButton(n)).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('전체')
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
  })

  // 테스트 코드: DSH-032
  it('필터 바에 월 칸이 없다', async () => {
    // when: /dashboard를 연다
    await renderAt('/dashboard')
    await screen.findByLabelText('연도')

    // then: 월 칸이 없다
    expect(screen.queryByLabelText('월')).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-033
  it('연도 선택지는 URL에 있는 연도를 더해 보이고 그 연도가 선택된다', async () => {
    // when: URL 연도 2031로 연다
    await renderAt('/dashboard?year=2031')

    // then: 선택지는 시드의 이른 연도~내년에 2031이 더해지고 2031이 선택되어 있다
    const year = await screen.findByLabelText('연도')
    await waitFor(() => expect(within(year).getAllByRole('option').map((o) => o.textContent)).toEqual(['2026', '2027', '2031']))
    expect(year).toHaveValue('2031')
  })

  // 테스트 코드: DSH-034
  it('Quarter를 고르면 URL에 쓰고 탭을 유지하며 서버 조회에 보낸다', async () => {
    // given: Status 탭
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q2를 누른다
    await user.click(quarterButton(2))

    // then: URL에 status.quarter=2가 있고 탭·연도가 유지되며 조회에 분기 [2]가 간다
    await waitFor(() => expect(location()).toContain('status.quarter=2'))
    expect(location()).toContain('tab=status')
    expect(location()).toContain('status.year=2026')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
  })

  // 테스트 코드: DSH-029
  it('담당자와 Vendor를 고르면 URL에 id로 쓰고 조회에 보낸다', async () => {
    // given: 담당자·Vendor 선택지가 읽힌 화면
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard')
    const vendor = await screen.findByLabelText('Vendor')
    await within(vendor).findByRole('option', { name: 'Okta' })
    await within(screen.getByLabelText('담당자')).findByRole('option', { name: '김영업' })

    // when: 담당자 김영업, Vendor Okta를 고른다
    await user.selectOptions(screen.getByLabelText('담당자'), '김영업')
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Okta')

    // then: URL에 id가 쓰이고 조회 조건에도 id가 간다
    await waitFor(() => expect(location()).toContain(`status.owner=${USER_ID.kim}`))
    expect(location()).toContain(`status.vendor=${seedVendorId('Okta')}`)
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, ownerId: USER_ID.kim, vendorId: seedVendorId('Okta') }))
  })

  // 테스트 코드: DSH-032
  it('담당자 선택지에 퇴사자를 "이름(퇴사)"로 보인다', async () => {
    // when: /dashboard를 연다
    await renderAt('/dashboard')

    // then: 담당자 선택지에 강퇴사(퇴사)가 있다
    expect(await within(await screen.findByLabelText('담당자')).findByRole('option', { name: '강퇴사(퇴사)' })).toBeInTheDocument()
  })

  // 테스트 코드: DSH-029
  it('같은 주소를 다시 열면 같은 탭·연도·분기·담당자·Vendor를 보인다', async () => {
    // when: Forecast 탭 2027년·Q3·박영업·Okta 조건의 주소를 새로 연다
    await renderAt(`/dashboard?tab=forecast&forecast.year=2027&forecast.quarter=3&forecast.owner=${USER_ID.park}&forecast.vendor=${seedVendorId('Okta')}`)

    // then: 같은 탭과 조건이 필터 바에 보인다
    expect(await screen.findByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('연도')).toHaveValue('2027')
    expect(quarterButton(3)).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(screen.getByLabelText('담당자')).toHaveDisplayValue('박영업'))
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta'))
  })

  // 테스트 코드: DSH-030
  it('예전 공용 주소는 연도·담당자를 두 탭에, 분기를 Status 탭에만 쓴다', async () => {
    // given: 요약 조회를 지켜본다
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 예전 공용 주소(year·quarter·owner)로 Status 탭을 연다
    const { user } = await renderAt(`/dashboard?year=2026&quarter=3&owner=${USER_ID.kim}`)
    await screen.findByRole('heading', { name: STATUS_HEADING })

    // then: Status 조회에는 분기 [3]이 있다
    expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [3], ownerId: USER_ID.kim })

    // when: Forecast 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: FORECAST_HEADING })

    // then: 담당자는 같고 분기는 모두 눌리지 않았으며 조회에 분기가 없다
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
    for (const n of [1, 2, 3, 4]) expect(quarterButton(n)).toHaveAttribute('aria-pressed', 'false')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, ownerId: USER_ID.kim }))
  })

  // 테스트 코드: DSH-032
  it('Forecast 탭에도 연도·Quarter 토글·담당자·Vendor 칸이 있다', async () => {
    // when: Forecast 탭을 Q2 조건으로 연다
    await renderAt('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=2')
    await screen.findByRole('heading', { name: FORECAST_HEADING })

    // then: 네 칸이 있고 Q2가 눌려 있으며 Quarter 선택 상자는 없다
    expect(screen.getByLabelText('연도')).toBeVisible()
    expect(screen.getByLabelText('담당자')).toBeVisible()
    expect(screen.getByLabelText('Vendor')).toBeVisible()
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('combobox', { name: 'Quarter' })).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-028
  it('Forecast 탭을 다녀와도 Status 탭의 분기가 그대로 돌아온다', async () => {
    // given: Status 탭 Q2 조건
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=2')
    await screen.findByRole('group', { name: 'Quarter' })
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'true')

    // when: Forecast 탭으로 갔다가 Status 탭으로 돌아온다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: FORECAST_HEADING })
    // then: Forecast 탭에서는 Q2가 눌려 있지 않다
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'false')
    await user.click(screen.getByRole('tab', { name: 'Status' }))

    // then: Status 탭으로 돌아오면 Q2가 눌려 있다
    await screen.findByRole('heading', { name: STATUS_HEADING })
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'true')
  })

  // 테스트 코드: DSH-036
  it('목록에 없는 Vendor id는 전체로 보이고 조회에서 뺀다', async () => {
    // given: 등록되지 않은 Vendor id가 URL에 있다
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 그 주소를 열고 Vendor 목록이 읽히기를 기다린다
    await renderAt(`/dashboard?year=2026&vendor=${NO_SUCH_ID}`)
    await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })

    // then: Vendor는 전체로 보이고 조회에 Vendor가 없다
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체'))
    await waitFor(() => expect(lastQuery(summary).vendorId).toBeUndefined())
  })

  // 테스트 코드: DSH-031
  it.each(['abc', '0', '-3'])('틀린 담당자 값 %j은 무시한다', async (value) => {
    // given: 요약 조회를 지켜본다
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 틀린 owner 값으로 연다
    await renderAt(`/dashboard?owner=${value}`)

    // then: 담당자는 전체이고 조회에 담당자가 없다
    expect(await screen.findByLabelText('담당자')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary).ownerId).toBeUndefined())
  })
})

describe('빈 상태·오류·이전 값 유지', () => {
  // 테스트 코드: DSH-040
  it('맞는 Deal이 없으면 빈 상태 문구를 보이고 표는 0으로 남는다', async () => {
    // given: 모든 값이 0인 응답
    mockSummary(emptyDashboardSummary())

    // when: Status 탭을 연다
    await renderAt('/dashboard')

    // then: 빈 상태 문구가 보이고 표와 행이 그대로 있다
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByRole('row', { name: /기회발굴/ })).toBeVisible()
  })

  // 테스트 코드: DSH-040
  it('Forecast 탭에서도 빈 상태 문구를 보인다', async () => {
    // given: 모든 값이 0인 응답
    mockSummary(emptyDashboardSummary())

    // when: Forecast 탭을 연다
    await renderAt('/dashboard?tab=forecast')

    // then: 빈 상태 문구와 표가 보인다
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.getByRole('table')).toBeVisible()
  })

  // 테스트 코드: DSH-040
  it('Deal이 있으면 빈 상태 문구가 없다', async () => {
    // given: Deal이 있는 응답
    mockSummary(dashboardSummaryFixture())

    // when: Status 탭을 연다
    await renderAt('/dashboard')

    // then: 표가 보이고 빈 상태 문구는 없다
    await screen.findByRole('table')
    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-039
  it('조회가 실패하면 오류 배너를 보이고 필터는 계속 쓸 수 있다', async () => {
    // given: 요약 조회가 500 "서버 오류가 발생했습니다."로 실패한다
    const summary = vi
      .spyOn(gateway.dashboard, 'summary')
      .mockRejectedValue(new ApiError(500, { type: 'https://sales.neoine.test/problems/internal-error', title: 'x', status: 500, detail: '서버 오류가 발생했습니다.' }))

    // when: Dashboard를 연다
    const { user, location } = await renderAt('/dashboard')

    // then: 오류 배너에 서버 문구가 보이고 연도 칸은 쓸 수 있다
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    expect(screen.getByLabelText('연도')).toBeEnabled()

    // when: Q1을 누른다
    await user.click(quarterButton(1))

    // then: URL과 조회 조건이 바뀐다
    await waitFor(() => expect(location()).toContain('status.quarter=1'))
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [1] }))
  })

  // 테스트 코드: DSH-039
  it('501로 실패해도 준비 중 문구 없이 같은 오류 배너를 보인다', async () => {
    // given: 요약 조회가 501로 실패한다
    vi.spyOn(gateway.dashboard, 'summary').mockRejectedValue(
      new ApiError(501, { type: 'https://sales.neoine.test/problems/not-implemented', title: 'x', status: 501, detail: '아직 연결되지 않았습니다.' }),
    )

    // when: /dashboard를 연다
    await renderAt('/dashboard')

    // then: 오류 배너가 보이고 준비 중 문구는 없다
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-038
  it('다음 조건을 기다리는 동안 이전 숫자를 화면에 둔다', async () => {
    // given: 첫 응답이 보이는 화면과 늦게 오는 다음 응답
    const original = gateway.dashboard.summary.bind(gateway.dashboard)
    const { user, location } = await renderAt('/dashboard')
    const table = await screen.findByRole('table')
    expect(table).toBeVisible()
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.spyOn(gateway.dashboard, 'summary').mockImplementation(async (query) => {
      await gate
      return original(query)
    })

    // when: Q2를 눌러 새 조건을 요청한다
    await user.click(quarterButton(2))

    // then: URL은 바뀌었고 응답 전에는 이전 표가 그대로이며 빈 상태 문구가 깜빡이지 않는다
    expect(location()).toContain('status.quarter=2')
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()

    // when: 응답이 도착한다
    release()
    await waitFor(() => expect(gateway.dashboard.summary).toHaveBeenCalledTimes(1))

    // then: 표가 계속 보인다
    expect(screen.getByRole('table')).toBeVisible()
  })
})
