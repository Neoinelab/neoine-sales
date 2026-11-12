import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { clearQuarter, dataRows, describedText, openQuarterPanel, quarterButton, toggleQuarter } from './testHelpers'

/**
 * 목록 Quarter 다중 선택(Quarter 다중 선택, U4~U6). 체크할 때마다 바로 조회하고 선택은 URL `quarter`
 * (오름차순·중복 제거·콤마 → `%2C`)가 정본이다. 기준일 2026-10-15(올해 2026).
 */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>
const monthNames = () => within(screen.getByLabelText('월')).getAllByRole('option').map((o) => o.textContent)
const quarterOfDate = (date: string) => Math.floor((Number(date.slice(5, 7)) - 1) / 3) + 1

describe('여러 Quarter 선택', () => {
  // 체크한 분기 중 하나의 Deal을 보이고 오름차순 목록을 URL에 쓴다
  // 테스트 코드: DL-076
  it('lists the deals of any checked quarter and puts the ascending list in the URL', async () => {
    // given: 시드 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    await toggleQuarter(user, 'Q3')
    // when: Quarter를 여러 개 체크한다
    await toggleQuarter(user, 'Q1')

    // then: URL quarter가 오름차순 콤마 목록이고 해당 Deal이 보인다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1%2C3'))
    expect(quarterButton('Q1, Q3')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [1, 3] }))
    const expected = await gateway.deals.list({ year: 2026, quarters: [1, 3], limit: 100 })
    expect(expected.total).toBeGreaterThan(0)
    for (const item of expected.items) expect([1, 3]).toContain(quarterOfDate(item.revenueDate))
    await waitFor(() => expect(dataRows()).toHaveLength(Math.min(expected.total, 20)))
    expect(await screen.findByText(`총 ${expected.total}건`)).toBeVisible()
  })

  // 하나만 체크하면 단일 값으로 쓴다
  // 테스트 코드: DL-076
  it('writes one quarter as a plain value', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    // when: Quarter 하나를 체크한다
    await toggleQuarter(user, 'Q2')

    // then: URL quarter가 그 값 하나다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=2'))
    expect(quarterButton('Q2')).toBeInTheDocument()
  })

  // 하나를 해제해도 나머지는 남는다
  // 테스트 코드: DL-076
  it('removes a quarter again and keeps the others', async () => {
    // given: 두 분기를 체크한 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3')
    await screen.findByRole('button', { name: 'Quarter Q1, Q3' })

    // when: 하나를 해제한다
    await toggleQuarter(user, 'Q1')

    // then: 나머지만 URL에 남는다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3'))
  })

  // 선택이 바뀌면 1페이지로 돌아간다
  // 테스트 코드: DL-068
  it('goes back to page 1 when the selection changes', async () => {
    // given: 2페이지를 보던 목록
    const { user, location } = await renderAt('/deals?year=all&sort=revenueAmount&order=desc&page=2')
    await screen.findByRole('button', { name: '이전' })

    // when: Quarter를 체크한다
    await toggleQuarter(user, 'Q4')

    // then: page 키가 사라진다
    await waitFor(() => expect(location()).toBe('/deals?year=all&sort=revenueAmount&order=desc&quarter=4'))
  })

  // Q1~Q4 체크박스와 전체 버튼을 보인다
  // 테스트 코드: DL-076
  it('shows Q1 to Q4 as checkboxes of the Quarter group with the all button', async () => {
    // given: Quarter 묶음
    const { user } = await renderAt('/deals?year=2026&quarter=2')
    await screen.findByRole('search', { name: 'Deal 필터' })

    // when: 화면을 확인한다
    const panel = await openQuarterPanel(user)

    // then: Q1~Q4와 전체 버튼이 있다
    expect(panel.getAllByRole('checkbox').map((c) => c.closest('label')?.textContent)).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    expect(panel.getByRole('checkbox', { name: 'Q2' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Q1' })).not.toBeChecked()
    expect(panel.getByRole('button', { name: '전체' })).toBeVisible()
  })

  // 전체 버튼으로 모든 분기를 해제한다
  // 테스트 코드: DL-076
  it('clears every quarter with the all button', async () => {
    // given: 분기를 체크한 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3')
    await screen.findByRole('search', { name: 'Deal 필터' })

    // when: 전체를 누른다
    await clearQuarter(user)

    // then: quarter 키가 지워진다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(quarterButton('전체')).toBeInTheDocument()
  })

  // 예전 단일 분기 주소는 분기 하나로 연다
  // 테스트 코드: DL-076
  it('opens an old single-quarter address as that one quarter', async () => {
    // when: 그 주소를 연다 (전제: quarter=3 주소)
    await renderAt('/deals?year=2026&quarter=4')

    // then: Q3만 체크돼 있다
    expect(await screen.findByRole('button', { name: 'Quarter Q4' })).toBeVisible()
  })

  // 형식이 틀린 분기 항목은 버린다
  // 테스트 코드: DL-076
  it('drops quarter items in the wrong format from the address', async () => {
    // given: 틀린 항목이 섞인 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=9%2C2%2Cx')
    // when: 그 주소를 연다
    await screen.findByRole('button', { name: 'Quarter Q2' })

    // then: 올바른 분기만 남는다
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [2] }))
  })
})

describe('Quarter에 따른 월 선택지', () => {
  // 월 선택지는 고른 분기들의 월이다
  // 테스트 코드: DL-078
  it('offers the months of the chosen quarters', async () => {
    // given: 분기를 고른 목록
    await renderAt('/deals?year=2026&quarter=1%2C3')
    // when: 월 선택지를 본다
    await screen.findByLabelText('월')

    // then: 고른 분기의 월 합집합이다
    expect(monthNames()).toEqual(['전체', '1월', '2월', '3월', '7월', '8월', '9월'])
  })

  // 새 분기에 있으면 월을 유지하고 없으면 지운다
  // 테스트 코드: DL-079
  it('keeps the month while the new quarters contain it and clears it when they do not', async () => {
    // given: 월이 걸린 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3&month=8')
    // when: 분기를 바꾼다
    await screen.findByLabelText('월')
    // then: 월이 유지되거나 지워진다
    expect(screen.getByLabelText('월')).toHaveDisplayValue('8월')

    await toggleQuarter(user, 'Q1') // Q3만 남는다: 8월 유지
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3&month=8'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('8월')

    await toggleQuarter(user, 'Q1') // Q1·Q3
    await toggleQuarter(user, 'Q3') // Q1만 남는다: 8월은 선택지에 없다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
  })

  // 전체로 분기를 해제하면 보이던 월은 유지한다
  // 테스트 코드: DL-079
  it('keeps the visible month when the all button clears the quarters', async () => {
    // given: 월이 보이는 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=1%2C3&month=8')
    await screen.findByLabelText('월')

    // when: 분기 전체 버튼을 누른다
    await clearQuarter(user)

    // then: 월이 유지된다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&month=8'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('8월')
  })

  // 월이 고른 분기에 속하면 월만 보낸다
  // 테스트 코드: DL-078
  it('sends only the month when it belongs to one of the chosen quarters', async () => {
    // given: 분기와 그 안의 월이 있는 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=1%2C3&month=8')
    // when: 그 주소를 연다
    await screen.findByText(/총 \d+건/)

    // then: 조회에 month만 실린다
    expect(lastQuery(list)).toMatchObject({ year: 2026, month: 8 })
    expect(lastQuery(list)).not.toHaveProperty('quarters')
  })

  // 월이 분기에 없으면 분기만 보낸다
  // 테스트 코드: DL-078
  it('sends the quarters when the month is not in them', async () => {
    // given: 분기와 그 밖의 월이 있는 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=1%2C3&month=5')
    // when: 그 주소를 연다
    await screen.findByText(/총 \d+건/)

    // then: 조회에 quarters만 실린다
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
    expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [1, 3] })
    expect(lastQuery(list)).not.toHaveProperty('month')
  })
})

describe('넷 다 체크하면 전체와 같다 (U6)', () => {
  // 넷 다 체크해도 유지하되 분기 조건은 보내지 않는다
  // 테스트 코드: DL-076
  it('shows 전체, keeps the four checked and in the URL, but sends no quarter', async () => {
    // given: 시드 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    // when: Q1~Q4를 모두 체크한다
    for (const name of ['Q1', 'Q2', 'Q3', 'Q4']) await toggleQuarter(user, name)

    // then: 요약은 전체, URL에는 넷 다 남고 조회에 quarter가 없다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1%2C2%2C3%2C4'))
    expect(quarterButton('전체')).toBeInTheDocument()
    const panel = await openQuarterPanel(user)
    for (const name of ['Q1', 'Q2', 'Q3', 'Q4']) expect(panel.getByRole('checkbox', { name })).toBeChecked()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026 }))
    expect(lastQuery(list)).not.toHaveProperty('quarters')
    expect(monthNames()).toHaveLength(13)
  })

  // 네 분기는 그 해 전체를 보인다
  // 테스트 코드: DL-076
  it('lists the whole year for the four quarters', async () => {
    // given: 네 분기가 체크된 목록
    await renderAt('/deals?year=2026&quarter=1%2C2%2C3%2C4')
    // when: 목록을 본다
    const all = await gateway.deals.list({ year: 2026, limit: 1 })

    // then: 그 해 전체 Deal 수가 보인다
    expect(await screen.findByText(`총 ${all.total}건`)).toBeVisible()
  })
})

describe('연도가 전체일 때 안내', () => {
  // 연도 전체에서 분기를 체크하면 올해 기준 안내를 보인다
  // 테스트 코드: DL-077
  it('tells that all years means this year once a quarter is checked', async () => {
    // given: 연도가 전체인 목록
    const { user } = await renderAt('/deals?year=all')
    // when: 분기를 체크한다
    await screen.findByRole('search', { name: 'Deal 필터' })
    // then: '연도가 전체이면 올해(YYYY) 기준입니다.'가 보인다
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()

    await toggleQuarter(user, 'Q2')

    expect(screen.getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(describedText(quarterButton('Q2'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')
  })
})
