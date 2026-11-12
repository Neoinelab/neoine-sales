import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { lastQuery, NOW, OPEN_PARAM } from './testHelpers'

/**
 * Dashboard 탭별 검색 조건: 연도·Quarter·담당자·Vendor를 Status 탭과 Forecast 탭이 각자 따로 가진다.
 * URL에는 `tab`과 두 탭의 조건이 접두사 키(`status.*`, `forecast.*`)로 모두 남고, 조회와 Drill-down은 활성 탭 조건만 쓴다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const group = () => screen.getByRole('group', { name: 'Quarter' })
const button = (n: number) => within(group()).getByRole('button', { name: `Q${n}` })
const pressed = () => [1, 2, 3, 4].filter((n) => button(n).getAttribute('aria-pressed') === 'true')

async function waitForOptions() {
  await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })
  await within(screen.getByLabelText('담당자')).findByRole('option', { name: '김영업' })
}

describe('탭마다 조건을 따로 가진다', () => {
  // 테스트 코드: DSH-028
  it('탭을 오가도 각 탭의 마지막 조건이 남는다', async () => {
    // given: 조건 없이 연 화면과 읽힌 선택지
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await waitForOptions()

    // when: Status 탭에서 2027(다음 해)·Q2·담당자 김영업을 고른다
    await within(screen.getByLabelText('연도')).findByRole('option', { name: '2027' })
    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    await user.click(button(2))
    await user.selectOptions(screen.getByLabelText('담당자'), '김영업')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2027, quarters: [2], ownerId: USER_ID.kim }))

    // when: Forecast 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    // then: 한 번도 연 적 없는 Forecast 탭은 기본값이다
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))

    // when: Forecast 탭에서 Q4와 Vendor Okta를 고른다
    await user.click(button(4))
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Okta')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [4], vendorId: seedVendorId('Okta') }))

    // when: 다시 Status 탭으로 온다
    await user.click(screen.getByRole('tab', { name: 'Status' }))
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })

    // then: Status 탭의 마지막 조건이 보인다
    expect(screen.getByLabelText('연도')).toHaveValue('2027')
    expect(pressed()).toEqual([2])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2027, quarters: [2], ownerId: USER_ID.kim }))

    // when: 다시 Forecast 탭으로 온다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    // then: Forecast 탭은 Q4·Vendor를 그대로 가진다
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([4])
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta')
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('전체')
  })

  // 테스트 코드: DSH-028
  it('조건을 바꾸면 활성 탭만 바뀌고 다른 탭 조건은 그대로다', async () => {
    // given: Status 탭이 활성이고 Forecast 탭에 Q3가 있는 주소
    const { user, location } = await renderAt('/dashboard?tab=status&status.year=2026&forecast.year=2026&forecast.quarter=3')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Status 탭에서 Q1을 누른다
    await user.click(button(1))

    // then: Status 분기만 바뀌고 Forecast 분기는 3 그대로다
    await waitFor(() => expect(location()).toContain('status.quarter=1'))
    expect(location()).toContain('forecast.quarter=3')
  })
})

describe('주소에 두 탭의 조건이 모두 남는다', () => {
  // 테스트 코드: DSH-029
  it('두 탭의 조건을 주소에서 그대로 복원한다', async () => {
    // when: 두 탭 조건이 모두 있는 주소를 연다
    const { user } = await renderAt('/dashboard?tab=status&status.year=2025&status.quarter=2&forecast.year=2026&forecast.quarter=1%2C3&forecast.vendor=' + seedVendorId('Okta'))
    await waitForOptions()

    // then: Status 탭은 2025·Q2·Vendor 전체다
    expect(screen.getByLabelText('연도')).toHaveValue('2025')
    expect(pressed()).toEqual([2])
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')

    // when: Forecast 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    // then: Forecast 탭은 2026·Q1,Q3·Okta다
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([1, 3])
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta'))
  })

  // 테스트 코드: DSH-029
  it('처음 바꿀 때 tab과 두 연도를 쓰고 빈 값은 쓰지 않는다', async () => {
    // given: 조건 없는 /dashboard
    const { user, location } = await renderAt('/dashboard')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q2를 누른다
    await user.click(button(2))

    // then: 주소는 tab, 두 탭 연도, status 분기뿐이다
    await waitFor(() => expect(location()).toBe('/dashboard?tab=status&status.year=2026&status.quarter=2&forecast.year=2026'))
  })

  // 테스트 코드: DSH-029
  it('탭을 바꾸면 두 탭의 조건과 새 tab을 쓴다', async () => {
    // given: Status 탭 Q2·담당자 조건
    const { user, location } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=2&status.owner=' + USER_ID.kim)
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Forecast 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    // then: 주소가 tab=forecast와 두 탭의 조건을 고정 순서로 가진다
    await waitFor(() => expect(location()).toBe(`/dashboard?tab=forecast&status.year=2026&status.quarter=2&status.owner=${USER_ID.kim}&forecast.year=2026`))
  })

  // 테스트 코드: DSH-027
  it('조건 없는 주소(메뉴 진입)는 두 탭 모두 기본값이고 Status 탭이다', async () => {
    // given: 요약 조회를 지켜본다
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 조건 없이 /dashboard를 연다
    const { user } = await renderAt('/dashboard')

    // then: Status 탭에 올해·분기 없음이 보인다
    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([])

    // when: Forecast 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    // then: Forecast 탭도 올해·분기 없음이고 조회는 연도뿐이다
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
  })
})

describe('예전 공용 주소', () => {
  // 테스트 코드: DSH-030
  it('예전 주소는 담당자를 두 탭에, 분기를 Status 탭에만 쓰고 sq는 무시하며 새 주소에 예전 키를 쓰지 않는다', async () => {
    // when: 예전 키(year·quarter·owner·sq)로 Forecast 탭을 연다
    const { user, location } = await renderAt(`/dashboard?tab=forecast&year=2025&quarter=2&owner=${USER_ID.kim}&sq=3`)
    await waitForOptions()

    // then: Forecast 탭은 연도·담당자를 쓰고 분기는 쓰지 않는다
    expect(screen.getByLabelText('연도')).toHaveValue('2025')
    expect(pressed()).toEqual([])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')

    // when: Status 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Status' }))
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })

    // then: Status 탭은 연도·분기 Q2·담당자를 쓰고 주소에는 접두사 키만 쓰인다
    expect(screen.getByLabelText('연도')).toHaveValue('2025')
    expect(pressed()).toEqual([2])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
    const keys = [...new URLSearchParams(location().split('?')[1]).keys()]
    expect(keys).not.toContain('year')
    expect(keys).not.toContain('quarter')
    expect(keys).not.toContain('owner')
    expect(keys).not.toContain('sq')
    expect(keys).toEqual(expect.arrayContaining(['tab', 'status.year', 'status.quarter', 'status.owner', 'forecast.year', 'forecast.owner']))
  })

  // 테스트 코드: DSH-030
  it('주소를 여는 것만으로는 주소를 다시 쓰지 않는다', async () => {
    // given: 예전 키가 섞인 주소
    const start = '/dashboard?tab=forecast&year=2025&quarter=2&owner=7&sq=3'

    // when: 그 주소를 연다
    const { location } = await renderAt(start)
    await screen.findByRole('group', { name: 'Quarter' })

    // then: 주소가 그대로다
    expect(location()).toBe(start)
  })
})

describe('조회는 활성 탭 조건만 쓴다', () => {
  // 테스트 코드: DSH-037
  it('활성 탭으로 한 번 요청하고 다른 탭이 같은 조건이면 다시 요청하지 않는다', async () => {
    // given: 조건 없이 열어 첫 응답을 받은 화면
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })
    const calls = summary.mock.calls.length

    // when: 같은 조건의 Forecast 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    // then: 처음 한 번만 요청했고 더 늘지 않았다(요청 여부가 결과인 케이스: 화면은 정상 표시)
    expect(calls).toBe(1)
    expect(summary.mock.calls.length).toBe(calls)
  })

  // 테스트 코드: DSH-037
  it('다른 탭으로 가면 그 탭의 조건으로만 요청한다', async () => {
    // given: Status 탭에서 Q2를 고른 화면
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await screen.findByRole('group', { name: 'Quarter' })
    await user.click(button(2))
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
    summary.mockClear()

    // when: Forecast 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    // then: Forecast 조건(연도만)으로만 요청하고 Status 분기는 다시 보내지 않는다
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
    expect(summary.mock.calls.every(([query]) => query.quarters === undefined)).toBe(true)
  })

  // 테스트 코드: DSH-037
  it('이미 읽은 조건의 탭으로 돌아오면 캐시를 쓴다', async () => {
    // given: 두 탭의 조건이 다르고 Forecast 탭까지 읽은 화면
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=2&forecast.year=2026')
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))

    // when: Status 탭으로 돌아온다
    await user.click(screen.getByRole('tab', { name: 'Status' }))

    // then: 이미 받은 결과를 로딩 표시 없이 바로 보인다(백그라운드 재조회는 허용)
    expect(screen.getByRole('heading', { name: /전체 Status Pipeline/ })).toBeInTheDocument()
    expect(screen.queryByText(/불러오는 중|로딩/)).not.toBeInTheDocument()
    expect(pressed()).toEqual([2])
  })
})

describe('Drill-down과 Vendor 판정은 활성 탭 조건을 쓴다', () => {
  // 테스트 코드: DSH-048
  it('Forecast 탭의 링크는 Status 탭에 다른 조건이 있어도 자기 조건을 쓴다', async () => {
    // when: Status 탭에 2025·Q2·담당자, Forecast 탭에 2026이 있는 주소로 Forecast 탭을 연다
    await renderAt(`/dashboard?tab=forecast&status.year=2025&status.quarter=2&status.owner=${USER_ID.kim}&forecast.year=2026`)
    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    // then: Open 합계 링크는 Forecast 탭 조건(2026)만 담는다
    expect(tile).toHaveAttribute('href', `/deals?year=2026&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-048
  it('Status 탭의 링크는 Forecast 탭에 다른 조건이 있어도 자기 조건을 쓴다', async () => {
    // when: Status 탭에 2025·Q2·담당자, Forecast 탭에 2026·Q4가 있는 주소로 Status 탭을 연다
    await renderAt(`/dashboard?tab=status&status.year=2025&status.quarter=2&status.owner=${USER_ID.kim}&forecast.year=2026&forecast.quarter=4`)
    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    // then: Open 합계 링크는 Status 탭 조건만 담는다
    expect(tile).toHaveAttribute('href', `/deals?year=2025&quarter=2&owner=${USER_ID.kim}&forecast=${OPEN_PARAM}`)
  })

  // 테스트 코드: DSH-036
  it('목록에 없는 Vendor는 활성 탭 것만 전체로 보고 조회에서 뺀다', async () => {
    // given: Status 탭엔 등록된 Okta, Forecast 탭엔 없는 Vendor id가 있는 주소
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: Forecast 탭을 열고 Vendor 목록이 읽히기를 기다린다
    await renderAt(`/dashboard?tab=forecast&status.vendor=${seedVendorId('Okta')}&forecast.vendor=999999999`)
    await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })

    // then: Forecast 탭의 Vendor는 전체로 보이고 조회에 Vendor가 없다
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체'))
    await waitFor(() => expect(lastQuery(summary).vendorId).toBeUndefined())
  })
})
