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

describe('팝업 닫기', () => {
  // 빈 팝업은 취소로 바로 닫힌다.
  // 테스트 코드: PA-084
  it('closes an empty dialog at once with 취소', async () => {
    // given: 아무것도 입력하지 않은 팝업
    const { user, dialog } = await open()

    // when: 취소를 누른다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 확인 창 없이 팝업이 닫힌다
    expect(entryDialog()).not.toBeInTheDocument()
    expect(discardDialog()).not.toBeInTheDocument()
  })

  // 빈 팝업은 Escape로도 바로 닫힌다.
  // 테스트 코드: PA-084
  it('closes an empty dialog at once with Escape', async () => {
    // given: 아무것도 입력하지 않은 팝업
    const { user } = await open()

    // when: Escape를 누른다
    await user.keyboard('{Escape}')

    // then: 확인 창 없이 팝업이 닫힌다
    expect(entryDialog()).not.toBeInTheDocument()
    expect(discardDialog()).not.toBeInTheDocument()
  })

  // 입력이 있으면 취소도 Escape와 같게 버릴지 묻는다.
  // 테스트 코드: PA-084
  it.each([
    ['content', async (user: Parameters<typeof choosePartner>[0], dialog: HTMLElement) => user.type(fieldsOf(dialog, 1).content, '쓰던 내용')],
    ['partner', async (user: Parameters<typeof choosePartner>[0], dialog: HTMLElement) => choosePartner(user, dialog, 1, '코어테크')],
  ])('asks before discarding when %s was filled in, and 취소 asks the same as Escape', async (_name, fill) => {
    // given: 한 칸을 채운 팝업
    const { user, dialog } = await open()
    await fill(user, dialog)

    // when: 취소를 누른다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: "입력한 내용을 버릴까요?" 확인 창이 뜨고 입력 팝업은 남아 있다
    const ask = await screen.findByRole('dialog', { name: '입력 취소' })
    expect(within(ask).getByText('입력한 내용을 버릴까요?')).toBeVisible()
    expect(entryDialog()).toBeInTheDocument()
  })

  // Escape도 입력이 있으면 버릴지 묻는다.
  // 테스트 코드: PA-084
  it('asks before discarding on Escape too', async () => {
    // given: 내용을 쓴 팝업
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).content, '쓰던 내용')

    // when: Escape를 누른다
    await user.keyboard('{Escape}')

    // then: 버릴지 묻는 창이 뜬다
    expect(await screen.findByRole('dialog', { name: '입력 취소' })).toBeVisible()
  })

  // 계속 입력을 고르면 입력이 남는다.
  // 테스트 코드: PA-084
  it('keeps the input when the user chooses to continue', async () => {
    // given: 내용을 쓰고 취소를 눌러 확인 창이 뜬 상태
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).content, '쓰던 내용')
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // when: 계속 입력을 누른다
    await user.click(within(await screen.findByRole('dialog', { name: '입력 취소' })).getByRole('button', { name: '계속 입력' }))

    // then: 확인 창만 닫히고 입력은 그대로다
    expect(discardDialog()).not.toBeInTheDocument()
    expect(entryDialog()).toBeInTheDocument()
    expect(fieldsOf(dialog, 1).content).toHaveValue('쓰던 내용')
  })

  // 버리기를 고르면 두 창이 닫히고 입력이 사라진다.
  // 테스트 코드: PA-084
  it('closes both dialogs and drops the input when the user chooses to discard', async () => {
    // given: 내용을 쓰고 취소를 눌러 확인 창이 뜬 상태
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).content, '쓰던 내용')
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // when: 버리기를 누른다
    await user.click(within(await screen.findByRole('dialog', { name: '입력 취소' })).getByRole('button', { name: '버리기' }))

    // then: 두 창이 닫히고 다시 열면 내용이 비어 있다
    await waitFor(() => expect(entryDialog()).not.toBeInTheDocument())
    expect(discardDialog()).not.toBeInTheDocument()
    const again = await openEntryDialog(user)
    expect(fieldsOf(again, 1).content).toHaveValue('')
  })
})
