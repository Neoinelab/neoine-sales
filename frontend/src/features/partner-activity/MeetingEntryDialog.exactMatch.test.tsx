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

describe('파트너 칸에 목록 글자를 그대로 치고 Enter', () => {
  // 목록 글자를 그대로 치고 Enter를 누르면 고른 것으로 보고 날짜 칸으로 간다.
  // 테스트 코드: PA-078
  it('takes a partner typed exactly as in the list as chosen and moves to the date field', async () => {
    // given: 입력 팝업이 열려 있다
    const { user, dialog } = await open()

    // when: 파트너 칸에 "코어테크"를 치고 Enter를 누른다
    await user.type(fieldsOf(dialog, 1).partner, '코어테크{Enter}')

    // then: 날짜 칸에 포커스가 가고 파트너 값이 유지되며 안내 문구가 없다
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(fieldsOf(dialog, 1).partner).toHaveValue('코어테크')
    expect(entryRow(dialog, 1).queryByText(NOT_IN_LIST)).not.toBeInTheDocument()
  })

  // 치는 글자 앞뒤 공백은 무시한다.
  // 테스트 코드: PA-078
  it('ignores spaces around the typed partner', async () => {
    // given: 입력 팝업이 열려 있다
    const { user, dialog } = await open()

    // when: 앞뒤에 공백을 붙여 치고 Enter를 누른다
    await user.type(fieldsOf(dialog, 1).partner, '  코어테크  {Enter}')

    // then: 날짜 칸으로 가고 파트너 값은 "코어테크"다
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(fieldsOf(dialog, 1).partner).toHaveValue('코어테크')
  })

  // 글자로 고른 회사도 다시 고르라는 요구 없이 저장된다.
  // 테스트 코드: PA-078
  it('saves with the company taken from typed text, without asking to choose again', async () => {
    // given: 입력 팝업에서 파트너를 글자로 고르고 날짜·내용을 채웠다
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어테크{Enter}')
    await user.clear(fieldsOf(dialog, 1).date)
    await user.type(fieldsOf(dialog, 1).date, '20270315{Enter}')
    await user.type(fieldsOf(dialog, 1).content, '글자로 고른 행')

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 새 기록이 맨 위에 보이고 팝업이 닫힌다
    await waitFor(() => expect(shownContents()[0]).toBe('글자로 고른 행'))
    expect(screen.queryByRole('dialog', { name: '미팅 내용 입력' })).not.toBeInTheDocument()
  })

  // 목록에 없는 글자를 치고 Enter를 누르면 그 칸에 머물며 목록에서 고르라고 안내한다.
  // 테스트 코드: PA-078
  it.each([
    ['partner', '코어'],
    ['partner', '없는회사'],
  ] as const)('stays on the %s field and says to choose from the list when "%s" matches no item', async (_field, typed) => {
    // given: 입력 팝업이 열려 있다
    const { user, dialog } = await open()

    // when: 목록과 정확히 같지 않은 글자를 치고 Enter를 누른다
    await user.type(fieldsOf(dialog, 1).partner, `${typed}{Enter}`)

    // then: 파트너 칸에 머물고 "목록에서 선택하세요."가 보인다
    expect(fieldsOf(dialog, 1).partner).toHaveFocus()
    expect(fieldsOf(dialog, 1).date).not.toHaveFocus()
    expect(await entryRow(dialog, 1).findByText(NOT_IN_LIST)).toBeVisible()
  })

  // 글자를 고치거나 목록에서 고르면 안내가 사라진다.
  // 테스트 코드: PA-078
  it('removes the message once the text is edited or an item is chosen from the list', async () => {
    // given: 목록에 없는 글자로 Enter를 눌러 안내가 보인다
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어{Enter}')
    expect(await entryRow(dialog, 1).findByText(NOT_IN_LIST)).toBeVisible()

    // when: 글자를 지우고 목록에서 파트너를 고른다
    await user.clear(fieldsOf(dialog, 1).partner)
    await choosePartner(user, dialog, 1, '코어테크')

    // then: 안내가 사라진다
    expect(entryRow(dialog, 1).queryByText(NOT_IN_LIST)).not.toBeInTheDocument()
  })

  // Enter 없이는 친 글자를 고른 것으로 보지 않는다.
  // 테스트 코드: PA-078
  it('does not take a typed partner as chosen without Enter (the list choice contract stays)', async () => {
    // given: 입력 팝업이 열려 있다
    const { user, dialog } = await open()

    // when: 파트너 칸에 "코어테크"만 친다
    await user.type(fieldsOf(dialog, 1).partner, '코어테크')

    // then: 날짜 칸으로 가지 않고 파트너 칸에 머문다
    expect(fieldsOf(dialog, 1).date).not.toHaveFocus()
    expect(fieldsOf(dialog, 1).partner).toHaveFocus()
  })
})
