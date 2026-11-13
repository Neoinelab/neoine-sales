import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/**
 * 이전 Update 카드의 "이전 Next Action을 진행사항에 채우기"는 진행사항을 채우고, 닫을 수 있으면
 * "저장 시 이전 Next Action을 종료(수행)로 바꿈" 체크(기본 켜짐)를 보인다. 저장은 요청 한 번
 * (`closePreviousNextActionId`)이고 서버가 같은 트랜잭션에서 처리한다.
 * 시드: Deal 1(한빛은행 ITDR 도입)의 기준 행은 김영업의 Open Next Action '계약서 초안 검토'(id 4),
 * Deal 3(미래전자 EDR 교체)의 기준 행은 박영업의 Open Next Action '데모 피드백 수렴'(id 11).
 */
afterEach(() => vi.restoreAllMocks())

type View = Awaited<ReturnType<typeof renderAt>>

const CHECKBOX = '저장 시 이전 Next Action을 종료(수행)로 바꿈'
const OTHERS_HINT = '다른 담당자의 Next Action이라 상태는 바꾸지 않습니다.'
const FILL = '이전 Next Action을 진행사항에 채우기'
const CHANGED = '이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요.'
const KIM_BASIS_ID = 4
const PARK_BASIS_ID = 11

async function openForm(no: number, title: string, role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(no, '?tab=actions'), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  await view.user.click(screen.getByRole('button', { name: 'Action 추가' }))
  const dialog = await screen.findByRole('dialog', { name: 'Action 추가' })
  const form = within(dialog).getByRole('form', { name: 'Action 추가' })
  return { ...view, table, dialog, form }
}

const openDeal1 = () => openForm(1, '한빛은행 ITDR 도입')

async function fillAndPress(user: View['user'], dialog: HTMLElement) {
  await user.click(within(dialog).getByRole('button', { name: FILL }))
}

async function register(user: View['user'], form: HTMLElement) {
  await user.type(within(form).getByLabelText('유형'), '미팅')
  await user.click(within(form).getByRole('button', { name: '등록' }))
}

const rowWith = (table: HTMLElement, text: string) => within(table).getAllByRole('row').find((r) => r.textContent?.includes(text)) as HTMLElement

/** 기준 행의 상태 칸: Open이면 "종료(수행)" 버튼이 있고, 종료(수행)이면 "Open으로" 버튼이 있다. */
const isStillOpen = (row: HTMLElement) =>
  within(row).queryByRole('button', { name: '종료(수행)' }) !== null && within(row).queryByRole('button', { name: 'Open으로' }) === null
const isClosedAsDone = (row: HTMLElement) =>
  within(row).queryByRole('button', { name: '종료(수행)' }) === null && within(row).queryByRole('button', { name: 'Open으로' }) !== null

describe('채우기 버튼과 종료 체크박스', () => {
  // 채우기 버튼을 누르기 전에는 종료 체크박스가 없다.
  // 테스트 코드: AC-081
  it('has no checkbox before the fill button is pressed', async () => {
    // when: sales가 Deal 1의 추가 팝업을 연다
    const { dialog } = await openDeal1()

    // then: 종료 체크박스가 없다
    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).not.toBeInTheDocument()
  })

  // 채우면 진행사항이 채워지고 이전 Update 카드 안에 체크가 켜진 채 나타난다.
  // 테스트 코드: AC-081
  it('fills the progress and turns the checkbox on inside the previous update card', async () => {
    // given: sales가 Deal 1의 추가 팝업을 연다
    const { user, dialog } = await openDeal1()

    // when: 이전 Next Action 채우기를 누른다
    await fillAndPress(user, dialog)

    // then: 진행사항이 이전 Next Action으로 채워진다
    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
    // then: 이전 Update 카드 안에 체크박스가 켜진 채 있다
    const checkbox = within(dialog).getByRole('checkbox', { name: CHECKBOX })
    expect(checkbox).toBeChecked()
    expect(within(within(dialog).getByRole('complementary', { name: '이전 Update' })).getByRole('checkbox', { name: CHECKBOX })).toBe(checkbox)
  })

  // 체크는 껐다 다시 켤 수 있다.
  // 테스트 코드: AC-081
  it('lets the user turn the checkbox off and on again', async () => {
    // given: 채우기를 누른 추가 팝업
    const { user, dialog } = await openDeal1()
    await fillAndPress(user, dialog)
    const checkbox = within(dialog).getByRole('checkbox', { name: CHECKBOX })

    // when: 체크를 끈다
    await user.click(checkbox)
    // then: 체크가 꺼진다
    expect(checkbox).not.toBeChecked()

    // when: 다시 켠다
    await user.click(checkbox)
    // then: 체크가 켜진다
    expect(checkbox).toBeChecked()
  })

  // 체크를 끄면 닫을 id를 보내지 않는다.
  // 테스트 코드: AC-081
  it('sends no close id when the checkbox is off', async () => {
    // given: 채우고 체크를 끈 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)
    await user.click(within(dialog).getByRole('checkbox', { name: CHECKBOX }))

    // when: 등록한다
    await register(user, form)

    // then: 요청이 한 번 가고 닫을 id가 없다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })

  // 채우기를 누르지 않았으면 닫을 id를 보내지 않는다.
  // 테스트 코드: AC-081
  it('sends no close id when the fill button was never pressed', async () => {
    // given: 직접 진행사항을 입력한 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form } = await openDeal1()
    await user.type(within(form).getByLabelText('진행사항'), '직접 입력')

    // when: 등록한다
    await register(user, form)

    // then: 요청이 한 번 가고 닫을 id가 없다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })

  // 체크가 켜져 있으면 같은 등록 요청에 기준 행 id를 싣는다.
  // 테스트 코드: AC-081
  it('sends the basis action id in the same create request when the checkbox is on', async () => {
    // given: 채운 추가 팝업(등록·상태 변경 요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const changeStatus = vi.spyOn(gateway.actions, 'changeNextActionStatus')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)

    // when: 등록한다
    await register(user, form)

    // then: 등록 요청 하나에 기준 행 id와 채운 진행사항이 실린다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toMatchObject({ closePreviousNextActionId: KIM_BASIS_ID, progress: '계약서 초안 검토' })
    // then: 상태 변경 요청은 따로 가지 않는다
    expect(changeStatus).not.toHaveBeenCalled()
  })
})

describe('상태를 바꿀 수 없거나 바꿀 필요가 없을 때', () => {
  // 이미 종료된 이전 Next Action에는 체크도 안내도 없다.
  // 테스트 코드: AC-082
  it('shows no checkbox and no hint when the previous next action is already closed', async () => {
    // given: 기준 행이 이미 종료로 읽히는 Deal 1
    const real = gateway.actions.list.bind(gateway.actions)
    vi.spyOn(gateway.actions, 'list').mockImplementation(async (code, query) =>
      (await real(code, query)).map((a) => (a.id === KIM_BASIS_ID ? { ...a, nextActionStatus: 'done' as const, nextActionClosedOn: '2026-10-14' } : a)),
    )
    // given: 추가 팝업을 연다
    const { user, dialog } = await openDeal1()

    // when: 이전 Next Action 채우기를 누른다
    await fillAndPress(user, dialog)

    // then: 진행사항은 채워지고 체크박스와 안내가 없다
    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).not.toBeInTheDocument()
    expect(within(dialog).queryByText(OTHERS_HINT)).not.toBeInTheDocument()
  })

  // 다른 sales의 Next Action에는 체크 대신 안내를 보인다.
  // 테스트 코드: AC-082
  it('shows the hint instead of the checkbox for another sales users next action', async () => {
    // given: 다른 sales의 기준 행이 있는 Deal 3의 추가 팝업
    const { user, dialog } = await openForm(3, '미래전자 EDR 교체')

    // when: 이전 Next Action 채우기를 누른다
    await fillAndPress(user, dialog)

    // then: 진행사항이 채워지고 체크박스가 없으며 안내가 보인다
    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('데모 피드백 수렴')
    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).not.toBeInTheDocument()
    expect(within(dialog).getByText(OTHERS_HINT)).toBeVisible()
  })

  // 다른 sales의 Next Action이면 닫을 id를 보내지 않는다.
  // 테스트 코드: AC-082
  it('does not send a close id for another sales users next action', async () => {
    // given: 다른 sales의 기준 행이 있는 Deal 3의 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openForm(3, '미래전자 EDR 교체')
    // when: 채우고 등록한다
    await fillAndPress(user, dialog)

    // then: 요청에 닫을 id가 없다
    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })

  // admin에게는 남의 Next Action에도 체크가 나오고 id를 보낸다.
  // 테스트 코드: AC-082
  it('shows the checkbox to an admin for anyones next action', async () => {
    // given: admin이 Deal 3의 추가 팝업을 열고(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openForm(3, '미래전자 EDR 교체', 'admin')
    // when: 이전 Next Action 채우기를 누른다
    await fillAndPress(user, dialog)

    // then: 체크가 켜져 있고 안내가 없다
    expect(within(dialog).getByRole('checkbox', { name: CHECKBOX })).toBeChecked()
    expect(within(dialog).queryByText(OTHERS_HINT)).not.toBeInTheDocument()

    // when: 등록한다
    await register(user, form)

    // then: 요청에 기준 행 id가 실린다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBe(PARK_BASIS_ID)
  })
})

describe('저장 결과', () => {
  // 등록하면 종료 알림이 붙고 이전 행이 종료(수행)로 보인다.
  // 테스트 코드: AC-081
  it('announces the closing and shows the previous row as 종료(수행)', async () => {
    // given: 이전 행이 Open인 Deal 1에서 채운 추가 팝업
    const { user, dialog, form, table } = await openDeal1()
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
    await fillAndPress(user, dialog)

    // when: 등록한다
    await register(user, form)

    // then: 팝업이 닫힌다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    // then: 알림에 이전 Next Action 종료 문구가 붙는다
    expect(screen.getByText('Action이 등록되었습니다. 이전 Next Action을 종료(수행)로 바꿨습니다.')).toBeVisible()
    // then: 이전 행이 종료(수행)로 보인다
    await waitFor(() => expect(isClosedAsDone(rowWith(table, '최종 가격 협의'))).toBe(true))
  })

  // 체크를 끄고 등록하면 기본 알림이고 이전 행은 Open 그대로다.
  // 테스트 코드: AC-081
  it('keeps the plain notice and the previous row open when the checkbox is off', async () => {
    // given: 채우고 체크를 끈 추가 팝업
    const { user, dialog, form, table } = await openDeal1()
    await fillAndPress(user, dialog)
    await user.click(within(dialog).getByRole('checkbox', { name: CHECKBOX }))

    // when: 등록한다
    await register(user, form)

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    // then: 기본 등록 알림이고 종료 문구가 없다
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
    expect(screen.queryByText(/이전 Next Action을 종료\(수행\)로 바꿨습니다/)).not.toBeInTheDocument()
    // then: 이전 행은 Open이다
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
  })

  // 이력에는 종료 줄 다음에 등록 줄이 남는다.
  // 테스트 코드: AC-081
  it('leaves the closing line and the registration line in the history (closing first, registration newest)', async () => {
    // given: 채운 추가 팝업과 등록 전 History 건수
    const { user, dialog, form } = await openDeal1()
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    const before = (await gateway.history.list(code, {})).length
    await fillAndPress(user, dialog)

    // when: 등록한다
    await register(user, form)

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    // then: History가 2건 늘고 맨 위가 Action 등록 줄이다
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(before + 2)
    expect(history[0]).toMatchObject({ target: 'Action' })
    // then: 그 아래가 Next Action 종료(수행) 줄이다
    expect(history[1]).toMatchObject({ target: 'Next Action', after: '종료(수행)' })
  })

  // 채운 뒤 취소하면 아무것도 바뀌지 않는다.
  // 테스트 코드: AC-085
  it('changes nothing when the dialog is cancelled after filling', async () => {
    // given: 채운 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, table } = await openDeal1()
    await fillAndPress(user, dialog)

    // when: 취소를 누른다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 팝업이 닫히고 등록 요청이 없다
    expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
    // then: 이전 행은 Open이다
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
  })

  // 그 사이 기준 행이 바뀌면 서버 문구를 보이고 폼과 입력을 유지한다.
  // 테스트 코드: AC-083
  it('keeps the form open with the server message and the input when the previous next action changed meanwhile', async () => {
    // given: 채운 추가 팝업에서 그 사이 다른 Next Action이 등록되었다
    const { user, dialog, form, table } = await openDeal1()
    await fillAndPress(user, dialog)
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    await gateway.actions.create(code, { type: { name: '미팅' }, progress: '그 사이 추가', nextAction: '다른 일정', dueDate: '2026-11-01', memo: '' })
    const count = (await gateway.actions.list(code, {})).length
    // given: 메모를 입력했다
    await user.type(within(form).getByLabelText('Memo'), '남아 있어야 하는 메모')

    // when: 등록한다
    await register(user, form)

    // then: 서버 문구가 팝업 안에 보인다
    expect(await within(dialog).findByText(CHANGED)).toBeVisible()
    // then: 팝업·진행사항·메모가 그대로다
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeInTheDocument()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
    expect(within(form).getByLabelText('Memo')).toHaveValue('남아 있어야 하는 메모')
    // then: 새 Action은 등록되지 않았고 이전 행은 Open이다
    expect(await gateway.actions.list(code, {})).toHaveLength(count)
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
  })

  // 403이면 서버 문구를 보이고 폼을 유지한다.
  // 테스트 코드: AC-083
  it('keeps the form open with the server message on a 403', async () => {
    // given: 등록이 403으로 거절되도록 하고 채운 추가 팝업을 연다
    const forbidden = new ApiError(403, {
      type: 'https://neoine-sales.example/problems/forbidden',
      title: 'forbidden',
      status: 403,
      detail: '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.',
    })
    vi.spyOn(gateway.actions, 'create').mockRejectedValue(forbidden)
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)

    // when: 등록한다
    await register(user, form)

    // then: 팝업 안에 서버 문구가 보인다
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.')
    // then: 진행사항이 그대로다
    expect(within(form).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
  })
})

describe('409 뒤 복구와 체크 유지', () => {
  // 409 뒤 팝업을 닫고 다시 열면 새 기준 행을 닫는 등록이 성공한다.
  // 테스트 코드: AC-083
  it('shows the new basis row after closing and reopening, and then succeeds closing it', async () => {
    // given: 채운 추가 팝업에서 그 사이 다른 Next Action이 등록되어 409가 났다
    const { user, dialog, form, table } = await openDeal1()
    await fillAndPress(user, dialog)
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    const added = await gateway.actions.create(code, { type: { name: '미팅' }, progress: '그 사이 추가', nextAction: '다른 일정', dueDate: '2026-11-01', memo: '' })
    // when: 등록한다
    await register(user, form)
    // then: 409 문구가 보인다
    expect(await within(dialog).findByText(CHANGED)).toBeVisible()

    // when: 팝업을 닫고 다시 열어 새 기준 행을 채워 등록한다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const reopened = await screen.findByRole('dialog', { name: 'Action 추가' })

    // then: 카드가 새 기준 행을 보인다
    await waitFor(() => expect(within(within(reopened).getByRole('complementary', { name: '이전 Update' })).getByText('다른 일정')).toBeVisible())
    await user.click(within(reopened).getByRole('button', { name: FILL }))
    // then: 진행사항이 새 기준 행으로 채워진다
    expect(within(reopened).getByLabelText('진행사항')).toHaveValue('다른 일정')
    await register(user, within(reopened).getByRole('form', { name: 'Action 추가' }))

    // then: 팝업이 닫히고 종료 알림이 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다. 이전 Next Action을 종료(수행)로 바꿨습니다.')).toBeVisible()
    // then: 새 기준 행이 종료(수행)가 된다
    const closed = (await gateway.actions.list(code, {})).find((a) => a.id === added.id)
    expect(closed?.nextActionStatus).toBe('done')
    await waitFor(() => expect(isClosedAsDone(rowWith(table, '그 사이 추가'))).toBe(true))
  })

  // 끈 체크는 채우기를 다시 눌러도 꺼진 채다.
  // 테스트 코드: AC-081
  it('keeps the checkbox off when the fill button is pressed again', async () => {
    // given: 채우고 체크를 끈 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)
    await user.click(within(dialog).getByRole('checkbox', { name: CHECKBOX }))

    // when: 채우기를 다시 누른다
    await fillAndPress(user, dialog)

    // then: 체크가 꺼져 있다
    expect(within(dialog).getByRole('checkbox', { name: CHECKBOX })).not.toBeChecked()
    // when: 등록한다
    await register(user, form)
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 닫을 id를 보내지 않는다
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })
})

describe('카드가 바뀐 뒤의 채움·체크', () => {
  const CARD_CHANGED = '이전 Update가 바뀌었습니다. 확인 후 다시 채우세요.'
  const other = { type: { name: '미팅' }, progress: '그 사이 추가', nextAction: '다른 일정', dueDate: '2026-11-01', memo: '' }

  async function cardChangedAfter409() {
    const view = await openDeal1()
    const { user, dialog, form, client } = view
    await fillAndPress(user, dialog)
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    const added = await gateway.actions.create(code, other)
    await register(user, form)
    expect(await within(dialog).findByText(CHANGED)).toBeVisible()
    await client.invalidateQueries({ queryKey: keys.actions(code) })
    await waitFor(() => expect(within(within(dialog).getByRole('complementary', { name: '이전 Update' })).getByText('다른 일정')).toBeVisible())
    return { ...view, code, added }
  }

  // 카드가 바뀌지 않았으면 채운 행 id를 보낸다.
  // 테스트 코드: AC-081
  it('sends the filled row id when the card has not changed', async () => {
    // given: 채운 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)

    // when: 등록한다
    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 요청에 채운 행 id가 실린다
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBe(KIM_BASIS_ID)
  })

  // 카드가 다른 행으로 바뀌면 체크가 사라지고 다시 채우라고 알린다.
  // 테스트 코드: AC-083
  it('clears the checkbox and tells the user to fill again once the card shows another row', async () => {
    // when: 채운 뒤 카드가 다른 행으로 바뀐 추가 팝업을 만든다
    const { dialog } = await cardChangedAfter409()

    // then: "이전 Update가 바뀌었습니다" 안내가 보인다
    expect(within(dialog).getByText(CARD_CHANGED)).toBeVisible()
    // 카드가 바뀌면 채움이 무효가 되어 종료 체크박스 자체가 사라진다.
    // then: 종료 체크박스가 없다
    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).toBeNull()
  })

  // 카드가 바뀐 뒤에는 어느 id도 보내지 않고 입력한 진행사항은 그대로다.
  // 테스트 코드: AC-083
  it('does not send the new basis id nor close it, and keeps the typed progress', async () => {
    // given: 채운 뒤 카드가 다른 행으로 바뀐 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form, code, added } = await cardChangedAfter409()
    create.mockClear()
    // then: 진행사항은 채운 그대로다
    expect(within(form).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')

    // when: 등록한다
    await user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 등록 요청이 한 번 간다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 닫을 id가 없다
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
    // then: 팝업이 닫히고 새 기준 행은 Open 그대로다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(dialog).not.toBeInTheDocument()
    const stillOpen = (await gateway.actions.list(code, {})).find((a) => a.id === added.id)
    expect(stillOpen?.nextActionStatus).toBe('open')
  })
})

describe('이전 Update 카드의 기준 행 (서버 정의와 같다)', () => {
  // 이전 Update 카드는 가장 최근 Next Action 행이고 같은 시각이면 id가 큰 행이다.
  // 테스트 코드: AC-081
  it('shows the latest next action row, ties of the same acted time broken by the higher id', async () => {
    // given: 같은 Fake 시각에 Next Action 행 두 건이 등록된 Deal 1
    const { user, client } = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    const base = { type: { name: '미팅' }, progress: '같은 시각', dueDate: '2026-11-01', memo: '' }
    await gateway.actions.create(code, { ...base, nextAction: '먼저 저장한 것' })
    const later = await gateway.actions.create(code, { ...base, nextAction: '나중에 저장한 것' }) // 같은 Fake 시각, 더 큰 id
    await client.invalidateQueries({ queryKey: keys.actions(code) })
    await screen.findByRole('table', { name: 'Action 목록' })

    // when: 추가 팝업을 열고 카드를 채워 등록한다
    await user.click(await screen.findByRole('button', { name: 'Action 추가' }))
    const dialog = await screen.findByRole('dialog', { name: 'Action 추가' })

    // then: 카드가 나중에 저장한 행을 보인다
    await waitFor(() => expect(within(within(dialog).getByRole('complementary', { name: '이전 Update' })).getByText('나중에 저장한 것')).toBeVisible())
    await user.click(within(dialog).getByRole('button', { name: FILL }))
    // then: 진행사항이 그 행으로 채워진다
    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('나중에 저장한 것')
    await user.type(within(dialog).getByLabelText('유형'), '미팅')
    const create = vi.spyOn(gateway.actions, 'create')
    await user.click(within(dialog).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 요청의 닫을 id는 큰 id의 행이다
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBe(later.id)
  })
})
