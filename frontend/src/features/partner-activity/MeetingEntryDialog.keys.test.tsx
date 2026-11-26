import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'
import {
  PAGE,
  choosePartner,
  fieldsOf,
  fillRow,
  openEntryDialog,
  pinClock,
  unpinClock,
  waitForRows,
} from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

async function open(role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(PAGE, { role })
  await waitForRows(10)
  const dialog = await openEntryDialog(view.user)
  return { ...view, dialog }
}

describe('칸 이동', () => {
  // 목록에서 파트너를 고르면 날짜 칸으로 포커스가 간다.
  // 테스트 코드: PA-077
  it('moves the focus to the date field when a partner is chosen from the list', async () => {
    // given: 입력 팝업이 열려 있다
    const { user, dialog } = await open()

    // when: 목록에서 파트너를 고른다
    await choosePartner(user, dialog, 1, '코어테크')

    // then: 날짜 칸에 포커스가 있다
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
  })

  // 행에는 Deal 칸이 없고 콤보박스는 파트너뿐이다.
  // 테스트 코드: PA-077
  it('has no deal field in a row', async () => {
    // when: 입력 팝업을 연다
    const { dialog } = await open()

    // then: Deal 콤보박스가 없고 콤보박스는 파트너 하나다
    expect(within(dialog).queryByRole('combobox', { name: 'Deal' })).not.toBeInTheDocument()
    expect(within(dialog).getAllByRole('combobox')).toHaveLength(1) // 파트너뿐
  })

  // 날짜 칸에서 20270310과 Enter를 치면 내용 칸으로 간다.
  // 테스트 코드: PA-079
  it('moves the focus to the content when 20270310 and Enter are typed in the date field', async () => {
    // given: 파트너를 고른 입력 팝업
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    const { date, content } = fieldsOf(dialog, 1)

    // when: 날짜 칸에 20270310을 치고 Enter를 누른다
    await user.clear(date)
    await user.type(date, '20270310{Enter}')

    // then: 날짜가 2027.03.10으로 표시되고 내용 칸에 포커스가 간다
    expect(date).toHaveValue('2027.03.10')
    await waitFor(() => expect(content).toHaveFocus())
  })

  // 달력에서 날짜를 고르면 내용 칸으로 간다.
  // 테스트 코드: PA-079
  it('moves the focus to the content when a date is picked in the calendar', async () => {
    // given: 파트너를 고른 입력 팝업
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    const { date, content, native } = fieldsOf(dialog, 1)

    // when: 달력에서 2027-03-12를 고른다
    fireEvent.change(native, { target: { value: '2027-03-12' } })

    // then: 날짜가 표시되고 내용 칸에 포커스가 간다
    expect(date).toHaveValue('2027.03.12')
    await waitFor(() => expect(content).toHaveFocus())
  })

  // 덜 친 날짜에서 Enter를 누르면 날짜 칸에 머물고 문구를 보인다.
  // 테스트 코드: PA-079
  it('stays on the date field and shows its message when Enter is pressed on an unfinished date', async () => {
    // given: 파트너를 고른 입력 팝업
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    const { date, content } = fieldsOf(dialog, 1)

    // when: 날짜 칸에 덜 친 값을 치고 Enter를 누른다
    await user.clear(date)
    await user.type(date, '202703{Enter}')

    // then: 날짜 칸에 머물고 오류 문구가 보인다
    expect(date).toHaveFocus()
    expect(content).not.toHaveFocus()
    expect(await within(dialog).findByRole('alert')).toBeVisible()
  })

  // 닫힌 콤보박스에서 Enter를 누르면 다음 칸으로 간다.
  // 테스트 코드: PA-079
  it('moves the focus on from a closed combobox with Enter', async () => {
    // given: 파트너를 고른 뒤 목록만 닫은 파트너 칸
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    const { partner, date } = fieldsOf(dialog, 1)
    await user.click(partner) // 포커스를 파트너 칸으로 되돌린다
    await user.keyboard('{Escape}') // 목록만 닫는다(팝업은 닫히지 않는다)
    // when: Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 날짜 칸으로 가고 팝업은 열려 있다
    await waitFor(() => expect(date).toHaveFocus())
    expect(screen.getByRole('dialog', { name: '미팅 내용 입력' })).toBeVisible()
  })

  // 목록이 열린 동안 Enter는 활성 항목을 고른다.
  // 테스트 코드: PA-079
  it('selects the active option with Enter while the list is open (the combobox keeps its own behavior)', async () => {
    // given: 파트너 목록이 열려 있다
    const { user, dialog } = await open()
    await user.click(fieldsOf(dialog, 1).partner)

    // when: 아래 화살표와 Enter를 누른다
    await user.keyboard('{ArrowDown}{Enter}')

    // then: 파트너가 채워지고 날짜 칸으로 간다
    expect(fieldsOf(dialog, 1).partner.value).not.toBe('')
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
  })
})

describe('내용 칸의 Enter', () => {
  // 완성 여부와 관계없이 Enter와 Shift+Enter는 내용에 줄바꿈만 넣는다.
  // 테스트 코드: PA-094
  it.each([
    { name: 'complete', dateValue: '20270310', withPartner: true, keys: '{Enter}' },
    { name: 'missing partner', dateValue: '20270310', withPartner: false, keys: '{Enter}' },
    { name: 'invalid date', dateValue: '202703', withPartner: true, keys: '{Enter}' },
    { name: 'Shift+Enter', dateValue: '20270310', withPartner: true, keys: '{Shift>}{Enter}{/Shift}' },
  ])('keeps native content newlines without saving or moving focus: $name', async ({ dateValue, withPartner, keys }) => {
    // given: 완성·파트너 누락·날짜 오류 중 하나인 입력과 등록 요청 관찰
    const { user, dialog } = await open()
    if (withPartner) await choosePartner(user, dialog, 1, '코어테크')
    const { date, content } = fieldsOf(dialog, 1)
    await user.clear(date)
    await user.type(date, dateValue)
    await user.type(content, '첫 줄')
    const create = vi.spyOn(gateway.partnerMeetings, 'create')

    // when: 내용 칸에서 줄바꿈 키와 다음 줄을 입력한다
    await user.keyboard(keys + '둘째 줄')

    // then: 한 입력을 유지하고 내용·포커스가 남으며 저장 요청은 없다
    expect(content).toHaveValue('첫 줄\n둘째 줄')
    expect(content).toHaveFocus()
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    expect(within(dialog).getByRole('button', { name: '저장' })).not.toHaveFocus()
    expect(create).not.toHaveBeenCalled()
    expect((await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 1)).total).toBe(12)
    create.mockRestore()
  })

  // 한글 조합을 확정하는 Enter는 기본 동작을 막거나 포커스를 옮기지 않는다.
  // 테스트 코드: PA-094
  it.each([
    ['isComposing', { key: 'Enter', isComposing: true }],
    ['keyCode 229', { key: 'Enter', keyCode: 229 }],
  ])('leaves Korean composition Enter to the textarea (%s)', async (_name, init) => {
    // given: 완성된 입력의 내용 칸
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', content: '견적 전달' })
    const { content } = fieldsOf(dialog, 1)

    // when: 조합 중 Enter 이벤트가 발생한다
    const allowed = fireEvent.keyDown(content, init)

    // then: 기본 동작을 허용하고 한 입력과 포커스를 유지한다
    expect(allowed).toBe(true)
    expect(content).toHaveFocus()
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
  })
})
