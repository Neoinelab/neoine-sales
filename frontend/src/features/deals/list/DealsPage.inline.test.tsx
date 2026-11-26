import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AMOUNT_INPUT_MESSAGE } from '../../../shared/model/money'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

afterEach(() => vi.restoreAllMocks())

const SEARCH = '/deals?q=대한제조 MFA'

describe('Inline Update 즉시 저장 (T-LIST-12~14)', () => {
  // 편집 중에는 저장·취소 버튼이 없다
  // 테스트 코드: DL-093
  it('has no save or cancel button while editing', async () => {
    // given: sales의 목록
    const { user } = await renderAt(SEARCH)

    const row = await rowOf(/대한제조 MFA 확대/)
    for (const label of ['Forecast', '금액(단위:원)', 'Expected Close']) {
      // when: 칸을 눌러 편집을 연다
      await user.click(within(row).getByRole('button', { name: (name) => name.endsWith(`${label} 편집`) }))
      // then: 저장·취소 버튼이 없다
      expect(within(row).queryByRole('button', { name: '저장' })).not.toBeInTheDocument()
      expect(within(row).queryByRole('button', { name: '취소' })).not.toBeInTheDocument()
      // when: Esc를 눌러 닫는다
      await user.keyboard('{Escape}')
    }
  })

  // Forecast는 고르는 즉시 저장되고 알림이 뜬다
  // 테스트 코드: DL-093
  it('saves a Forecast change as soon as it is picked and tells it in a status message', async () => {
    // given: sales의 목록
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)

    // when: Forecast 편집에서 값을 고른다
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')

    // then: 저장되어 상태 알림이 보인다
    expect(await within(row).findByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Commit')
    expect(within(row).queryByLabelText('Forecast 값')).not.toBeInTheDocument()
    expect(await screen.findByText(/대한제조 MFA 확대: Forecast.*'Commit'.*변경되었습니다/)).toBeVisible()
  })

  // 바꾸지 않고 포커스가 나가면 원래 값으로 닫는다
  // 테스트 코드: DL-093
  it('leaves the old value when a select loses focus without a change', async () => {
    // given: Forecast 편집기
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)

    // when: 값을 바꾸지 않고 포커스를 옮긴다
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.tab()

    // then: 원래 값이 그대로다
    expect(within(row).queryByLabelText('Forecast 값')).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Most Likely')
  })

  // 금액은 Enter에 저장되고 원 단위로 보인다
  // 테스트 코드: DL-094
  it('saves the amount with Enter and shows it in won', async () => {
    // given: sales의 목록
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    const input = within(row).getByLabelText('금액(단위:원) 값')

    // when: 금액을 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '500000000{Enter}')

    // then: 저장되어 원 단위 콤마 값이 보인다
    expect(await within(row).findByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent('500,000,000')
    expect(await screen.findByText(/금액\(단위:원\)이 '500,000,000'\(으\)로 변경되었습니다\./)).toBeVisible()
  })

  // 금액은 포커스 이동에 저장되고 글자마다 저장하지 않는다
  // 테스트 코드: DL-094
  it('saves the amount when the input loses focus, not on every keystroke', async () => {
    // given: 금액 편집기
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    const input = within(row).getByLabelText('금액(단위:원) 값')

    // when: 값을 입력한다
    await user.clear(input)
    await user.type(input, '700000000')
    // then: 아직 저장되지 않고 편집이 열려 있다
    expect(within(row).getByLabelText('금액(단위:원) 값')).toBeVisible()
    expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()

    // when: 칸을 벗어난다
    await user.tab()
    // then: 벗어날 때 저장된다
    expect(await within(row).findByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent('700,000,000')
  })

  // Esc는 입력한 금액을 버린다
  // 테스트 코드: DL-094
  it('discards the typed amount with Esc', async () => {
    // given: 금액 편집기
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    const before = within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }).textContent
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    const input = within(row).getByLabelText('금액(단위:원) 값')

    // when: 값을 입력하고 Esc를 누른다
    await user.clear(input)
    await user.type(input, '900000000{Escape}')

    // then: 원래 금액이 그대로다
    expect(within(row).queryByLabelText('금액(단위:원) 값')).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent(before ?? '')
    expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
  })

  // 틀린 금액은 거절하고 편집을 유지하며 저장하지 않는다
  // 테스트 코드: DL-094
  it('rejects an invalid amount, keeps editing and does not save', async () => {
    // given: 금액 편집기
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    const input = within(row).getByLabelText('금액(단위:원) 값')

    // when: 틀린 값을 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '0{Enter}')

    // then: 오류 문구가 보이고 편집이 유지된다
    expect(await within(row).findByRole('alert')).toHaveTextContent(AMOUNT_INPUT_MESSAGE)
    expect(within(row).getByLabelText('금액(단위:원) 값')).toBeVisible()
    expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
  })

  // 금액을 그대로 두면 저장하지 않는다
  // 테스트 코드: DL-094
  it('does not save when the amount is left as shown', async () => {
    // given: 금액 편집기
    const { user } = await renderAt(SEARCH)
    const code = (await gateway.deals.list({ keyword: '대한제조 MFA', limit: 5 })).items[0]!.code
    const before = (await gateway.history.list(code, {})).length
    const row = await rowOf(/대한제조 MFA 확대/)
    const shown = within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }).textContent

    // when: 금액 편집을 연다
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    // then: 현재 금액으로 시작한다
    expect(within(row).getByLabelText<HTMLInputElement>('금액(단위:원) 값').value).toBe(shown)

    // when: 바꾸지 않고 Enter를 누른다
    await user.keyboard('{Enter}')
    // then: 요청이 나가지 않고 금액이 그대로다
    expect(within(row).queryByLabelText('금액(단위:원) 값')).not.toBeInTheDocument()
    expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
    expect((await gateway.history.list(code, {})).length).toBe(before)
  })

  // Expected Close는 날짜를 고르는 순간 저장된다
  // 테스트 코드: DL-095
  it('saves Expected Close as soon as a date is picked', async () => {
    // given: sales의 목록
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)

    // when: 날짜를 고른다
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    fireEvent.change(within(row).getByLabelText('Expected Close 값'), { target: { value: '2027-02-03' } })

    // then: 저장되어 새 날짜가 보인다
    expect(await within(row).findByRole('button', { name: /Expected Close 편집/ })).toHaveTextContent('2027-02-03')
  })

  // yyyymmdd를 다 치는 순간 저장된다
  // 테스트 코드: DL-095
  it('saves Expected Close typed as yyyymmdd once the date is complete', async () => {
    // given: Expected Close 편집기
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    const input = within(row).getByLabelText('Expected Close 값')

    // when: yyyymmdd를 끝까지 입력한다
    await user.clear(input)
    await user.type(input, '20270203')

    // then: 저장되어 새 날짜가 보인다
    expect(await within(row).findByRole('button', { name: /Expected Close 편집/ })).toHaveTextContent('2027-02-03')
  })

  // 덜 친 동안은 저장하지 않고 문구도 없다
  // 테스트 코드: DL-095
  it('does not save while the date is partly typed and shows no message before Enter', async () => {
    // given: Expected Close 편집기
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    const input = within(row).getByLabelText('Expected Close 값')

    // when: 날짜를 덜 입력한다
    await user.clear(input)
    await user.type(input, '2027.0')

    // then: 저장되지 않고 문구가 없다
    expect(update).not.toHaveBeenCalled()
    expect(within(row).queryByRole('alert')).not.toBeInTheDocument()
    expect(within(row).getByLabelText('Expected Close 값')).toBeVisible()
  })

  // 없는 날짜에 Enter면 문구를 보이고 편집을 유지한다
  // 테스트 코드: DL-095
  it('rejects a non-existing Expected Close on Enter and keeps editing', async () => {
    // given: Expected Close 편집기
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    const input = within(row).getByLabelText('Expected Close 값')

    // when: 없는 날짜로 Enter를 누른다
    await user.clear(input)
    await user.type(input, '20271301{Enter}')

    // then: 날짜 문구가 보이고 편집이 유지된다
    expect(await within(row).findByRole('alert')).toHaveTextContent('없는 날짜입니다.')
    expect(update).not.toHaveBeenCalled()
    expect(within(row).getByLabelText('Expected Close 값')).toBeVisible()
  })

  // 달력 버튼을 거쳐 포커스가 나가면 저장 없이 닫힌다
  // 테스트 코드: DL-095
  it('closes the Expected Close editor with Tab through the calendar button and out, keeping the old value', async () => {
    // given: Expected Close 편집기
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    const before = within(row).getByRole('button', { name: /Expected Close 편집/ }).textContent

    // when: Expected Close 편집을 열고 Tab을 누른다
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    await user.tab()
    // then: 달력 버튼에 포커스가 간다
    expect(within(row).getByRole('button', { name: /달력 열기/ })).toHaveFocus()

    // when: Tab으로 밖으로 나간다
    await user.tab()
    // then: 원래 값으로 닫힌다
    expect(within(row).queryByLabelText('Expected Close 값')).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /Expected Close 편집/ })).toHaveTextContent(before ?? '')
    expect(update).not.toHaveBeenCalled()
  })

  // 덜 친 채 밖으로 나가면 오류 없이 버리고 닫는다
  // 테스트 코드: DL-095
  it('closes a partly typed Expected Close editor without saving or an error when Tab leaves it', async () => {
    // given: 덜 친 편집기
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    const input = within(row).getByLabelText('Expected Close 값')

    // when: Tab으로 밖으로 나간다
    await user.clear(input)
    await user.type(input, '2027.0')
    await user.tab()
    await user.tab()

    // then: 저장·오류 없이 닫힌다
    expect(within(row).queryByLabelText('Expected Close 값')).not.toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })

  // 텍스트와 달력 버튼 사이 이동으로는 닫히지 않는다
  // 테스트 코드: DL-095
  it('does not close the editor when Tab only moves from the text to the calendar button', async () => {
    // given: Expected Close 편집기
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)

    // when: Tab으로 달력 버튼으로 간다
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    await user.tab()

    // then: 편집기가 열려 있다
    expect(within(row).getByLabelText('Expected Close 값')).toBeVisible()
  })

  // 빈 Expected Close는 문구를 보이고 편집을 유지한다
  // 테스트 코드: DL-095
  it('rejects an empty Expected Close and keeps editing', async () => {
    // given: Expected Close 편집기
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)

    // when: 값을 비우고 Enter를 누른다
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    fireEvent.change(within(row).getByLabelText('Expected Close 값'), { target: { value: '' } })

    // then: 'Expected Close를 입력하세요.'가 보이고 편집이 유지된다
    expect(await within(row).findByRole('alert')).toHaveTextContent('Expected Close를 입력하세요.')
    expect(within(row).getByLabelText('Expected Close 값')).toBeVisible()
  })

  // 테스트 코드: DL-093
  it('offers editing for Forecast, amount and Expected Close when there is no Next Action', async () => {
    // given: sales의 목록
    await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)

    // when: 편집 버튼을 센다
    const labels = within(row)
      .getAllByRole('button', { name: /편집/ })
      .map((b) => b.getAttribute('aria-label') ?? '')

    expect(labels).toEqual(['Forecast', '금액(단위:원)', 'Expected Close'].map((label) => `대한제조 MFA 확대 ${label} 편집`))
  })

  // user 역할에는 편집 버튼이 없다
  // 테스트 코드: DL-064
  it('gives a user role no edit buttons', async () => {
    // given: user 역할
    await renderAt(SEARCH, { role: 'user' })

    // when: 목록을 연다
    const row = await rowOf(/대한제조 MFA 확대/)

    // then: 편집 버튼이 없다
    expect(within(row).queryByRole('button', { name: /편집/ })).not.toBeInTheDocument()
  })
})

async function storedStatus(row: HTMLElement) {
  const href = within(row).getAllByRole('link')[0]?.getAttribute('href')
  if (!href) throw new Error('Deal 링크가 없습니다.')
  return (await gateway.deals.get(href.slice('/deals/'.length))).statusKey
}

describe('Forecast 편집에 따른 Status 동기화 (목록)', () => {
  it('asks for the actual revenue before closing a deal as 계약완료 and tells the co-changed value', async () => {
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Won')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    const amount = within(dialog).getByLabelText('매출금액(단위:원, 실제 값)')

    // when: 금액을 비운다
    await user.clear(amount)
    // then: 확정이 꺼진다
    expect(within(dialog).getByRole('button', { name: '확정' })).toBeDisabled()

    // when: 금액을 입력하고 확정한다
    await user.type(amount, '1800000000')
    expect(within(dialog).getByRole('button', { name: '확정' })).toBeEnabled()
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    // then: Won·계약완료·새 금액이 보이고 함께 바뀐 값을 알린다
    expect(await within(row).findByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Won')
    expect(await storedStatus(row)).toBe('contract_completed')
    expect(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent('1,800,000,000')
    expect(await screen.findByText(/함께 변경되었습니다/)).toBeVisible()
  })

  // 매출 대화상자를 취소하면 아무것도 바뀌지 않는다(DD)
  it('leaves everything unchanged when the revenue dialog is cancelled', async () => {
    // given: 매출 입력 창
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Won')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })

    // when: 취소한다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 값이 그대로다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Commit')
    expect(await storedStatus(row)).toBe('price_negotiation')
  })

  // Won Deal을 되돌리면 새 Status를 고르게 한다(DD)
  it('makes the user pick the new Status when a Won deal is reopened', async () => {
    // given: Won Deal
    const { user } = await renderAt('/deals?q=바른제약 PAM')
    const row = await rowOf(/바른제약 PAM/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))

    // when: Forecast를 Won이 아닌 값으로 바꾼다
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })

    // then: 새 Status 선택 창이 뜬다
    expect(within(dialog).getByRole('button', { name: '확인' })).toBeDisabled()
    expect(within(dialog).queryByRole('radio', { name: '계약완료' })).not.toBeInTheDocument()

    // when: 기술평가를 고르고 확인한 뒤 계약 처리 창에서 유지를 누른다
    await user.click(within(dialog).getByRole('radio', { name: '기술평가' }))
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    await user.click(within(await screen.findByRole('dialog', { name: '라이선스 계약 처리' })).getByRole('button', { name: '유지' }))
    // then: Status가 기술평가로 바뀌고 Forecast는 Commit이다
    expect(await within(row).findByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Commit')
    expect(await storedStatus(row)).toBe('technical_evaluation')
  })

  // 선택 창을 취소하면 원래 값이 남는다(DD)
  it('keeps the old values when the choice dialog is cancelled', async () => {
    // given: 선택 창
    const { user } = await renderAt('/deals?q=청명대학교 SSO')
    const row = await rowOf(/청명대학교 SSO\/MFA/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })

    // when: 취소한다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 값이 그대로다
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Won')
    expect(await storedStatus(row)).toBe('contract_completed')
  })
})
