import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import {
  PAGE,
  TODAY_TEXT,
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
  async function readyRow(user: Awaited<ReturnType<typeof open>>['user'], dialog: HTMLElement, n = 1) {
    await fillRow(user, dialog, n, { company: '코어테크', date: '20270310', content: '견적 전달' })
  }

  // 마지막 채운 행의 내용 칸에서 Enter를 누르면 오늘 날짜의 새 행이 생기고 파트너 칸으로 간다.
  // 테스트 코드: PA-080
  it('adds a new row with today as its date and puts the focus on its partner when Enter is pressed in the last full row', async () => {
    // given: 모든 칸을 채운 마지막 행
    const { user, dialog } = await open()
    await readyRow(user, dialog)

    // when: 내용 칸에서 Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 새 행이 생기고 파트너 칸에 포커스가 가며 첫 행 내용에 줄바꿈이 없다
    expect(within(dialog).getAllByRole('group')).toHaveLength(2)
    await waitFor(() => expect(fieldsOf(dialog, 2).partner).toHaveFocus())
    expect(fieldsOf(dialog, 2).date).toHaveValue(TODAY_TEXT)
    expect(fieldsOf(dialog, 1).content).toHaveValue('견적 전달') // 줄바꿈이 들어가지 않는다
  })

  // 다음 행이 있으면 새 행 대신 다음 행의 파트너 칸으로 간다.
  // 테스트 코드: PA-080
  it('moves to the partner of the next row instead of adding one when a next row exists', async () => {
    // given: 행이 둘이고 첫 행을 모두 채웠다
    const { user, dialog } = await open()
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    await readyRow(user, dialog)

    // when: 첫 행 내용 칸에서 Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 행은 둘 그대로이고 둘째 행 파트너 칸에 포커스가 간다
    expect(within(dialog).getAllByRole('group')).toHaveLength(2)
    await waitFor(() => expect(fieldsOf(dialog, 2).partner).toHaveFocus())
  })

  // 행이 덜 찼으면 새 행 대신 빠진 첫 칸으로 간다.
  // 테스트 코드: PA-080
  it('moves to the first missing field of the row instead of adding a row when the row is incomplete', async () => {
    // given: 내용만 쓴 행
    const { user, dialog } = await open()
    await user.click(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '내용만 있음')

    // when: 내용 칸에서 Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 행은 하나 그대로이고 빠진 파트너 칸에 포커스가 간다
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    await waitFor(() => expect(fieldsOf(dialog, 1).partner).toHaveFocus())
  })

  // 틀린 날짜가 첫 문제이면 날짜 칸으로 간다.
  // 테스트 코드: PA-080
  it('goes to the wrong date when the date is the first thing missing', async () => {
    // given: 파트너를 고르고 날짜를 덜 친 채 내용을 썼다
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    const { date, content } = fieldsOf(dialog, 1)
    await user.clear(date)
    await user.type(date, '202703')
    await user.click(content)
    await user.type(content, '내용')

    // when: 내용 칸에서 Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 날짜 칸에 포커스가 가고 행은 하나 그대로다
    await waitFor(() => expect(date).toHaveFocus())
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
  })

  // Shift+Enter는 줄바꿈을 넣는다.
  // 테스트 코드: PA-080
  it('inserts a line break with Shift+Enter and keeps everything else', async () => {
    // given: 모든 칸을 채운 행의 내용 칸
    const { user, dialog } = await open()
    await readyRow(user, dialog)

    // when: Shift+Enter 뒤 "둘째 줄"을 친다
    await user.keyboard('{Shift>}{Enter}{/Shift}둘째 줄')

    // then: 내용에 줄바꿈이 들어가고 포커스·행 수는 그대로다
    const { content } = fieldsOf(dialog, 1)
    expect(content).toHaveValue('견적 전달\n둘째 줄')
    expect(content).toHaveFocus()
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
  })

  // 한글 조합을 확정하는 Enter는 무시한다.
  // 테스트 코드: PA-080
  it.each([
    ['isComposing', { key: 'Enter', isComposing: true }],
    ['keyCode 229', { key: 'Enter', keyCode: 229 }],
  ])('ignores an Enter that confirms a Korean composition (%s)', async (_name, init) => {
    // given: 모든 칸을 채운 행의 내용 칸
    const { user, dialog } = await open()
    await readyRow(user, dialog)
    const { content } = fieldsOf(dialog, 1)

    // when: 한글 조합 중 Enter 키 이벤트가 온다
    fireEvent.keyDown(content, init)

    // then: 새 행이 생기지 않고 포커스가 그대로다
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    expect(content).toHaveFocus()
  })

  // Enter로도 51번째 행은 만들 수 없고 한도를 안내한다.
  // 테스트 코드: PA-076
  it('does not add a 51st row with Enter and explains the limit', async () => {
    // given: 50행이 있고 마지막 행을 모두 채웠다
    const { user, dialog } = await open()
    for (let i = 1; i < 50; i += 1) await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    await fillRow(user, dialog, 50, { company: '코어테크', date: '20270310', content: '마지막' })

    // when: 마지막 행 내용 칸에서 Enter를 누른다
    await user.keyboard('{Enter}')

    // then: 50행 그대로이고 한도 안내가 보인다
    expect(within(dialog).getAllByRole('group')).toHaveLength(50)
    expect(await within(dialog).findByText('한 번에 50건까지 입력할 수 있습니다.')).toBeVisible()
  }, 60_000)
})
