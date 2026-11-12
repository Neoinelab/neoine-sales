import { defaultMock } from '../../test/fake/default'
import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'
import { PAGE, cellsOf, choosePartner, entryRow, fieldsOf, pinClock, rowWithContent, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

const OWN = 'ITDR 가격 협상' // kim 작성, 코어테크 / 2027-03-13

async function openEdit(content = OWN, role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(PAGE, { role })
  await waitForRows(10)
  await view.user.click(within(rowWithContent(content)).getByRole('button', { name: '수정' }))
  const dialog = await screen.findByRole('dialog', { name: '미팅 수정' })
  return { ...view, dialog }
}

describe('행 수정', () => {
  // 수정 팝업은 저장된 값이 든 한 행이고 행을 더하거나 지울 수 없다.
  // 테스트 코드: PA-085
  it('opens one row filled with the stored values and no way to add rows', async () => {
    // when: 내 기록의 수정 버튼을 눌러 수정 팝업을 연다
    const { dialog } = await openEdit()

    // then: 저장된 회사·날짜·내용이 든 한 행이고 행 추가·삭제 버튼과 Deal 칸이 없다
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    const { partner, date, content } = fieldsOf(dialog, 1)
    expect(partner).toHaveValue('코어테크')
    expect(within(dialog).queryByRole('combobox', { name: 'Deal' })).not.toBeInTheDocument()
    expect(within(dialog).getAllByRole('combobox')).toHaveLength(1)
    expect(date).toHaveValue('2027.03.13')
    expect(content).toHaveValue(OWN)
    expect(within(dialog).queryByRole('button', { name: '행 추가' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: '행 삭제' })).not.toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: '저장' })).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '취소' })).toBeVisible()
  })

  // 내용 칸에서 Enter를 누르면 저장 버튼으로 포커스가 간다.
  // 테스트 코드: PA-085
  it('moves the focus to the save button when Enter is pressed in the content', async () => {
    // given: 수정 팝업이 열려 있다
    const { user, dialog } = await openEdit()

    // when: 내용 칸에서 Enter를 누른다
    await user.click(fieldsOf(dialog, 1).content)
    await user.keyboard('{Enter}')

    // then: 저장 버튼에 포커스가 가고 내용에 줄바꿈이 없다
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '저장' })).toHaveFocus())
    expect(fieldsOf(dialog, 1).content).toHaveValue(OWN) // 줄바꿈이 들어가지 않는다
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
  })

  // 새 날짜·내용을 저장하면 팝업이 닫히고 새 위치에 보인다.
  // 테스트 코드: PA-085
  it('saves a new date and content, closes the dialog and shows the record in its new place', async () => {
    // given: 수정 팝업이 열려 있다
    const { user, dialog } = await openEdit()
    const { date, content } = fieldsOf(dialog, 1)

    // when: 날짜와 내용을 고쳐 저장한다
    await user.clear(date)
    await user.type(date, '20270315')
    await user.clear(content)
    await user.type(content, '고친 내용')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 팝업이 닫히고 고친 기록이 가장 늦은 날짜로 맨 위에 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 수정' })).not.toBeInTheDocument())
    await waitFor(() => expect(shownContents()).toContain('고친 내용'))
    expect(shownContents()).not.toContain(OWN)
    expect(cellsOf(rowWithContent('고친 내용'))[1]).toHaveTextContent('2027-03-15')
    expect(shownContents()[0]).toBe('고친 내용') // 가장 늦은 날짜가 되어 맨 위로 옮겨 간다
  })

  // admin은 남의 기록을 수정한다.
  // 테스트 코드: PA-085
  it('lets admin edit a record of someone else', async () => {
    // given: admin이 남의 기록의 수정 팝업을 열었다
    const { user, dialog } = await openEdit('수주 후 일정 점검', 'admin')

    // when: 내용을 고쳐 저장한다
    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '관리자가 고침')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 고친 내용이 보인다
    await waitFor(() => expect(shownContents()).toContain('관리자가 고침'))
  })

  // 연락처 회사명이 그 사이 바뀌어도 내용만 고쳐 저장된다.
  // 테스트 코드: PA-086
  it('saves a content-only change even after the contact company was renamed meanwhile', async () => {
    // given: 수정 팝업을 연 뒤 연락처 회사명이 바뀌었다
    const { user, dialog } = await openEdit()
    await defaultMock.signInAs(USER_ID.root)
    for (const row of await gateway.contacts.byCompany('partner', '코어테크')) {
      await gateway.contacts.update(row.id, { company: '새이름테크', name: row.name, title: row.title, email: row.email, phone: row.phone })
    }
    await defaultMock.signInAs(USER_ID.kim)

    // when: 내용만 고쳐 저장한다
    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '회사명이 바뀐 뒤 수정')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 고친 내용이 보인다
    await waitFor(() => expect(shownContents()).toContain('회사명이 바뀐 뒤 수정'))
  })

  // 저장은 회사·날짜·내용 세 값만 보낸다.
  // 테스트 코드: PA-085
  it('sends only the three fields on save', async () => {
    // given: 수정 팝업과 수정 요청 관찰
    const { user, dialog } = await openEdit()
    const update = vi.spyOn(gateway.partnerMeetings, 'update')

    // when: 내용을 고쳐 저장한다
    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '필드 확인')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 요청 본문이 세 값뿐이다
    await waitFor(() => expect(update).toHaveBeenCalled())
    expect(update.mock.calls[0]?.[1]).toStrictEqual({ partnerCompany: '코어테크', meetingDate: '2027-03-13', content: '필드 확인' })
    update.mockRestore()
  })

  // 빈 내용은 문구를 보이고 보내지 않는다.
  // 테스트 코드: PA-086
  it('shows the message and does not send a blank content', async () => {
    // given: 수정 팝업이 열려 있다
    const { user, dialog } = await openEdit()

    // when: 내용을 지우고 저장한다
    await user.clear(fieldsOf(dialog, 1).content)
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 문구가 보이고 팝업이 열려 있으며 기록은 그대로다
    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(screen.getByRole('dialog', { name: '미팅 수정' })).toBeVisible()
    expect(shownContents()).toContain(OWN)
  })

  // 내용 문구는 내용 칸의 접근성 설명에 연결된다.
  // 테스트 코드: PA-086
  it('connects the content message to the textarea as its description', async () => {
    // given: 수정 팝업이 열려 있다
    const { user, dialog } = await openEdit()

    // when: 내용을 지우고 저장한다
    await user.clear(fieldsOf(dialog, 1).content)
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 문구가 보이고 내용 칸의 설명으로 연결된다
    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(fieldsOf(dialog, 1).content).toHaveAccessibleDescription('미팅 내용을 입력하세요.')
  })

  // 틀린 날짜는 문구를 보이고 날짜 칸에 포커스한다.
  // 테스트 코드: PA-086
  it('shows the message and focuses the date for a wrong date', async () => {
    // given: 수정 팝업이 열려 있다
    const { user, dialog } = await openEdit()

    // when: 날짜를 덜 치고 저장한다
    await user.clear(fieldsOf(dialog, 1).date)
    await user.type(fieldsOf(dialog, 1).date, '202703')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 문구가 보이고 날짜 칸에 포커스가 간다
    expect(await entryRow(dialog, 1).findByRole('alert')).toBeVisible()
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
  })

  // 다른 파트너를 골라도 날짜·내용을 유지한다.
  // 테스트 코드: PA-086
  it('keeps the date and content when another partner is chosen', async () => {
    // given: 수정 팝업이 열려 있다
    const { user, dialog } = await openEdit()

    // when: 파트너를 지우고 다른 회사를 고른다
    await user.clear(fieldsOf(dialog, 1).partner)
    await choosePartner(user, dialog, 1, '넷브릿지')

    // then: 파트너만 바뀌고 날짜·내용은 그대로다
    expect(fieldsOf(dialog, 1).partner).toHaveValue('넷브릿지')
    expect(fieldsOf(dialog, 1).date).toHaveValue('2027.03.13')
    expect(fieldsOf(dialog, 1).content).toHaveValue(OWN)
  })

  // 수정하는 사이 기록이 지워지면 서버 문구를 보인다.
  // 테스트 코드: PA-086
  it('shows the server message when the record was deleted while editing', async () => {
    // given: 수정 팝업이 열린 사이에 그 기록이 지워졌다
    const { user, dialog } = await openEdit()
    const mine = (await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc', content: OWN }, 0, 10)).items[0]
    await gateway.partnerMeetings.remove(mine?.id ?? 0)

    // when: 내용을 고쳐 저장한다
    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '삭제된 뒤 저장')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 서버 문구가 팝업에 보인다
    expect(await within(dialog).findByText('미팅 기록을 찾을 수 없습니다.')).toBeVisible()
  })

  // 취소하면 저장 없이 닫힌다.
  // 테스트 코드: PA-085
  it('closes with 취소 without saving', async () => {
    // given: 내용을 고친 수정 팝업
    const { user, dialog } = await openEdit()
    await user.type(fieldsOf(dialog, 1).content, ' 추가')

    // when: 취소를 누른다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 팝업이 닫히고 기록은 그대로다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 수정' })).not.toBeInTheDocument())
    expect(shownContents()).toContain(OWN)
  })
})
