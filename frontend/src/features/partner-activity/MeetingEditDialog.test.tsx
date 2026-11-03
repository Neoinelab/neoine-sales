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

describe('행 수정 (AC10)', () => {
  it('opens one row filled with the stored values and no way to add rows', async () => {
    const { dialog } = await openEdit()

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

  it('moves the focus to the save button when Enter is pressed in the content', async () => {
    const { user, dialog } = await openEdit()

    await user.click(fieldsOf(dialog, 1).content)
    await user.keyboard('{Enter}')

    await waitFor(() => expect(within(dialog).getByRole('button', { name: '저장' })).toHaveFocus())
    expect(fieldsOf(dialog, 1).content).toHaveValue(OWN) // 줄바꿈이 들어가지 않는다
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
  })

  it('saves a new date and content, closes the dialog and shows the record in its new place', async () => {
    const { user, dialog } = await openEdit()
    const { date, content } = fieldsOf(dialog, 1)

    await user.clear(date)
    await user.type(date, '20270315')
    await user.clear(content)
    await user.type(content, '고친 내용')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 수정' })).not.toBeInTheDocument())
    await waitFor(() => expect(shownContents()).toContain('고친 내용'))
    expect(shownContents()).not.toContain(OWN)
    expect(cellsOf(rowWithContent('고친 내용'))[1]).toHaveTextContent('2027-03-15')
    expect(shownContents()[0]).toBe('고친 내용') // 가장 늦은 날짜가 되어 맨 위로 옮겨 간다
  })

  it('lets admin edit a record of someone else', async () => {
    const { user, dialog } = await openEdit('수주 후 일정 점검', 'admin')

    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '관리자가 고침')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(shownContents()).toContain('관리자가 고침'))
  })

  it('saves a content-only change even after the contact company was renamed meanwhile', async () => {
    const { user, dialog } = await openEdit()
    await gateway.auth.quickLogin(USER_ID.root)
    for (const row of await gateway.contacts.byCompany('partner', '코어테크')) {
      await gateway.contacts.update(row.id, { company: '새이름테크', name: row.name, title: row.title, email: row.email, phone: row.phone })
    }
    await gateway.auth.quickLogin(USER_ID.kim)

    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '회사명이 바뀐 뒤 수정')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(shownContents()).toContain('회사명이 바뀐 뒤 수정'))
  })

  it('sends only the three fields on save', async () => {
    const { user, dialog } = await openEdit()
    const update = vi.spyOn(gateway.partnerMeetings, 'update')

    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '필드 확인')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(update).toHaveBeenCalled())
    expect(update.mock.calls[0]?.[1]).toStrictEqual({ partnerCompany: '코어테크', meetingDate: '2027-03-13', content: '필드 확인' })
    update.mockRestore()
  })

  it('shows the message and does not send a blank content', async () => {
    const { user, dialog } = await openEdit()

    await user.clear(fieldsOf(dialog, 1).content)
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(screen.getByRole('dialog', { name: '미팅 수정' })).toBeVisible()
    expect(shownContents()).toContain(OWN)
  })

  it('connects the content message to the textarea as its description', async () => {
    const { user, dialog } = await openEdit()

    await user.clear(fieldsOf(dialog, 1).content)
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(fieldsOf(dialog, 1).content).toHaveAccessibleDescription('미팅 내용을 입력하세요.')
  })

  it('shows the message and focuses the date for a wrong date', async () => {
    const { user, dialog } = await openEdit()

    await user.clear(fieldsOf(dialog, 1).date)
    await user.type(fieldsOf(dialog, 1).date, '202703')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 1).findByRole('alert')).toBeVisible()
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
  })

  it('keeps the date and content when another partner is chosen', async () => {
    const { user, dialog } = await openEdit()

    await user.clear(fieldsOf(dialog, 1).partner)
    await choosePartner(user, dialog, 1, '넷브릿지')

    expect(fieldsOf(dialog, 1).partner).toHaveValue('넷브릿지')
    expect(fieldsOf(dialog, 1).date).toHaveValue('2027.03.13')
    expect(fieldsOf(dialog, 1).content).toHaveValue(OWN)
  })

  it('shows the server message when the record was deleted while editing', async () => {
    const { user, dialog } = await openEdit()
    const mine = (await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc', content: OWN }, 0, 10)).items[0]
    await gateway.partnerMeetings.remove(mine?.id ?? 0)

    await user.clear(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '삭제된 뒤 저장')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByText('미팅 기록을 찾을 수 없습니다.')).toBeVisible()
  })

  it('closes with 취소 without saving', async () => {
    const { user, dialog } = await openEdit()
    await user.type(fieldsOf(dialog, 1).content, ' 추가')

    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 수정' })).not.toBeInTheDocument())
    expect(shownContents()).toContain(OWN)
  })
})
