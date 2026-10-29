import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../gateway'
import { dealCodeOf } from '../../test/detailTestUtils'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'
import {
  PAGE,
  choosePartner,
  chooseDeal,
  entryRow,
  fieldsOf,
  fillRow,
  meetingRows,
  openEntryDialog,
  pinClock,
  shownContents,
  unpinClock,
  waitForRows,
} from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

async function open() {
  const view = await renderAt(PAGE)
  await waitForRows(10)
  const dialog = await openEntryDialog(view.user)
  return { ...view, dialog }
}

const total = async () => (await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 1)).total

describe('저장 성공 (AC12)', () => {
  it('saves several rows, closes the dialog, shows them at the top of the list and says how many were saved', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '오늘 첫 번째' })
    await user.keyboard('{Enter}')
    await fillRow(user, dialog, 2, { company: '넷브릿지', deal: /미래전자 EDR 교체/, date: '20270316', content: '내일 두 번째' })

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 내용 입력' })).not.toBeInTheDocument())
    expect(await screen.findByText('미팅 2건을 저장했습니다.')).toBeVisible()
    await waitFor(() => expect(shownContents().slice(0, 2)).toEqual(['내일 두 번째', '오늘 첫 번째']))
    expect(await total()).toBe(14)
  })

  it('skips completely empty rows and counts only the saved ones', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '하나만' })
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await screen.findByText('미팅 1건을 저장했습니다.')).toBeVisible()
    expect(await total()).toBe(13)
  })

  it('shows the saved author as the logged-in user and keeps line breaks', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '첫 줄' })
    await user.keyboard('{Shift>}{Enter}{/Shift}둘째 줄')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(shownContents()[0]).toBe('첫 줄\n둘째 줄'))
    expect(within(meetingRows()[0] as HTMLElement).getAllByRole('cell')[4]).toHaveTextContent('김영업')
  })

  it('opens again with a single empty row after a save', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '저장함' })
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 내용 입력' })).not.toBeInTheDocument())

    const again = await openEntryDialog(user)

    expect(within(again).getAllByRole('group')).toHaveLength(1)
    expect(fieldsOf(again, 1).content).toHaveValue('')
    expect(fieldsOf(again, 1).partner).toHaveValue('')
  })
})

describe('저장 전 검사 (AC11)', () => {
  it('sends nothing and says so when every row is empty', async () => {
    const { user, dialog } = await open()

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByText('입력한 미팅이 없습니다.')).toBeVisible()
    expect(screen.getByRole('dialog', { name: '미팅 내용 입력' })).toBeVisible()
    expect(await total()).toBe(12)
  })

  it('does not look at the default date of an untouched row', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '하나' })
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await screen.findByText('미팅 1건을 저장했습니다.')).toBeVisible()
  })

  it('marks every missing field of a partly filled row, sends nothing and focuses the first one', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '정상 행' })
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    await choosePartner(user, dialog, 2, '넷브릿지')
    await user.keyboard('{Escape}')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    const second = entryRow(dialog, 2)
    expect(await second.findByText('Deal을 선택하세요.')).toBeVisible()
    expect(second.getByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(second.queryByText('파트너를 선택하세요.')).not.toBeInTheDocument()
    expect(entryRow(dialog, 1).queryByRole('alert')).not.toBeInTheDocument()
    await waitFor(() => expect(fieldsOf(dialog, 2).deal).toHaveFocus())
    expect(await total()).toBe(12)
  })

  it('requires the partner to be chosen from the list, not just typed', async () => {
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어테크')
    await user.keyboard('{Escape}')
    await user.type(fieldsOf(dialog, 1).content, '내용')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 1).findByText('파트너를 선택하세요.')).toBeVisible()
    expect(await total()).toBe(12)
  })

  it('shows the date message and focuses the date field for a wrong date', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '202703', content: '날짜 틀림' })

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 1).findByRole('alert')).toBeVisible()
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(await total()).toBe(12)
  })

  it('asks for a date when the date is cleared', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, content: '날짜 없음' })
    await user.clear(fieldsOf(dialog, 1).date)

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 1).findByText('미팅 날짜를 입력하세요.')).toBeVisible()
  })

  it('connects the content message to the textarea as its description', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '넷브릿지')
    await chooseDeal(user, dialog, /미래전자 EDR 교체/)

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(fieldsOf(dialog, 1).content).toHaveAccessibleDescription('미팅 내용을 입력하세요.')
    expect(fieldsOf(dialog, 1).content).toBeInvalid()
  })

  it('removes the message of a field once it is filled in', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '넷브릿지')
    await user.keyboard('{Escape}')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()

    await user.type(fieldsOf(dialog, 1).content, '채움')

    await waitFor(() => expect(entryRow(dialog, 1).queryByText('미팅 내용을 입력하세요.')).not.toBeInTheDocument())
  })
})

describe('서버가 거절할 때 (AC12)', () => {
  it('saves nothing, keeps the dialog open and shows the server message at the row and field that were rejected', async () => {
    const code = await dealCodeOf(2)
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /세종에너지/, date: '20270315', content: '정상 행' })
    await user.click(within(dialog).getByRole('button', { name: '행 추가' })) // 2: 빈 행
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    await fillRow(user, dialog, 3, { company: '코어테크', deal: /대한제조 MFA 확대/, date: '20270316', content: '링크가 풀린 행' })
    await gateway.deals.update(code, { partner: null }) // 선택한 뒤 파트너 링크가 풀렸다

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await entryRow(dialog, 3).findByText('선택한 파트너와 연결된 Deal이 아닙니다.')).toBeVisible()
    expect(entryRow(dialog, 1).queryByRole('alert')).not.toBeInTheDocument()
    expect(entryRow(dialog, 2).queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '미팅 내용 입력' })).toBeVisible()
    expect(await total()).toBe(12)
    expect(fieldsOf(dialog, 1).content).toHaveValue('정상 행') // 입력한 값이 남아 있다
  })

  it('shows a 403 from the server in the dialog without losing the input', async () => {
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '권한 없음' })
    await gateway.auth.quickLogin(USER_ID.han) // 읽기 전용 계정: 서버가 쓰기를 거절한다

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByRole('alert')).toBeVisible()
    expect(fieldsOf(dialog, 1).content).toHaveValue('권한 없음')
  })

  it('fills the deal text from the choice so a later save sends the chosen code', async () => {
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /세종에너지/)
    await user.click(fieldsOf(dialog, 1).content)
    await user.type(fieldsOf(dialog, 1).content, '코드 확인')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(shownContents()[0]).toBe('코드 확인'))
    expect(within(meetingRows()[0] as HTMLElement).getByRole('link', { name: '세종에너지 취약점 진단' })).toBeVisible()
  })
})
