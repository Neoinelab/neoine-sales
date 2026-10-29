import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { dealCodeOf } from '../../test/detailTestUtils'
import { renderAt } from '../../test/mockApp'
import { PAGE, chooseDeal, choosePartner, entryRow, fieldsOf, openEntryDialog, pinClock, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

const NOT_IN_LIST = '목록에서 선택하세요.'
/** user-event의 type/keyboard는 `[`를 키 설명으로 읽으므로 글자 그대로 치려면 `[[`로 쓴다. */
const literal = (text: string): string => text.replaceAll('[', '[[')

async function open() {
  const view = await renderAt(PAGE)
  await waitForRows(10)
  const dialog = await openEntryDialog(view.user)
  return { ...view, dialog }
}

describe('파트너·Deal 칸에 목록 글자를 그대로 치고 Enter (계약 변경)', () => {
  it('takes a partner typed exactly as in the list as chosen and moves to the Deal field', async () => {
    const { user, dialog } = await open()

    await user.type(fieldsOf(dialog, 1).partner, '코어테크{Enter}')

    await waitFor(() => expect(fieldsOf(dialog, 1).deal).toHaveFocus())
    expect(fieldsOf(dialog, 1).deal).toBeEnabled()
    expect(fieldsOf(dialog, 1).partner).toHaveValue('코어테크')
    expect(await within(dialog).findByRole('option', { name: /미래전자 ITDR/ })).toBeVisible() // 그 회사의 Deal 선택지가 열렸다
    expect(entryRow(dialog, 1).queryByText(NOT_IN_LIST)).not.toBeInTheDocument()
  })

  it('ignores spaces around the typed partner', async () => {
    const { user, dialog } = await open()

    await user.type(fieldsOf(dialog, 1).partner, '  코어테크  {Enter}')

    await waitFor(() => expect(fieldsOf(dialog, 1).deal).toHaveFocus())
    expect(fieldsOf(dialog, 1).partner).toHaveValue('코어테크')
  })

  it('takes a deal typed exactly as shown (any case, spaces around) as chosen and moves to the date', async () => {
    const code = await dealCodeOf(15)
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    await user.keyboard('{Escape}')

    await user.type(fieldsOf(dialog, 1).deal, `${literal(`  미래전자 itdr [${code.toLowerCase()}]  `)}{Enter}`)

    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(fieldsOf(dialog, 1).deal).toHaveValue(`미래전자 ITDR [${code}]`) // 목록의 글자로 바로잡힌다
    expect(entryRow(dialog, 1).queryByText(NOT_IN_LIST)).not.toBeInTheDocument()
  })

  it('saves with the codes taken from typed text, without asking to choose again', async () => {
    const code = await dealCodeOf(15)
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어테크{Enter}')
    await user.keyboard('{Escape}')
    await user.type(fieldsOf(dialog, 1).deal, `${literal(`미래전자 ITDR [${code}]`)}{Enter}`)
    await user.clear(fieldsOf(dialog, 1).date)
    await user.type(fieldsOf(dialog, 1).date, '20270315{Enter}')
    await user.type(fieldsOf(dialog, 1).content, '글자로 고른 행')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(shownContents()[0]).toBe('글자로 고른 행'))
    expect(screen.queryByRole('dialog', { name: '미팅 내용 입력' })).not.toBeInTheDocument()
  })

  it.each([
    ['partner', '코어'],
    ['partner', '없는회사'],
  ] as const)('stays on the %s field and says to choose from the list when "%s" matches no item', async (_field, typed) => {
    const { user, dialog } = await open()

    await user.type(fieldsOf(dialog, 1).partner, `${typed}{Enter}`)

    expect(fieldsOf(dialog, 1).partner).toHaveFocus()
    expect(fieldsOf(dialog, 1).deal).toBeDisabled()
    expect(await entryRow(dialog, 1).findByText(NOT_IN_LIST)).toBeVisible()
  })

  it.each(['미래전자', '없는 Deal [20270101-D999]'])('stays on the deal field and says to choose from the list when "%s" matches no item', async (typed) => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    await user.keyboard('{Escape}')

    await user.type(fieldsOf(dialog, 1).deal, `${literal(typed)}{Enter}`)

    expect(fieldsOf(dialog, 1).deal).toHaveFocus()
    expect(await entryRow(dialog, 1).findByText(NOT_IN_LIST)).toBeVisible()
    expect(fieldsOf(dialog, 1).date).not.toHaveFocus()
  })

  it('removes the message once the text is edited or an item is chosen from the list', async () => {
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어{Enter}')
    expect(await entryRow(dialog, 1).findByText(NOT_IN_LIST)).toBeVisible()

    await user.clear(fieldsOf(dialog, 1).partner)
    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /미래전자 ITDR/)

    expect(entryRow(dialog, 1).queryByText(NOT_IN_LIST)).not.toBeInTheDocument()
  })

  it('does not take a typed partner as chosen without Enter (the list choice contract stays)', async () => {
    const { user, dialog } = await open()

    await user.type(fieldsOf(dialog, 1).partner, '코어테크')

    expect(fieldsOf(dialog, 1).deal).toBeDisabled()
  })
})
