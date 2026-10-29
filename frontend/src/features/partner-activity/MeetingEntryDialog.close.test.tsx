import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import { PAGE, choosePartner, fieldsOf, openEntryDialog, pinClock, unpinClock, waitForRows } from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

async function open() {
  const view = await renderAt(PAGE)
  await waitForRows(10)
  const dialog = await openEntryDialog(view.user)
  return { ...view, dialog }
}

const entryDialog = () => screen.queryByRole('dialog', { name: '미팅 내용 입력' })
const discardDialog = () => screen.queryByRole('dialog', { name: '입력 취소' })

describe('팝업 닫기 (AC13)', () => {
  it('closes an empty dialog at once with 취소', async () => {
    const { user, dialog } = await open()

    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    expect(entryDialog()).not.toBeInTheDocument()
    expect(discardDialog()).not.toBeInTheDocument()
  })

  it('closes an empty dialog at once with Escape', async () => {
    const { user } = await open()

    await user.keyboard('{Escape}')

    expect(entryDialog()).not.toBeInTheDocument()
    expect(discardDialog()).not.toBeInTheDocument()
  })

  it('does not count the default date as input', async () => {
    const { user, dialog } = await open()
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))

    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    expect(entryDialog()).not.toBeInTheDocument()
  })

  it.each([
    ['content', async (user: Parameters<typeof choosePartner>[0], dialog: HTMLElement) => user.type(fieldsOf(dialog, 1).content, '쓰던 내용')],
    ['partner', async (user: Parameters<typeof choosePartner>[0], dialog: HTMLElement) => choosePartner(user, dialog, 1, '코어테크')],
  ])('asks before discarding when %s was filled in, and 취소 asks the same as Escape', async (_name, fill) => {
    const { user, dialog } = await open()
    await fill(user, dialog)

    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    const ask = await screen.findByRole('dialog', { name: '입력 취소' })
    expect(within(ask).getByText('입력한 내용을 버릴까요?')).toBeVisible()
    expect(entryDialog()).toBeInTheDocument()
  })

  it('asks before discarding on Escape too', async () => {
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).content, '쓰던 내용')

    await user.keyboard('{Escape}')

    expect(await screen.findByRole('dialog', { name: '입력 취소' })).toBeVisible()
  })

  it('keeps the input when the user chooses to continue', async () => {
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).content, '쓰던 내용')
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    await user.click(within(await screen.findByRole('dialog', { name: '입력 취소' })).getByRole('button', { name: '계속 입력' }))

    expect(discardDialog()).not.toBeInTheDocument()
    expect(entryDialog()).toBeInTheDocument()
    expect(fieldsOf(dialog, 1).content).toHaveValue('쓰던 내용')
  })

  it('closes both dialogs and drops the input when the user chooses to discard', async () => {
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).content, '쓰던 내용')
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    await user.click(within(await screen.findByRole('dialog', { name: '입력 취소' })).getByRole('button', { name: '버리기' }))

    await waitFor(() => expect(entryDialog()).not.toBeInTheDocument())
    expect(discardDialog()).not.toBeInTheDocument()
    const again = await openEntryDialog(user)
    expect(fieldsOf(again, 1).content).toHaveValue('')
  })
})
