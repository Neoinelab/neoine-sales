import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import {
  PAGE,
  TODAY_TEXT,
  chooseDeal,
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

describe('칸 이동 (AC8, AC9)', () => {
  it('moves the focus to the deal field and opens its list when a partner is chosen', async () => {
    const { user, dialog } = await open()

    await choosePartner(user, dialog, 1, '코어테크')

    await waitFor(() => expect(fieldsOf(dialog, 1).deal).toHaveFocus())
    expect(await within(dialog).findByRole('listbox', { name: 'Deal' })).toBeVisible()
  })

  it('moves the focus to the date field when a deal is chosen', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')

    await chooseDeal(user, dialog, /미래전자 ITDR/)

    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
  })

  it('moves the focus to the content when 20270310 and Enter are typed in the date field', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /미래전자 ITDR/)
    const { date, content } = fieldsOf(dialog, 1)

    await user.clear(date)
    await user.type(date, '20270310{Enter}')

    expect(date).toHaveValue('2027.03.10')
    await waitFor(() => expect(content).toHaveFocus())
  })

  it('moves the focus to the content when a date is picked in the calendar', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /미래전자 ITDR/)
    const { date, content, native } = fieldsOf(dialog, 1)

    fireEvent.change(native, { target: { value: '2027-03-12' } })

    expect(date).toHaveValue('2027.03.12')
    await waitFor(() => expect(content).toHaveFocus())
  })

  it('stays on the date field and shows its message when Enter is pressed on an unfinished date', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /미래전자 ITDR/)
    const { date, content } = fieldsOf(dialog, 1)

    await user.clear(date)
    await user.type(date, '202703{Enter}')

    expect(date).toHaveFocus()
    expect(content).not.toHaveFocus()
    expect(await within(dialog).findByRole('alert')).toBeVisible()
  })

  it('moves the focus on from a closed combobox with Enter', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    const { deal, date } = fieldsOf(dialog, 1)
    await waitFor(() => expect(deal).toHaveFocus())

    await user.keyboard('{Escape}') // 목록만 닫는다(팝업은 닫히지 않는다)
    await user.keyboard('{Enter}')

    await waitFor(() => expect(date).toHaveFocus())
    expect(screen.getByRole('dialog', { name: '미팅 내용 입력' })).toBeVisible()
  })

  it('selects the active option with Enter while the list is open (the combobox keeps its own behavior)', async () => {
    const { user, dialog } = await open()
    await user.click(fieldsOf(dialog, 1).partner)

    await user.keyboard('{ArrowDown}{Enter}')

    expect(fieldsOf(dialog, 1).partner.value).not.toBe('')
    await waitFor(() => expect(fieldsOf(dialog, 1).deal).toHaveFocus())
  })
})

describe('내용 칸의 Enter (AC9)', () => {
  async function readyRow(user: Awaited<ReturnType<typeof open>>['user'], dialog: HTMLElement, n = 1) {
    await fillRow(user, dialog, n, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270310', content: '견적 전달' })
  }

  it('adds a new row with today as its date and puts the focus on its partner when Enter is pressed in the last full row', async () => {
    const { user, dialog } = await open()
    await readyRow(user, dialog)

    await user.keyboard('{Enter}')

    expect(within(dialog).getAllByRole('group')).toHaveLength(2)
    await waitFor(() => expect(fieldsOf(dialog, 2).partner).toHaveFocus())
    expect(fieldsOf(dialog, 2).date).toHaveValue(TODAY_TEXT)
    expect(fieldsOf(dialog, 1).content).toHaveValue('견적 전달') // 줄바꿈이 들어가지 않는다
  })

  it('moves to the partner of the next row instead of adding one when a next row exists', async () => {
    const { user, dialog } = await open()
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    await readyRow(user, dialog)

    await user.keyboard('{Enter}')

    expect(within(dialog).getAllByRole('group')).toHaveLength(2)
    await waitFor(() => expect(fieldsOf(dialog, 2).partner).toHaveFocus())
  })

  it('moves to the first missing field of the row instead of adding a row when the row is incomplete', async () => {
    const { user, dialog } = await open()
    await user.click(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '내용만 있음')

    await user.keyboard('{Enter}')

    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    await waitFor(() => expect(fieldsOf(dialog, 1).partner).toHaveFocus())
  })

  it('goes to the wrong date when the date is the first thing missing', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /미래전자 ITDR/)
    const { date, content } = fieldsOf(dialog, 1)
    await user.clear(date)
    await user.type(date, '202703')
    await user.click(content)
    await user.type(content, '내용')

    await user.keyboard('{Enter}')

    await waitFor(() => expect(date).toHaveFocus())
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
  })

  it('inserts a line break with Shift+Enter and keeps everything else', async () => {
    const { user, dialog } = await open()
    await readyRow(user, dialog)

    await user.keyboard('{Shift>}{Enter}{/Shift}둘째 줄')

    const { content } = fieldsOf(dialog, 1)
    expect(content).toHaveValue('견적 전달\n둘째 줄')
    expect(content).toHaveFocus()
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
  })

  it.each([
    ['isComposing', { key: 'Enter', isComposing: true }],
    ['keyCode 229', { key: 'Enter', keyCode: 229 }],
  ])('ignores an Enter that confirms a Korean composition (%s)', async (_name, init) => {
    const { user, dialog } = await open()
    await readyRow(user, dialog)
    const { content } = fieldsOf(dialog, 1)

    fireEvent.keyDown(content, init)

    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    expect(content).toHaveFocus()
  })

  it('does not add a 51st row with Enter and explains the limit', async () => {
    const { user, dialog } = await open()
    for (let i = 1; i < 50; i += 1) await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    await fillRow(user, dialog, 50, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270310', content: '마지막' })

    await user.keyboard('{Enter}')

    expect(within(dialog).getAllByRole('group')).toHaveLength(50)
    expect(await within(dialog).findByText('한 번에 50건까지 입력할 수 있습니다.')).toBeVisible()
  }, 60_000)
})
