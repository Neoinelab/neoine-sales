import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import { PAGE, choosePartner, entryRow, fieldsOf, openEntryDialog, pinClock, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

const NOT_IN_LIST = '목록에서 선택하세요.'

async function open() {
  const view = await renderAt(PAGE)
  await waitForRows(10)
  const dialog = await openEntryDialog(view.user)
  return { ...view, dialog }
}

describe('파트너 칸에 목록 글자를 그대로 치고 Enter (AC9)', () => {
  it('takes a partner typed exactly as in the list as chosen and moves to the date field', async () => {
    const { user, dialog } = await open()

    await user.type(fieldsOf(dialog, 1).partner, '코어테크{Enter}')

    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(fieldsOf(dialog, 1).partner).toHaveValue('코어테크')
    expect(entryRow(dialog, 1).queryByText(NOT_IN_LIST)).not.toBeInTheDocument()
  })

  it('ignores spaces around the typed partner', async () => {
    const { user, dialog } = await open()

    await user.type(fieldsOf(dialog, 1).partner, '  코어테크  {Enter}')

    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(fieldsOf(dialog, 1).partner).toHaveValue('코어테크')
  })

  it('saves with the company taken from typed text, without asking to choose again', async () => {
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어테크{Enter}')
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
    expect(fieldsOf(dialog, 1).date).not.toHaveFocus()
    expect(await entryRow(dialog, 1).findByText(NOT_IN_LIST)).toBeVisible()
  })

  it('removes the message once the text is edited or an item is chosen from the list', async () => {
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어{Enter}')
    expect(await entryRow(dialog, 1).findByText(NOT_IN_LIST)).toBeVisible()

    await user.clear(fieldsOf(dialog, 1).partner)
    await choosePartner(user, dialog, 1, '코어테크')

    expect(entryRow(dialog, 1).queryByText(NOT_IN_LIST)).not.toBeInTheDocument()
  })

  it('does not take a typed partner as chosen without Enter (the list choice contract stays)', async () => {
    const { user, dialog } = await open()

    await user.type(fieldsOf(dialog, 1).partner, '코어테크')

    expect(fieldsOf(dialog, 1).date).not.toHaveFocus()
    expect(fieldsOf(dialog, 1).partner).toHaveFocus()
  })
})
