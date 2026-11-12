import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { clearQuarter, dataRows, describedText, quarterButton, toggleQuarter } from './testHelpers'

/** Quarter와 월(2026-10-26 개편). 기준일 2026-10-15(올해 2026). */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('분기 안의 월만 선택', () => {
  // 고른 분기의 월만 월 선택지로 보인다
  // 테스트 코드: DL-078
  it('offers only the months of the chosen quarter', async () => {
    // given: 연도·분기가 걸린 목록
    await renderAt('/deals?year=2026&quarter=2')

    // when: 월 선택지를 본다
    await screen.findByLabelText('월')

    // then: 그 분기의 월만 있다
    expect(optionNames(screen.getByLabelText('월'))).toEqual(['전체', '4월', '5월', '6월'])
  })

  // 분기마다 그 분기의 월을 선택지로 보인다
  // 테스트 코드: DL-078
  it.each([
    [1, ['전체', '1월', '2월', '3월']],
    [3, ['전체', '7월', '8월', '9월']],
    [4, ['전체', '10월', '11월', '12월']],
  ])('offers the months of Q%i', async (quarter, names) => {
    // given: 분기별 주소
    await renderAt(`/deals?year=2026&quarter=${quarter}`)

    // when: 월 선택지를 본다
    await screen.findByLabelText('월')

    // then: 그 분기의 월 이름 목록이다
    expect(optionNames(screen.getByLabelText('월'))).toEqual(names)
  })

  // 분기가 전체이면 열두 달을 보인다
  // 테스트 코드: DL-078
  it('offers all twelve months when the quarter is set to all', async () => {
    // given: 분기를 전체로 한 목록
    const { user } = await renderAt('/deals?year=2026&quarter=2')
    await screen.findByLabelText('월')

    // when: 월 선택지를 본다
    await clearQuarter(user)

    // then: 12개월과 전체가 있다
    expect(optionNames(screen.getByLabelText('월'))).toEqual(['전체', ...Array.from({ length: 12 }, (_, i) => `${i + 1}월`)])
  })
})

describe('월을 골라도 분기는 유지', () => {
  // 월을 골라도 분기는 유지하고 월만 보내 그 달을 보인다
  // 테스트 코드: DL-078
  it('keeps the quarter, sends only the month and lists that month', async () => {
    // given: 분기가 걸린 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByText(/총 \d+건/)

    // when: 분기 안의 월을 고른다
    await user.selectOptions(screen.getByLabelText('월'), '11월')

    // then: 분기는 유지되고 조회에 month만 실려 그 달 Deal이 보인다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=4&month=11'))
    expect(quarterButton('Q4')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ year: 2026, month: 11 }))
    expect(lastQuery(list)).not.toHaveProperty('quarters')

    const expected = await gateway.deals.list({ year: 2026, month: 11, limit: 100 })
    const quarter = await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })
    expect(expected.total).toBeGreaterThan(0)
    expect(expected.total).toBeLessThan(quarter.total)
    for (const item of expected.items) expect(item.revenueDate.startsWith('2026-11')).toBe(true)
    await waitFor(() => expect(dataRows()).toHaveLength(expected.total))
  })
})

describe('분기에 속하지 않는 월', () => {
  // 분기에 속하지 않는 월이면 분기만 조회한다
  // 테스트 코드: DL-078
  it('shows all months and queries the quarter only', async () => {
    // given: 분기 밖 월이 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=2026&quarter=4&month=3')

    // when: 그 주소를 연다
    await screen.findByText(/총 \d+건/)

    // then: 월 칸은 전체로 보이고 분기만 조회한다
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
    expect(lastQuery(list)).toMatchObject({ year: 2026, quarters: [4] })
    expect(lastQuery(list)).not.toHaveProperty('month')
  })

  // 분기에 속한 월이면 그 월이 보인다
  // 테스트 코드: DL-078
  it('shows the month that belongs to the quarter', async () => {
    // given: 분기 안 월이 든 주소
    await renderAt('/deals?year=2026&quarter=4&month=11')

    // when: 그 주소를 연다
    await screen.findByLabelText('월')

    // then: 월 칸이 그 월이다
    expect(screen.getByLabelText('월')).toHaveDisplayValue('11월')
  })
})

describe('분기를 바꿀 때 월 (Quarter 다중 선택)', () => {
  // 체크한 분기 집합에 월이 있으면 유지하고 없으면 지운다
  // 테스트 코드: DL-079
  it('keeps the month while a checked quarter set still contains it, and clears it once it does not', async () => {
    // given: 월이 걸린 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=4&month=11')
    await screen.findByLabelText('월')

    // when: 분기를 바꾼다
    await toggleQuarter(user, 'Q3') // Q3·Q4 → 7~12월에 11월이 있다

    // then: 월이 유지되다가 없어지면 지워진다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3%2C4&month=11'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('11월')

    await toggleQuarter(user, 'Q4') // Q3만 → 11월은 선택지에 없다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=3'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
  })

  // 전체 버튼으로 분기를 풀어도 보이던 월은 유지한다
  // 테스트 코드: DL-079
  it('keeps the visible month when the quarters are cleared with the all button', async () => {
    // given: 월이 보이는 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=4&month=11')
    await screen.findByLabelText('월')

    // when: 분기 전체를 누른다
    await clearQuarter(user)

    // then: 월이 유지된다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&month=11'))
    expect(screen.getByLabelText('월')).toHaveDisplayValue('11월')
  })

  // 분기 때문에 숨은 월은 분기를 풀 때 지운다
  // 테스트 코드: DL-079
  it('drops a month hidden by the quarter when the quarters are cleared', async () => {
    // given: 분기에 가려 숨은 월이 있는 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=4&month=3')
    await screen.findByLabelText('월')

    // when: 분기를 푼다
    await clearQuarter(user)

    // then: 숨은 월이 지워진다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })
})

describe('연도가 전체일 때 안내', () => {
  // 연도 전체이면 올해 기준 안내를 보이고 연도를 고르면 숨긴다
  // 테스트 코드: DL-077
  it('tells that all years means this year and hides it when a year is chosen', async () => {
    // given: 연도 전체에서 월을 고른 목록
    const { user } = await renderAt('/deals?year=all&quarter=1')

    await screen.findByLabelText('Quarter')
    expect(describedText(quarterButton('Q1'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')
    expect(screen.getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(screen.queryByText(/연도를 고르지 않으면/)).not.toBeInTheDocument()

    // when: 연도를 고른다
    await user.selectOptions(screen.getByLabelText('연도'), '2027')

    // then: 안내가 사라진다
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })

  // 분기 없이 월만 고르면 월 아래에 안내를 보인다
  // 테스트 코드: DL-077
  it('shows the hint under the month when there is no quarter', async () => {
    // given: 연도 전체에서 월만 고른 목록
    await renderAt('/deals?year=all&month=3')
    await screen.findByLabelText('월')

    // when: 화면을 확인한다
    const label = screen.getByLabelText('월').closest('label') as HTMLElement

    // then: 월 아래에 안내가 있다
    expect(within(label).getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(screen.getAllByText(/연도가 전체이면/)).toHaveLength(1)
  })

  // 연도만 전체이고 분기·월이 없으면 안내가 없다
  // 테스트 코드: DL-077
  it('shows no hint when only the year is all', async () => {
    // given: 연도 전체만 걸린 목록
    await renderAt('/deals?year=all')

    // when: 화면을 확인한다
    await screen.findByLabelText('월')

    // then: 안내가 없다
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })
})
