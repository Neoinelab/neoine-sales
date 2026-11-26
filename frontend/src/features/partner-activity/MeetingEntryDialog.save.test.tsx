import { defaultMock } from '../../test/fake/default'
import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'
import {
  PAGE,
  choosePartner,
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

/** 다른 사람(admin)이 연락처 회사명을 바꿔 그 회사가 파트너 회사 목록에서 사라진다. 끝나면 김영업으로 돌아온다. */
async function renameCompanyBehindTheScenes(from: string, to: string): Promise<void> {
  await defaultMock.signInAs(USER_ID.root)
  for (const row of await gateway.contacts.byCompany('partner', from)) {
    await gateway.contacts.update(row.id, { company: to, name: row.name, title: row.title, email: row.email, phone: row.phone })
  }
  await defaultMock.signInAs(USER_ID.kim)
}

const total = async () => (await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 1)).total

describe('저장 성공', () => {
  // 저장 버튼을 누르면 한 건만 저장하고 팝업을 닫아 목록과 건수 알림을 갱신한다.
  // 테스트 코드: PA-081
  it('saves one meeting, closes the dialog and shows the saved count and list entry', async () => {
    // given: 한 미팅을 채운 팝업
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270315', content: '오늘 미팅' })

    // when: 저장 버튼을 누른다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 한 건 알림과 목록 항목이 보이고 전체 기록은 한 건 늘었다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 내용 입력' })).not.toBeInTheDocument())
    expect(await screen.findByText('미팅 1건을 저장했습니다.')).toBeVisible()
    await waitFor(() => expect(shownContents()[0]).toBe('오늘 미팅'))
    expect(await total()).toBe(13)
  })

  // 저장한 기록의 작성자는 로그인 사용자이고 줄바꿈이 유지된다.
  // 테스트 코드: PA-081
  it('shows the saved author as the logged-in user and keeps line breaks', async () => {
    // given: 줄바꿈이 든 내용을 채운 행
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270315', content: '첫 줄' })
    await user.keyboard('{Enter}둘째 줄{Shift>}{Enter}{/Shift}셋째 줄')

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 줄바꿈이 유지된 채 맨 위에 보이고 작성자는 김영업이다
    await waitFor(() => expect(shownContents()[0]).toBe('첫 줄\n둘째 줄\n셋째 줄'))
    expect(within(meetingRows()[0] as HTMLElement).getAllByRole('cell')[3]).toHaveTextContent('김영업')
  })

  // 저장한 뒤 다시 열면 빈 행 하나다.
  // 테스트 코드: PA-081
  it('opens again with a single empty row after a save', async () => {
    // given: 한 행을 저장하고 팝업이 닫혔다
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270315', content: '저장함' })
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '미팅 내용 입력' })).not.toBeInTheDocument())

    // when: 입력 팝업을 다시 연다
    const again = await openEntryDialog(user)

    // then: 빈 행 하나다
    expect(within(again).getAllByRole('group')).toHaveLength(1)
    expect(fieldsOf(again, 1).content).toHaveValue('')
    expect(fieldsOf(again, 1).partner).toHaveValue('')
  })
})

describe('저장 전 검사', () => {
  // 모든 행이 비어 있으면 안내하고 요청하지 않는다.
  // 테스트 코드: PA-082
  it('sends nothing and says so when every row is empty', async () => {
    // given: 모든 행이 빈 입력 팝업
    const { user, dialog } = await open()

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 안내가 보이고 팝업은 열려 있으며 서버에 12건 그대로다
    expect(await within(dialog).findByText('입력한 미팅이 없습니다.')).toBeVisible()
    expect(screen.getByRole('dialog', { name: '미팅 내용 입력' })).toBeVisible()
    expect(await total()).toBe(12)
  })

  // 덜 채운 행은 빠진 칸마다 문구를 보이고 요청하지 않으며 첫 칸에 포커스한다.
  // 테스트 코드: PA-082
  it('marks every missing field of a partly filled row, sends nothing and focuses the first one', async () => {
    // given: 파트너만 고른 뒤 날짜를 지워 날짜와 내용이 빠진 상태
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '넷브릿지')
    await user.clear(fieldsOf(dialog, 1).date)

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 날짜와 내용 문구가 보이고 날짜 칸에 포커스가 가며 서버에 12건 그대로다
    const current = entryRow(dialog, 1)
    expect(await current.findByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(current.queryByText('파트너를 선택하세요.')).not.toBeInTheDocument()
    expect(current.queryByText(/Deal/)).not.toBeInTheDocument()
    expect(current.getByText('미팅 날짜를 입력하세요.')).toBeVisible()
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(await total()).toBe(12)
  })

  // 파트너는 목록에서 골라야 하고 글자만으로는 저장되지 않는다.
  // 테스트 코드: PA-082
  it('requires the partner to be chosen from the list, not just typed', async () => {
    // given: 파트너에 글자만 치고 내용을 쓴 행
    const { user, dialog } = await open()
    await user.type(fieldsOf(dialog, 1).partner, '코어테크')
    await user.keyboard('{Escape}')
    await user.type(fieldsOf(dialog, 1).content, '내용')

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: "파트너를 선택하세요."가 보이고 서버에 12건 그대로다
    expect(await entryRow(dialog, 1).findByText('파트너를 선택하세요.')).toBeVisible()
    expect(await total()).toBe(12)
  })

  // 틀린 날짜는 날짜 문구를 보이고 날짜 칸에 포커스한다.
  // 테스트 코드: PA-082
  it('shows the date message and focuses the date field for a wrong date', async () => {
    // given: 날짜를 덜 친 행
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', date: '202703', content: '날짜 틀림' })

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 날짜 문구가 보이고 날짜 칸에 포커스가 가며 서버에 12건 그대로다
    expect(await entryRow(dialog, 1).findByRole('alert')).toBeVisible()
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
    expect(await total()).toBe(12)
  })

  // 날짜를 지우면 날짜를 입력하라고 안내한다.
  // 테스트 코드: PA-082
  it('asks for a date when the date is cleared', async () => {
    // given: 날짜를 지운 행
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', content: '날짜 없음' })
    await user.clear(fieldsOf(dialog, 1).date)

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 날짜 입력 문구가 보인다
    expect(await entryRow(dialog, 1).findByText('미팅 날짜를 입력하세요.')).toBeVisible()
  })

  // 내용 문구는 내용 칸의 접근성 설명에 연결된다.
  // 테스트 코드: PA-082
  it('connects the content message to the textarea as its description', async () => {
    // given: 파트너만 고른 행
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '넷브릿지')

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 문구가 보이고 내용 칸이 그 문구를 설명으로 갖고 invalid다
    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()
    expect(fieldsOf(dialog, 1).content).toHaveAccessibleDescription('미팅 내용을 입력하세요.')
    expect(fieldsOf(dialog, 1).content).toBeInvalid()
  })

  // 칸을 채우면 그 칸 문구가 사라진다.
  // 테스트 코드: PA-082
  it('removes the message of a field once it is filled in', async () => {
    // given: 내용이 비어 문구가 보이는 행
    const { user, dialog } = await open()
    await choosePartner(user, dialog, 1, '넷브릿지')
    await user.keyboard('{Escape}')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    expect(await entryRow(dialog, 1).findByText('미팅 내용을 입력하세요.')).toBeVisible()

    // when: 내용 칸을 채운다
    await user.type(fieldsOf(dialog, 1).content, '채움')

    // then: 문구가 사라진다
    await waitFor(() => expect(entryRow(dialog, 1).queryByText('미팅 내용을 입력하세요.')).not.toBeInTheDocument())
  })
})

describe('서버가 거절할 때', () => {
  // 서버가 거절하면 입력을 유지하고 거절된 행·칸에 서버 문구를 보인다.
  // 테스트 코드: PA-083
  it('saves nothing, keeps the dialog open and shows the server message at the row and field that were rejected', async () => {
    // given: 선택한 회사가 저장 전에 연락처 회사명 변경으로 사라졌다
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270316', content: '회사가 사라진 행' })
    await renameCompanyBehindTheScenes('코어테크', '새이름테크') // 선택한 뒤 연락처 회사명이 바뀌었다

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 파트너 칸에 서버 문구가 보이고 팝업과 입력이 남으며 서버에 12건 그대로다
    expect(await entryRow(dialog, 1).findByText('등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.')).toBeVisible()
    await waitFor(() => expect(fieldsOf(dialog, 1).partner).toHaveFocus())
    expect(screen.getByRole('dialog', { name: '미팅 내용 입력' })).toBeVisible()
    expect(await total()).toBe(12)
    expect(fieldsOf(dialog, 1).content).toHaveValue('회사가 사라진 행') // 입력한 값이 남아 있다
  })

  // 위치 없는 실패(403)는 팝업 배너로 보이고 입력을 잃지 않는다.
  // 테스트 코드: PA-083
  it('shows a 403 from the server in the dialog without losing the input', async () => {
    // given: 행을 채운 뒤 읽기 전용 계정으로 바뀌었다
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270315', content: '권한 없음' })
    await defaultMock.signInAs(USER_ID.han) // 읽기 전용 계정: 서버가 쓰기를 거절한다

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 팝업 안 오류 배너가 보이고 입력이 남는다
    expect(await within(dialog).findByRole('alert')).toBeVisible()
    expect(fieldsOf(dialog, 1).content).toHaveValue('권한 없음')
  })

  // 행마다 세 값만 서버로 보낸다.
  // 테스트 코드: PA-081
  it('sends only the three fields of a row to the server', async () => {
    // given: 한 행을 채우고 등록 요청을 관찰한다
    const { user, dialog } = await open()
    const create = vi.spyOn(gateway.partnerMeetings, 'create')
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270315', content: '필드 확인' })

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 요청 항목은 회사·날짜·내용 세 값뿐이다
    await waitFor(() => expect(create).toHaveBeenCalled())
    const sent = create.mock.calls[0]?.[0] ?? []
    expect(sent).toStrictEqual([{ partnerCompany: '코어테크', meetingDate: '2027-03-15', content: '필드 확인' }])
    create.mockRestore()
  })

  // 저장한 기록은 Deal 링크 없이 목록에 보인다.
  // 테스트 코드: PA-081
  it('shows a saved row without any deal link in the list', async () => {
    // given: 한 행을 채운 입력 팝업
    const { user, dialog } = await open()
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270315', content: '링크 없음' })

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 맨 위 행에 링크가 없다
    await waitFor(() => expect(shownContents()[0]).toBe('링크 없음'))
    expect(within(meetingRows()[0] as HTMLElement).queryByRole('link')).not.toBeInTheDocument()
  })
})
