import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { A_INPUT, DETAIL, addAction, bodyRows, fieldValue, makeGate, openActionsTab, openDetail, type DetailView } from '../../../test/actionDetail'
import { defaultMock, resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { seedActionTypeId } from '../../../test/fake/seed/actionTypes'

/** Action 상세 팝업의 칸별 인라인 수정(AC-R50·R51). 서버 시계는 2026-11-13로 고정한다. */
const NOW = '2026-11-13T14:30:00+09:00'
const HINT = '목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다.'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const detail = () => screen.getByRole('dialog', { name: DETAIL })
const queryDetail = () => screen.queryByRole('dialog', { name: DETAIL })

/** 김영업의 Action A를 남기고 그 상세 팝업을 연다. */
async function openA(view?: DetailView) {
  const v = view ?? (await openActionsTab())
  const action = await addAction(v, A_INPUT)
  return { view: v, action, dialog: await openDetail(v, '킥오프 미팅') }
}

/** 김영업의 진행사항만 Action C를 남기고 그 상세 팝업을 연다. */
async function openC() {
  const view = await openActionsTab()
  const action = await addAction(view, { progress: '자료 송부' })
  return { view, action, dialog: await openDetail(view, '자료 송부') }
}

describe('진행사항 인라인 수정', () => {
  // 진행사항만 고치면 그 칸만 바꾼 수정 요청이 한 번 나가고 팝업은 열린 채 새 값을 보인다.
  // 테스트 코드: AC-136
  it('sends one update with only the progress changed and keeps the popup open with the new value', async () => {
    // given: 김영업의 Action A 상세 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, action, dialog } = await openA()
    const badges = within(dialog).getByText('가격협상').textContent

    // when: "진행사항 수정"을 눌러 "킥오프 미팅 완료"로 바꾸고 "진행사항 저장"을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const input = within(dialog).getByLabelText('진행사항')
    await view.user.clear(input)
    await view.user.type(input, '킥오프 미팅 완료')
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))

    // then: 수정 요청은 한 번이고 다른 칸은 그대로이며 acted_on이 없다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[0]).toBe(action.id)
    expect(update.mock.calls[0]?.[1]).toEqual({
      type: { id: seedActionTypeId('미팅') },
      progress: '킥오프 미팅 완료',
      nextAction: '요구사항 문서 전달',
      dueDate: '2027-01-15',
    })
    expect(update.mock.calls[0]?.[1]).not.toHaveProperty('actedOn')
    // then: 팝업은 열린 채 새 값을 보이고 알림이 나온다
    await waitFor(() => expect(fieldValue(detail(), '진행사항')).toHaveTextContent('킥오프 미팅 완료'))
    expect(screen.getByText('Action이 수정되었습니다.')).toBeVisible()
    expect(within(detail()).getByText('가격협상').textContent).toBe(badges)

    // when: 팝업을 닫는다
    await view.user.click(within(detail()).getByRole('button', { name: '닫기' }))
    // then: 표의 그 행도 새 진행사항이다
    expect(queryDetail()).not.toBeInTheDocument()
    await waitFor(() => expect(within(view.table).getByText('킥오프 미팅 완료')).toBeVisible())
  })

  // 저장한 수정은 Deal History에 "수정:" 이력으로 남는다.
  // 테스트 코드: AC-136
  it('leaves an edit entry in the deal history', async () => {
    // given: 진행사항을 고친 Action
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const input = within(dialog).getByLabelText('진행사항')
    await view.user.clear(input)
    await view.user.type(input, '이력 확인용')
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))
    await waitFor(() => expect(fieldValue(detail(), '진행사항')).toHaveTextContent('이력 확인용'))

    // when: 팝업을 닫고 Deal History 탭으로 간다
    await view.user.click(within(detail()).getByRole('button', { name: '닫기' }))
    await view.user.click(screen.getByRole('tab', { name: 'Deal History' }))

    // then: Action 이력과 "수정:" 문구가 있다
    expect((await screen.findAllByRole('cell', { name: 'Action' })).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/수정: /).length).toBeGreaterThan(0)
  })
})

describe('유형 인라인 수정', () => {
  // 후보를 고르면 고르는 순간 id로 저장한다.
  // 테스트 코드: AC-137
  it('saves a picked candidate at once with its id', async () => {
    // given: 유형 목록에 "이메일"이 있는 Action A 팝업
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()

    // when: "유형 수정"을 눌러 후보 "이메일"을 고른다
    await view.user.click(within(dialog).getByRole('button', { name: '유형 수정' }))
    await view.user.click(within(dialog).getByRole('combobox', { name: '유형' }))
    await view.user.click(within(await screen.findByRole('listbox', { name: '유형' })).getByRole('option', { name: '이메일' }))

    // then: 바로 그 유형 id로 한 번 보낸다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].type).toEqual({ id: seedActionTypeId('이메일') })
    await waitFor(() => expect(fieldValue(detail(), '유형')).toHaveTextContent('이메일'))
  })

  // 목록에 없는 이름은 편집 중 안내가 보이고 이름으로 보낸다.
  // 테스트 코드: AC-137
  it('hints about an unknown type while editing and sends it by name', async () => {
    // given: Action A 팝업의 유형 편집
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '유형 수정' }))
    const input = within(dialog).getByRole('combobox', { name: '유형' })

    // when: "현장 데모"를 쳐서 Enter를 누른다
    await view.user.clear(input)
    await view.user.type(input, '현장 데모')
    // then: 새 유형 안내가 보인다
    expect(within(dialog).getByText(HINT)).toBeVisible()
    await view.user.keyboard('{Enter}')

    // then: 이름으로 보내고 팝업 유형이 "현장 데모"가 된다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].type).toEqual({ name: '현장 데모' })
    await waitFor(() => expect(fieldValue(detail(), '유형')).toHaveTextContent('현장 데모'))
  })

  // 유형을 바꿔 저장하면 Deal History에 "수정: <새 유형> · " 이력이 남는다.
  // 테스트 코드: AC-137
  it('leaves a history entry with the new type name', async () => {
    // given: Action A 팝업에서 유형을 "현장 점검"으로 바꿔 저장했다
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '유형 수정' }))
    const input = within(dialog).getByRole('combobox', { name: '유형' })
    await view.user.clear(input)
    await view.user.type(input, '현장 점검{Enter}')
    await waitFor(() => expect(fieldValue(detail(), '유형')).toHaveTextContent('현장 점검'))

    // when: 팝업을 닫고 Deal History 탭으로 간다
    await view.user.click(within(detail()).getByRole('button', { name: '닫기' }))
    await view.user.click(screen.getByRole('tab', { name: 'Deal History' }))

    // then: "수정: 현장 점검 · " 이력이 있다
    expect((await screen.findAllByText(/수정: 현장 점검 · /)).length).toBeGreaterThan(0)
  })

  // 공백뿐이거나 51자인 유형은 칸 아래 문구로 막고 요청하지 않는다.
  // 테스트 코드: AC-137
  it.each([
    ['공백뿐', '   ', '유형을 입력하세요.'],
    ['51자', '가'.repeat(51), '유형은 50자 이내로 입력하세요.'],
  ])('blocks a %s type under the field without a request', async (_name, typed, message) => {
    // given: Action A 팝업의 유형 편집(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '유형 수정' }))
    const input = within(dialog).getByRole('combobox', { name: '유형' })

    // when: 그 값을 치고 Enter를 누른다
    await view.user.clear(input)
    await view.user.type(input, `${typed}{Enter}`)

    // then: 문구가 보이고 편집이 열린 채 요청이 없다
    expect(await within(dialog).findByText(message)).toBeVisible()
    expect(within(dialog).getByRole('combobox', { name: '유형' })).toBeVisible()
    expect(update).not.toHaveBeenCalled()
  })
})

describe('진행사항 저장 버튼', () => {
  // Enter·Shift+Enter는 줄바꿈이고 저장 버튼을 누르기 전에는 요청이 없다.
  // 테스트 코드: AC-138
  it('breaks the line with Enter and Shift+Enter and saves only with the save button', async () => {
    // given: Action A 팝업의 진행사항 편집(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const progress = within(dialog).getByLabelText('진행사항')

    // when: 지우고 "1줄", Enter, "2줄", Shift+Enter, "3줄"을 쓴다
    await view.user.clear(progress)
    await view.user.type(progress, '1줄{Enter}2줄{Shift>}{Enter}{/Shift}3줄')

    // then: 저장 전에는 요청이 없고 칸 값에 줄바꿈이 들어 있으며 편집이 열린 채다
    expect(update).not.toHaveBeenCalled()
    expect(progress).toHaveValue('1줄\n2줄\n3줄')

    // when: "진행사항 저장"을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))

    // then: 요청은 한 번이고 진행사항이 세 줄이며 memo 키는 없고 팝업 진행사항이 세 줄로 보인다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].progress).toBe('1줄\n2줄\n3줄')
    expect(update.mock.calls[0]?.[1]).not.toHaveProperty('memo')
    await waitFor(() => expect(fieldValue(detail(), '진행사항').textContent).toContain('1줄\n2줄\n3줄'))
  })

  // Next Action이 남아 있으면 진행사항을 모두 지워 저장하고 "—"로 보인다.
  // 테스트 코드: AC-138
  it('saves an emptied progress while a next action remains and shows a dash', async () => {
    // given: Next Action이 있는 Action A 팝업의 진행사항 편집
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))

    // when: 진행사항을 모두 지우고 "진행사항 저장"을 누른다
    await view.user.clear(within(dialog).getByLabelText('진행사항'))
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))

    // then: 진행사항 ""로 저장되고 팝업 진행사항이 "—"다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].progress).toBe('')
    await waitFor(() => expect(fieldValue(detail(), '진행사항')).toHaveTextContent('—'))
  })

  // 진행사항과 Next Action이 모두 비면 칸 아래 문구로 막는다.
  // 테스트 코드: AC-138
  it('blocks emptying the progress of an action that has no next action', async () => {
    // given: 진행사항만 있는 Action C 팝업의 진행사항 편집(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openC()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))

    // when: 진행사항을 모두 지우고 "진행사항 저장"을 누른다
    await view.user.clear(within(dialog).getByLabelText('진행사항'))
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))

    // then: 문구가 칸 아래 보이고 요청이 없으며 편집이 열린 채 포커스가 진행사항 칸에 있다
    expect(await within(dialog).findByText('진행사항 또는 Next Action을 입력하세요.')).toBeVisible()
    expect(update).not.toHaveBeenCalled()
    expect(within(dialog).getByLabelText('진행사항')).toHaveFocus()
  })
})

describe('Next Action · Due Date 묶음 수정', () => {
  // Next Action만 쓰면 막히고, Due Date 칸의 Enter는 저장이 아니며, 둘을 채워 저장 버튼을 누르면 한 요청으로 저장되고 Open이 된다.
  // 테스트 코드: AC-139
  it('validates the pair together and saves both in one request with the state Open only by the save button', async () => {
    // given: 진행사항만 Action C 팝업의 "Next Action · Due Date 수정"(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openC()
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' }))
    const save = () => within(dialog).getByRole('button', { name: 'Next Action · Due Date 저장' })

    // when: Next Action에 "견적 발송"만 쓰고 저장 버튼을 누른다
    await view.user.type(within(dialog).getByLabelText('Next Action'), '견적 발송')
    await view.user.click(save())
    // then: "Due Date를 입력하세요."로 막히고 요청이 없다
    expect(await within(dialog).findByText('Due Date를 입력하세요.')).toBeVisible()
    expect(update).not.toHaveBeenCalled()

    // when: Due Date에 20270110을 쓰고 Enter를 누른다
    await view.user.type(within(dialog).getByLabelText('Due Date'), '20270110{Enter}')
    // then: 요청이 없고 편집이 열린 채 Due Date 칸이 확정된 날짜다
    expect(update).not.toHaveBeenCalled()
    expect(within(dialog).getByLabelText('Due Date')).toHaveValue('2027.01.10')

    // when: 저장 버튼을 누른다
    await view.user.click(save())
    // then: 한 요청으로 두 값을 보내고 팝업에 두 값과 상태 Open이 보인다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1]).toMatchObject({ progress: '자료 송부', nextAction: '견적 발송', dueDate: '2027-01-10' })
    await waitFor(() => expect(fieldValue(detail(), 'Next Action')).toHaveTextContent('견적 발송'))
    expect(fieldValue(detail(), 'Due Date')).toHaveTextContent('2027-01-10')
    expect(fieldValue(detail(), 'Next Action 상태')).toHaveTextContent('Open')
  })

  // Next Action을 모두 지우면 Due Date 칸도 비고 저장하면 둘 다 "—"가 된다.
  // 테스트 코드: AC-139
  it('empties the due date together with the next action and saves both as empty', async () => {
    // given: Next Action·Due Date가 있는 Action A 팝업의 묶음 편집(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' }))

    // when: Next Action을 모두 지운다
    await view.user.clear(within(dialog).getByLabelText('Next Action'))
    // then: Due Date 칸도 비어 있다
    expect(within(dialog).getByLabelText('Due Date')).toHaveValue('')

    // when: 저장 버튼을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 저장' }))
    // then: Next Action ""·Due null로 보내고 팝업의 세 값이 "—"가 된다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1]).toMatchObject({ nextAction: '', dueDate: null })
    await waitFor(() => expect(fieldValue(detail(), 'Next Action')).toHaveTextContent('—'))
    expect(fieldValue(detail(), 'Due Date')).toHaveTextContent('—')
    expect(fieldValue(detail(), 'Next Action 상태')).toHaveTextContent('—')
  })
})

describe('편집 닫기와 변경 없음', () => {
  // 편집 중 Esc는 그 칸만 닫고 다음 Esc가 팝업을 닫는다.
  // 테스트 코드: AC-140
  it('closes only the field on the first Escape and the popup on the next one', async () => {
    // given: 진행사항 편집에 " 버릴 글"을 쓴 Action A 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    await view.user.type(within(dialog).getByLabelText('진행사항'), ' 버릴 글')

    // when: Esc를 누른다
    await view.user.keyboard('{Escape}')
    // then: 편집만 닫히고 진행사항은 그대로이며 팝업이 열려 있고 요청이 없다
    expect(within(detail()).queryByLabelText('진행사항')).not.toBeInTheDocument()
    expect(fieldValue(detail(), '진행사항')).toHaveTextContent(/^킥오프 미팅$/)
    expect(update).not.toHaveBeenCalled()

    // when: 다시 Esc를 누른다
    await view.user.keyboard('{Escape}')
    // then: 팝업이 닫힌다
    expect(queryDetail()).not.toBeInTheDocument()
  })

  // "취소"는 입력을 버리고 요청 없이 그 칸 편집만 닫는다.
  // 테스트 코드: AC-140
  it('discards the input and closes only the field with the cancel button', async () => {
    // given: 진행사항 편집에 " 버릴 글"을 쓴 Action A 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    await view.user.type(within(dialog).getByLabelText('진행사항'), ' 버릴 글')

    // when: "진행사항 취소"를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 취소' }))

    // then: 편집이 닫히고 진행사항은 그대로이며 팝업은 열려 있고 요청이 없다
    expect(within(detail()).queryByLabelText('진행사항')).not.toBeInTheDocument()
    expect(fieldValue(detail(), '진행사항')).toHaveTextContent(/^킥오프 미팅$/)
    expect(queryDetail()).toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })

  // 값을 바꾸지 않고 "저장"하면 요청 없이 편집만 닫힌다.
  // 테스트 코드: AC-140
  it('closes the editor without a request when nothing changed', async () => {
    // given: 진행사항 편집을 연 Action A 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))

    // when: 아무것도 바꾸지 않고 "진행사항 저장"을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))

    // then: 편집이 닫히고 요청이 없으며 팝업은 열려 있다
    await waitFor(() => expect(within(detail()).queryByLabelText('진행사항')).not.toBeInTheDocument())
    expect(update).not.toHaveBeenCalled()
  })
})

describe('저장 실패와 저장 중', () => {
  // 응답 전에는 닫기·삭제가 꺼지고 Esc가 무시되며, 거절되면 칸 아래 서버 문구가 보이고 입력이 남는다.
  // 테스트 코드: AC-141
  it('disables close and delete and ignores Escape while saving, then shows the server message under the field', async () => {
    // given: 열어 둔 사이 A가 다른 곳에서 삭제됐고 저장 응답을 붙들어 둔다
    const { view, action, dialog } = await openA()
    await gateway.actions.remove(action.id)
    const original = gateway.actions.update.bind(gateway.actions)
    const { gate, release } = makeGate()
    vi.spyOn(gateway.actions, 'update').mockImplementation(async (...args) => {
      await gate
      return original(...args)
    })
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const input = within(dialog).getByLabelText('진행사항')
    await view.user.clear(input)

    // when: 진행사항을 고쳐 "진행사항 저장"을 누르고 응답 전에 Esc를 누른다
    await view.user.type(input, '사라진 Action 수정')
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))
    // then: 응답 전에는 진행사항 칸·저장·취소·닫기·삭제가 꺼져 있다
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '닫기' })).toBeDisabled())
    expect(within(dialog).getByRole('button', { name: '삭제' })).toBeDisabled()
    expect(within(dialog).getByLabelText('진행사항')).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: '진행사항 저장' })).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: '진행사항 취소' })).toBeDisabled()
    await view.user.keyboard('{Escape}')
    // then: Esc로 팝업이 닫히지 않는다
    expect(queryDetail()).toBeInTheDocument()

    // when: 응답이 온다
    release()
    // then: 진행사항 칸 아래 서버 문구가 보이고 편집과 입력한 글이 그대로다
    expect(await within(dialog).findByText('Action을 찾을 수 없습니다.')).toBeVisible()
    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('사라진 Action 수정')
    await waitFor(() => expect(within(dialog).getByLabelText('진행사항')).toBeEnabled())
    expect(within(dialog).getByRole('button', { name: '진행사항 저장' })).toBeEnabled()
    expect(within(dialog).getByRole('button', { name: '진행사항 취소' })).toBeEnabled()
  })
})

describe('저장 뒤 검색 조건에서 빠진 Action', () => {
  // 검색 조건에서 빠져도 팝업은 열린 채 새 값을 보이고, 닫으면 빈 결과 문구가 보인다.
  // 테스트 코드: AC-143
  it('keeps the popup open with the new value after the action leaves the search result', async () => {
    // given: 키워드 "킥오프"로 검색해 A 한 행만 남기고 그 상세 팝업을 연다
    const view = await openActionsTab()
    await addAction(view, A_INPUT)
    const search = screen.getByRole('search', { name: 'Action 검색' })
    await view.user.type(within(search).getByLabelText('키워드'), '킥오프')
    await view.user.click(within(search).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(bodyRows(view.table)).toHaveLength(1))
    const dialog = await openDetail(view, '킥오프 미팅')

    // when: 진행사항을 "착수 회의"로 고쳐 "진행사항 저장"을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const input = within(dialog).getByLabelText('진행사항')
    await view.user.clear(input)
    await view.user.type(input, '착수 회의')
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))

    // then: 목록은 조건에서 빠졌지만 팝업은 열린 채 새 값을 보인다
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeInTheDocument()
    expect(fieldValue(detail(), '진행사항')).toHaveTextContent('착수 회의')

    // when: 팝업을 닫는다
    await view.user.click(within(detail()).getByRole('button', { name: '닫기' }))
    // then: 표 자리에 빈 결과 문구가 보인다
    expect(queryDetail()).not.toBeInTheDocument()
    expect(screen.getByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
  })
})

describe('유형 이름이 바뀐 뒤의 다른 칸 저장', () => {
  // 유형이 아닌 칸을 저장하면 이름이 바뀌었어도 원래 id로 보내고 새 유형을 만들지 않는다.
  // 테스트 코드: AC-087
  it('sends the original type id and creates no type when another field is saved after an admin renamed the type', async () => {
    // given: A(유형 미팅)의 상세 팝업을 연 뒤 admin이 "미팅"을 "고객 미팅"으로 바꿨다
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    const typesBefore = await gateway.actionTypes.list()
    expect(dialog).toBeVisible()
    await defaultMock.signInAs(USER_ID.root)
    await gateway.actionTypes.rename(seedActionTypeId('미팅'), '고객 미팅')
    await defaultMock.signInAs(USER_ID.kim)
    await view.client.invalidateQueries()
    await waitFor(() => expect(view.client.isFetching()).toBe(0))

    // when: KIM이 진행사항을 고쳐 "진행사항 저장"을 누른다
    await view.user.click(within(detail()).getByRole('button', { name: '진행사항 수정' }))
    const progress = within(detail()).getByLabelText('진행사항')
    await view.user.clear(progress)
    await view.user.type(progress, '다른 진행')
    await view.user.click(within(detail()).getByRole('button', { name: '진행사항 저장' }))

    // then: 요청의 유형은 원래 id이고 유형 수가 그대로다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].type).toEqual({ id: seedActionTypeId('미팅') })
    expect(await gateway.actionTypes.list()).toHaveLength(typesBefore.length)
    // then: 저장 뒤 팝업 유형 값은 "고객 미팅"이다
    await waitFor(() => expect(fieldValue(detail(), '유형')).toHaveTextContent('고객 미팅'))
  })
})
