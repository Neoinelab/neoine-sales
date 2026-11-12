import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AMOUNT_INPUT_MESSAGE, AMOUNT_TOO_LARGE_MESSAGE } from '../../../shared/model/money'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

async function openBar(no: number, title: string, role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(no), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  return { ...view, bar: screen.getByRole('region', { name: 'Deal 정보' }) }
}

/** Status/Forecast 값을 클릭 → 선택(고르는 순간 반영). 동기화 팝업은 호출한 테스트가 이어서 다룬다. */
async function pick(user: UserEvent, bar: HTMLElement, field: 'Status' | 'Forecast', option: string) {
  await user.click(within(bar).getByRole('button', { name: `${field} 수정` }))
  await user.selectOptions(within(bar).getByLabelText(field), option)
}

const shown = (bar: HTMLElement, field: 'Status' | 'Forecast') => within(bar).getByRole('button', { name: `${field} 수정` })

describe('상세 현재값 바 인라인 변경 (T-SYNC-UI 상세)', () => {
  // 동기화가 필요 없는 Forecast 변경은 바로 저장되고 알림이 보인다.
  // 테스트 코드: DD-097
  it('changes the forecast right away when no sync is needed and tells the user', async () => {
    // given: 대한제조 MFA 확대 Deal
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')

    // when: Forecast를 Commit으로 고른다
    await pick(user, bar, 'Forecast', 'Commit')

    // then: 대화상자 없이 Forecast가 Commit이 되고 "Forecast가 'Commit'(으)로 변경되었습니다."가 보인다
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Commit'))
    expect(await screen.findByText("Forecast가 'Commit'(으)로 변경되었습니다.")).toBeVisible()
  })

  // 계약완료로 바꾸면 매출 확정을 묻고 확정하면 Forecast도 Won이 된다.
  // 테스트 코드: DD-098
  it('asks for the revenue before moving to 계약완료 and then changes forecast to Won too', async () => {
    // given: 가격협상·Commit Deal
    const { user, bar } = await openBar(1, '한빛은행 ITDR 도입')

    // when: Status를 계약완료로 고르고 금액을 비운다
    await pick(user, bar, 'Status', '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    const confirm = within(dialog).getByRole('button', { name: '확정' })
    await user.clear(within(dialog).getByLabelText('매출금액(단위:원, 실제 값)'))

    // then: 확정이 꺼진다
    expect(confirm).toBeDisabled()

    // when: 금액·매출일을 넣어 확정한다
    await user.type(within(dialog).getByLabelText('매출금액(단위:원, 실제 값)'), '1800000000')
    await user.clear(within(dialog).getByLabelText('매출일(실제 값)'))
    await user.type(within(dialog).getByLabelText('매출일(실제 값)'), '2026-11-30')
    await user.click(confirm)

    // then: 계약완료·Won, 새 금액, '함께 변경' 알림이 보인다
    await waitFor(() => expect(shown(bar, 'Status')).toHaveTextContent('계약완료'))
    expect(shown(bar, 'Forecast')).toHaveTextContent('Won')
    expect(await screen.findByText(/함께 변경되었습니다/)).toBeVisible()
    expect(within(bar).getByText('1,800,000,000')).toBeVisible()
  })

  // 매출 확정 대화상자를 취소하면 값이 그대로다.
  // 테스트 코드: DD-099
  it('keeps the old values when the revenue dialog is cancelled', async () => {
    // given: 가격협상·Commit Deal
    const { user, bar } = await openBar(1, '한빛은행 ITDR 도입')
    await pick(user, bar, 'Status', '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })

    // when: '취소'를 누른다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 대화상자가 닫히고 Status·Forecast가 그대로다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(shown(bar, 'Status')).toHaveTextContent('가격협상')
    expect(shown(bar, 'Forecast')).toHaveTextContent('Commit')
  })

  // Won에서 벗어나면 계약완료를 뺀 Status를 기본값 없이 묻는다.
  // 테스트 코드: DD-100
  it('asks which status to use when a won deal leaves Won, with no default and 계약완료 excluded', async () => {
    // given: 계약완료·Won Deal
    const { user, bar } = await openBar(12, '바른제약 PAM')

    // when: Forecast를 Commit으로 고른다
    await pick(user, bar, 'Forecast', 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    const confirm = within(dialog).getByRole('button', { name: '확인' })

    // then: '확인'이 꺼진 선택 대화상자에 계약완료 선택지가 없다
    expect(confirm).toBeDisabled()
    expect(within(dialog).queryByRole('radio', { name: '계약완료' })).not.toBeInTheDocument()

    // when: 기술평가를 고르고 확인한 뒤 계약 처리 창에서 유지를 누른다
    await user.click(within(dialog).getByRole('radio', { name: '기술평가' }))
    await user.click(confirm)
    await user.click(within(await screen.findByRole('dialog', { name: '라이선스 계약 처리' })).getByRole('button', { name: '유지' }))

    // then: Status가 기술평가로 바뀐다
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Commit'))
    expect(shown(bar, 'Status')).toHaveTextContent('기술평가')
  })

  // 계약완료에서 이전 단계로 가면 Won을 뺀 Forecast를 묻는다.
  // 테스트 코드: DD-101
  it('asks which forecast to use when a contract-completed deal goes back to an earlier status', async () => {
    // given: 계약완료·Won Deal
    const { user, bar } = await openBar(12, '바른제약 PAM')

    // when: Status를 기술평가로 고른다
    await pick(user, bar, 'Status', '기술평가')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })

    // then: '확인'이 꺼진 선택 대화상자가 나온다
    expect(within(dialog).getByRole('button', { name: '확인' })).toBeDisabled()

    // when: Best를 고르고 확인한 뒤 계약 처리 창에서 유지를 누른다
    await user.click(within(dialog).getByRole('radio', { name: 'Best' }))
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    await user.click(within(await screen.findByRole('dialog', { name: '라이선스 계약 처리' })).getByRole('button', { name: '유지' }))

    // then: Status·Forecast가 함께 바뀐다
    await waitFor(() => expect(shown(bar, 'Status')).toHaveTextContent('기술평가'))
    expect(shown(bar, 'Forecast')).toHaveTextContent('Best')
  })

  // Lost를 되살리면 현재 Status를 기본으로 묻는다.
  // 테스트 코드: DD-102
  it('asks for a status when reviving a lost deal, defaulting to the current status', async () => {
    // given: 가격협상·Lost Deal
    const { user, bar } = await openBar(16, '새론병원 SSO')

    // when: Forecast를 Best로 고른다
    await pick(user, bar, 'Forecast', 'Best')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })

    // then: 선택 대화상자에서 현재 Status(가격협상)가 선택돼 있다
    expect(within(dialog).getByRole('radio', { name: '가격협상' })).toBeChecked()

    // when: 확인을 누른다
    await user.click(within(dialog).getByRole('button', { name: '확인' }))

    // then: Forecast가 Best가 된다
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Best'))
  })

  // Status 편집을 Esc나 포커스 이동으로 닫으면 아무것도 묻거나 바꾸지 않는다.
  // 테스트 코드: DD-103
  it('closes the status editor with Escape or by leaving it, without changing anything or asking', async () => {
    // given: 가격협상 Deal
    const { user, bar } = await openBar(1, '한빛은행 ITDR 도입')

    // when: Status 편집을 열어 Esc로 닫는다
    await user.click(within(bar).getByRole('button', { name: 'Status 수정' }))
    await user.keyboard('{Escape}')
    // then: 편집 칸이 닫힌다
    expect(within(bar).queryByLabelText('Status')).not.toBeInTheDocument()

    // when: 다시 열어 Tab으로 나간다
    await user.click(within(bar).getByRole('button', { name: 'Status 수정' }))
    await user.tab()
    // then: 편집 칸이 닫히고 대화상자가 없으며 Status가 그대로다
    expect(within(bar).queryByLabelText('Status')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(shown(bar, 'Status')).toHaveTextContent('가격협상')
  })
})

describe('금액·Expected Close 인라인 편집', () => {
  // 새 금액을 입력하고 포커스를 옮기면 저장되어 보인다.
  // 테스트 코드: DD-104
  it('saves a new amount and shows it', async () => {
    // given: 금액 420,000,000원 Deal
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))
    const input = within(bar).getByLabelText('금액(단위:원)')

    // when: 500000000을 입력하고 Tab을 누른다
    await user.clear(input)
    await user.type(input, '500000000')
    await user.tab()

    // then: 금액이 500,000,000으로 보인다
    await waitFor(() => expect(within(bar).getByText('500,000,000')).toBeVisible())
  })

  // 빈 금액은 문구로 막고 편집을 유지한다.
  // 테스트 코드: DD-104
  it('rejects an empty amount with the server message and keeps the editor open', async () => {
    // given: 금액 편집을 연 sales
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')

    // when: 금액을 비우고 Enter를 누른다
    await user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))
    await user.clear(within(bar).getByLabelText('금액(단위:원)'))
    await user.keyboard('{Enter}')

    // then: 금액 입력 문구가 보이고 입력이 열려 있다
    expect(await within(bar).findByRole('alert')).toHaveTextContent(AMOUNT_INPUT_MESSAGE)
    expect(within(bar).getByLabelText('금액(단위:원)')).toBeVisible()
  })

  // 금액 편집은 Esc로 취소되고 저장되지 않는다.
  // 테스트 코드: DD-104
  it('cancels the amount edit with Escape without saving', async () => {
    // given: 금액 편집을 연 sales
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')

    // when: 숫자를 입력하고 Esc를 누른다
    await user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))
    await user.type(within(bar).getByLabelText('금액(단위:원)'), '9{Escape}')

    // then: 편집이 닫히고 원래 금액이 보인다
    expect(within(bar).queryByLabelText('금액(단위:원)')).not.toBeInTheDocument()
    expect(within(bar).getByText('420,000,000')).toBeVisible()
  })

  // 금액을 Enter로 저장한다.
  // 테스트 코드: DD-104
  it('saves the amount with Enter from the keyboard', async () => {
    // given: 금액 편집을 연 sales(입력에 포커스)
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))

    const input = within(bar).getByLabelText('금액(단위:원)')
    expect(input).toHaveFocus()

    // when: 777000000을 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '777000000{Enter}')

    // then: 금액이 777,000,000으로 보인다
    await waitFor(() => expect(within(bar).getByText('777,000,000')).toBeVisible())
  })

  // 금액 편집은 현재 원 값(콤마 포함)으로 시작한다.
  // 테스트 코드: DD-104
  it('starts the amount editor with the won value', async () => {
    // given: 금액 420,000,000원 Deal
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')

    // when: 금액 편집을 연다
    await user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))

    // then: 입력 값이 '420,000,000'이다
    expect(within(bar).getByLabelText('금액(단위:원)')).toHaveValue('420,000,000')
  })

  // 입력 중 콤마가 붙고 입력한 원 값이 저장된다.
  // 테스트 코드: DD-104
  it('adds commas while typing and saves the typed won', async () => {
    // given: 금액 편집을 연 sales
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))
    const input = within(bar).getByLabelText('금액(단위:원)')

    // when: 1234567을 입력한다
    await user.clear(input)
    await user.type(input, '1234567')
    // then: 입력이 '1,234,567'로 보인다
    expect(input).toHaveValue('1,234,567')

    // when: Enter를 누른다
    await user.keyboard('{Enter}')
    // then: 저장된 금액이 보인다
    await waitFor(() => expect(within(bar).getByText('1,234,567')).toBeVisible())
  })

  // 상한(2^53-1)을 넘는 금액은 문구로 막고 편집을 유지한다.
  // 테스트 코드: DD-104
  it('rejects an amount over the maximum and keeps the editor open', async () => {
    // given: 금액 편집을 연 sales
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))
    const input = within(bar).getByLabelText('금액(단위:원)')

    // when: 9007199254740992를 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '9007199254740992{Enter}')

    // then: 상한 문구가 보이고 입력이 열려 있다
    expect(await within(bar).findByRole('alert')).toHaveTextContent(AMOUNT_TOO_LARGE_MESSAGE)
    expect(within(bar).getByLabelText('금액(단위:원)')).toBeVisible()
  })

  // 금액 항목 이름에 단위가 있고 값에는 '원' 글자가 없다.
  // 테스트 코드: DD-104
  it('labels the amount with its unit', async () => {
    // given: 금액 420,000,000원 Deal
    const { bar } = await openBar(2, '대한제조 MFA 확대')
    const term = within(bar).getByText('금액(단위:원)', { selector: 'dt' })

    // when: Deal 정보를 본다
    const value = term.nextElementSibling as HTMLElement

    // then: 항목 이름이 '금액(단위:원)'이고 값은 콤마 숫자뿐이다
    expect(value).toHaveTextContent('420,000,000')
    expect(value.textContent).not.toContain('원')
  })

  // 새 Expected Close를 입력하고 Enter로 저장한다.
  // 테스트 코드: DD-105
  it('saves a new Expected Close', async () => {
    // given: 대한제조 MFA 확대 Deal
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: 'Expected Close 수정' }))
    const input = within(bar).getByLabelText('Expected Close')

    // when: Expected Close에 2027-03-31을 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '2027-03-31')
    await user.keyboard('{Enter}')

    // then: 2027-03-31이 보인다
    await waitFor(() => expect(within(bar).getByText('2027-03-31')).toBeVisible())
  })

  // Status·Forecast 변경은 Deal History에 남는다.
  // 테스트 코드: DD-105
  it('records the change in the deal history', async () => {
    // given: 대한제조 MFA 확대 Deal
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')

    // when: Forecast를 Commit으로 바꾼다
    await pick(user, bar, 'Forecast', 'Commit')
    // then: Forecast가 Commit으로 보인다
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Commit'))

    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: Forecast 행에 변경 전 Most Likely, 변경 후 Commit이 보인다
    const row = (await screen.findAllByRole('row')).find((r) => within(r).queryByRole('cell', { name: 'Forecast' }))
    expect(row).toBeDefined()
    expect(row).toHaveTextContent('Most Likely')
    expect(row).toHaveTextContent('Commit')
  })
})
