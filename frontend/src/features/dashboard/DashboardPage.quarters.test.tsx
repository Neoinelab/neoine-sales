import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { lastQuery, NOW } from './testHelpers'

/**
 * Dashboard Quarter 토글(Quarter 다중 선택): 두 탭 모두 연도 select 바로 다음에 Q1~Q4 토글 묶음이 있고,
 * 누를 때마다 켜고 꺼지며 활성 탭의 URL 키(`<탭>.quarter`)와 조회가 바뀐다. 넷 다 누르면 누른 채 보이지만 조회·Drill-down은 전체와 같다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)
const group = () => screen.getByRole('group', { name: 'Quarter' })
const button = (n: number) => within(group()).getByRole('button', { name: `Q${n}` })
const pressed = () => [1, 2, 3, 4].filter((n) => button(n).getAttribute('aria-pressed') === 'true')

describe('Quarter 토글의 위치', () => {
  // 테스트 코드: DSH-032
  it.each(['status', 'forecast'])('%s 탭에서 Quarter 묶음이 연도 칸 바로 다음, 담당자 칸 앞에 있다', async (tab) => {
    // when: 탭을 연다
    await renderAt(`/dashboard?tab=${tab}`)

    // then: Quarter 묶음이 연도 뒤·담당자 앞이고 버튼은 Q1~Q4다
    const form = within(await screen.findByRole('tabpanel')).getByRole('form', { name: 'Dashboard 필터' })
    const year = within(form).getByLabelText('연도')
    const owner = within(form).getByLabelText('담당자')

    expect(follows(year, group())).toBe(true)
    expect(follows(group(), owner)).toBe(true)
    expect(within(group()).getAllByRole('button').map((b) => b.textContent)).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  // 테스트 코드: DSH-032
  it.each(['status', 'forecast'])('%s 탭에 Quarter 선택 상자(combobox)가 없다', async (tab) => {
    // when: 탭을 연다
    await renderAt(`/dashboard?tab=${tab}`)
    await screen.findByRole('group', { name: 'Quarter' })

    // then: Quarter 선택 상자가 없다
    expect(screen.queryByRole('combobox', { name: 'Quarter' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Quarter', { selector: 'select' })).not.toBeInTheDocument()
  })

  // 테스트 코드: DSH-027
  it('기본으로는 아무 분기도 눌려 있지 않다', async () => {
    // when: 조건 없이 /dashboard를 연다
    await renderAt('/dashboard')
    await screen.findByRole('group', { name: 'Quarter' })

    // then: 눌린 버튼이 없다
    expect(pressed()).toEqual([])
  })
})

describe('토글 동작', () => {
  // 테스트 코드: DSH-034
  it('활성 탭의 분기만 켜고 끄며 URL과 조회가 따라 바뀐다', async () => {
    // given: Status 탭
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q1, Q3를 누른다
    await user.click(button(1))
    await user.click(button(3))

    // then: URL과 조회에 분기 1,3이 있고 Forecast 분기 키는 없다
    await waitFor(() => expect(location()).toContain('status.quarter=1%2C3'))
    expect(pressed()).toEqual([1, 3])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [1, 3] }))
    expect(location()).not.toContain('forecast.quarter')

    // when: Q1을 다시 눌러 끈다
    await user.click(button(1))

    // then: 분기 3만 남는다
    await waitFor(() => expect(location()).toContain('status.quarter=3'))
    expect(location()).not.toContain('status.quarter=1')
    expect(pressed()).toEqual([3])

    // when: Q3도 끈다
    await user.click(button(3))

    // then: 분기 키가 사라지고 조회는 연도뿐이다
    await waitFor(() => expect(location()).not.toContain('status.quarter'))
    expect(pressed()).toEqual([])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
  })

  // 테스트 코드: DSH-034
  it('누른 순서와 무관하게 분기를 오름차순으로 쓴다', async () => {
    // given: Status 탭
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q4, Q2 순서로 누른다
    await user.click(button(4))
    await user.click(button(2))

    // then: URL에는 2,4 순서로 쓰인다
    await waitFor(() => expect(location()).toContain('status.quarter=2%2C4'))
  })

  // 테스트 코드: DSH-034
  it('Forecast 탭에서도 자기 키로 똑같이 동작한다', async () => {
    // given: Forecast 탭
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=forecast')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q2를 누른다
    await user.click(button(2))

    // then: forecast.quarter만 바뀌고 조회에 분기 [2]가 간다
    await waitFor(() => expect(location()).toContain('forecast.quarter=2'))
    expect(location()).not.toContain('status.quarter')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
  })

  // 테스트 코드: DSH-034
  it('누른 분기는 aria-pressed로 표시하고 나머지는 누르지 않은 채 둔다', async () => {
    // given: Status 탭
    const { user } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q2를 누른다
    await user.click(button(2))

    // then: Q2만 aria-pressed=true다
    await waitFor(() => expect(button(2)).toHaveAttribute('aria-pressed', 'true'))
    for (const n of [1, 3, 4]) expect(button(n)).toHaveAttribute('aria-pressed', 'false')
  })

  // 테스트 코드: DSH-029
  it('주소의 분기를 눌린 버튼으로 읽는다', async () => {
    // when: 분기 4,1이 적힌 주소를 연다
    await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=4%2C1')
    await screen.findByRole('group', { name: 'Quarter' })

    // then: Q1·Q4가 눌려 있다
    expect(pressed()).toEqual([1, 4])
  })

  // 테스트 코드: DSH-031
  it('주소의 형식이 틀린 분기 항목은 버린다', async () => {
    // given: 요약 조회를 지켜본다
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 분기 5,x,2가 적힌 주소를 연다
    await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=5%2Cx%2C2')
    await screen.findByRole('group', { name: 'Quarter' })

    // then: 올바른 Q2만 눌리고 조회에도 [2]만 간다
    expect(pressed()).toEqual([2])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
  })
})

describe('넷 다 누르면 전체와 같다', () => {
  // 테스트 코드: DSH-035
  it('넷 다 눌린 상태와 URL은 남지만 조회와 링크에는 분기가 없다', async () => {
    // given: Status 탭
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q1~Q4를 모두 누른다
    for (const n of [1, 2, 3, 4]) await user.click(button(n))

    // then: URL은 1,2,3,4이고 네 버튼이 눌려 있으며 조회·링크에는 분기가 없다
    await waitFor(() => expect(location()).toContain('status.quarter=1%2C2%2C3%2C4'))
    expect(pressed()).toEqual([1, 2, 3, 4])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
    const tile = await screen.findByRole('link', { name: /Pipeline/ })
    expect(tile.getAttribute('href')).not.toContain('quarter')
  })

  // 테스트 코드: DSH-035
  it('넷 다 누른 숫자는 분기 없는 조회와 같다', async () => {
    // given: Status 탭과 분기 없는 조회의 기준 값
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })
    const none = await gateway.dashboard.summary({ year: 2026 })

    // when: Q1~Q4를 모두 누른다
    for (const n of [1, 2, 3, 4]) await user.click(button(n))

    // then: 조회는 연도뿐이고 Open 합계 타일 건수가 기준 값과 같다
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
    const tile = await screen.findByRole('link', { name: /Open 합계/ })
    expect(tile).toHaveTextContent(`${none.forecast.openTotal.count}건`)
  })

  // 테스트 코드: DSH-035
  it('넷 중 하나를 끄면 나머지 셋으로 조회한다', async () => {
    // given: 넷 다 눌린 Status 탭
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=1%2C2%2C3%2C4')
    await screen.findByRole('group', { name: 'Quarter' })

    // when: Q4를 끈다
    await user.click(button(4))

    // then: 조회에 Q1~Q3가 가고 세 버튼이 눌려 있다
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [1, 2, 3] }))
    expect(pressed()).toEqual([1, 2, 3])
  })
})

describe('sq는 무시한다', () => {
  // 테스트 코드: DSH-030
  it('sq가 있어도 Selected Quarter를 보이지 않고 다음 주소에 sq를 쓰지 않는다', async () => {
    // when: 예전 sq가 붙은 Forecast 탭 주소를 연다
    const { user, location } = await renderAt('/dashboard?tab=forecast&forecast.year=2026&sq=3')
    await screen.findByRole('group', { name: 'Quarter' })

    // then: Selected Quarter 영역이 없다
    expect(screen.queryByText(/Selected Quarter/)).not.toBeInTheDocument()

    // when: Q1을 누른다
    await user.click(button(1))

    // then: forecast.quarter=1만 쓰이고 sq는 쓰이지 않는다
    await waitFor(() => expect(location()).toContain('forecast.quarter=1'))
    expect(location()).not.toContain('sq=')
    expect(pressed()).toEqual([1])
  })
})

describe('Status 탭 주의 필요 Deal은 분기와 무관하다', () => {
  // 테스트 코드: DSH-044
  it('분기를 눌러도 기한초과·미업데이트 타일의 숫자와 링크가 같다', async () => {
    // given: Status 탭의 주의 필요 Deal 타일
    const { user } = await renderAt('/dashboard?tab=status')
    const overdue = await screen.findByRole('link', { name: /기한초과/ })
    const before = { text: overdue.textContent, href: overdue.getAttribute('href') }
    const stale = screen.getByRole('link', { name: /미업데이트/ })
    const staleBefore = { text: stale.textContent, href: stale.getAttribute('href') }

    // when: Q1, Q3를 누른다
    await user.click(button(1))
    await user.click(button(3))

    // then: 두 타일의 글자와 링크 주소가 그대로다
    await waitFor(() => expect(pressed()).toEqual([1, 3]))
    const after = await screen.findByRole('link', { name: /기한초과/ })
    expect({ text: after.textContent, href: after.getAttribute('href') }).toEqual(before)
    const staleAfter = screen.getByRole('link', { name: /미업데이트/ })
    expect({ text: staleAfter.textContent, href: staleAfter.getAttribute('href') }).toEqual(staleBefore)
  })
})
