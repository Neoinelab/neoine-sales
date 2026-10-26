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
 * (`closePreviousNextActionId`)이고 서버가 같은 트랜잭션에서 처리한다(R4 AC4-8~10).
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

describe('채우기 버튼과 종료 체크박스 (AC4-8)', () => {
  it('has no checkbox before the fill button is pressed', async () => {
    const { dialog } = await openDeal1()

    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).not.toBeInTheDocument()
  })

  it('fills the progress and turns the checkbox on inside the previous update card', async () => {
    const { user, dialog } = await openDeal1()

    await fillAndPress(user, dialog)

    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
    const checkbox = within(dialog).getByRole('checkbox', { name: CHECKBOX })
    expect(checkbox).toBeChecked()
    expect(within(within(dialog).getByRole('complementary', { name: '이전 Update' })).getByRole('checkbox', { name: CHECKBOX })).toBe(checkbox)
  })

  it('lets the user turn the checkbox off and on again', async () => {
    const { user, dialog } = await openDeal1()
    await fillAndPress(user, dialog)
    const checkbox = within(dialog).getByRole('checkbox', { name: CHECKBOX })

    await user.click(checkbox)
    expect(checkbox).not.toBeChecked()

    await user.click(checkbox)
    expect(checkbox).toBeChecked()
  })

  it('sends no close id when the checkbox is off', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)
    await user.click(within(dialog).getByRole('checkbox', { name: CHECKBOX }))

    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })

  it('sends no close id when the fill button was never pressed', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form } = await openDeal1()
    await user.type(within(form).getByLabelText('진행사항'), '직접 입력')

    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })

  it('sends the basis action id in the same create request when the checkbox is on', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const changeStatus = vi.spyOn(gateway.actions, 'changeNextActionStatus')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)

    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toMatchObject({ closePreviousNextActionId: KIM_BASIS_ID, progress: '계약서 초안 검토' })
    expect(changeStatus).not.toHaveBeenCalled()
  })
})

describe('상태를 바꿀 수 없거나 바꿀 필요가 없을 때 (AC4-9)', () => {
  it('shows no checkbox and no hint when the previous next action is already closed', async () => {
    const real = gateway.actions.list.bind(gateway.actions)
    vi.spyOn(gateway.actions, 'list').mockImplementation(async (code, query) =>
      (await real(code, query)).map((a) => (a.id === KIM_BASIS_ID ? { ...a, nextActionStatus: 'done' as const, nextActionClosedAt: '2026-10-14T10:00:00+09:00' } : a)),
    )
    const { user, dialog } = await openDeal1()

    await fillAndPress(user, dialog)

    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).not.toBeInTheDocument()
    expect(within(dialog).queryByText(OTHERS_HINT)).not.toBeInTheDocument()
  })

  it('shows the hint instead of the checkbox for another sales users next action', async () => {
    const { user, dialog } = await openForm(3, '미래전자 EDR 교체')

    await fillAndPress(user, dialog)

    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('데모 피드백 수렴')
    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).not.toBeInTheDocument()
    expect(within(dialog).getByText(OTHERS_HINT)).toBeVisible()
  })

  it('does not send a close id for another sales users next action', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openForm(3, '미래전자 EDR 교체')
    await fillAndPress(user, dialog)

    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })

  it('shows the checkbox to an admin for anyones next action', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openForm(3, '미래전자 EDR 교체', 'admin')
    await fillAndPress(user, dialog)

    expect(within(dialog).getByRole('checkbox', { name: CHECKBOX })).toBeChecked()
    expect(within(dialog).queryByText(OTHERS_HINT)).not.toBeInTheDocument()

    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBe(PARK_BASIS_ID)
  })
})

describe('저장 결과 (AC4-10)', () => {
  it('announces the closing and shows the previous row as 종료(수행)', async () => {
    const { user, dialog, form, table } = await openDeal1()
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
    await fillAndPress(user, dialog)

    await register(user, form)

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다. 이전 Next Action을 종료(수행)로 바꿨습니다.')).toBeVisible()
    await waitFor(() => expect(isClosedAsDone(rowWith(table, '최종 가격 협의'))).toBe(true))
  })

  it('keeps the plain notice and the previous row open when the checkbox is off', async () => {
    const { user, dialog, form, table } = await openDeal1()
    await fillAndPress(user, dialog)
    await user.click(within(dialog).getByRole('checkbox', { name: CHECKBOX }))

    await register(user, form)

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
    expect(screen.queryByText(/이전 Next Action을 종료\(수행\)로 바꿨습니다/)).not.toBeInTheDocument()
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
  })

  it('leaves the closing line and the registration line in the history (closing first, registration newest)', async () => {
    const { user, dialog, form } = await openDeal1()
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    const before = (await gateway.history.list(code, {})).length
    await fillAndPress(user, dialog)

    await register(user, form)

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(before + 2)
    expect(history[0]).toMatchObject({ target: 'Action' })
    expect(history[1]).toMatchObject({ target: 'Next Action', after: '종료(수행)' })
  })

  it('changes nothing when the dialog is cancelled after filling', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, table } = await openDeal1()
    await fillAndPress(user, dialog)

    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
  })

  it('keeps the form open with the server message and the input when the previous next action changed meanwhile', async () => {
    const { user, dialog, form, table } = await openDeal1()
    await fillAndPress(user, dialog)
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    await gateway.actions.create(code, { type: { name: '미팅' }, progress: '그 사이 추가', nextAction: '다른 일정', dueDate: '2026-11-01', memo: '' })
    const count = (await gateway.actions.list(code, {})).length
    await user.type(within(form).getByLabelText('Memo'), '남아 있어야 하는 메모')

    await register(user, form)

    expect(await within(dialog).findByText(CHANGED)).toBeVisible()
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeInTheDocument()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
    expect(within(form).getByLabelText('Memo')).toHaveValue('남아 있어야 하는 메모')
    expect(await gateway.actions.list(code, {})).toHaveLength(count)
    expect(isStillOpen(rowWith(table, '최종 가격 협의'))).toBe(true)
  })

  it('keeps the form open with the server message on a 403', async () => {
    const forbidden = new ApiError(403, {
      type: 'https://neoine-sales.example/problems/forbidden',
      title: 'forbidden',
      status: 403,
      detail: '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.',
    })
    vi.spyOn(gateway.actions, 'create').mockRejectedValue(forbidden)
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)

    await register(user, form)

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.')
    expect(within(form).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
  })
})

describe('409 뒤 복구와 체크 유지 (리뷰 지적)', () => {
  it('shows the new basis row after closing and reopening, and then succeeds closing it', async () => {
    const { user, dialog, form, table } = await openDeal1()
    await fillAndPress(user, dialog)
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    const added = await gateway.actions.create(code, { type: { name: '미팅' }, progress: '그 사이 추가', nextAction: '다른 일정', dueDate: '2026-11-01', memo: '' })
    await register(user, form)
    expect(await within(dialog).findByText(CHANGED)).toBeVisible()

    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const reopened = await screen.findByRole('dialog', { name: 'Action 추가' })

    await waitFor(() => expect(within(within(reopened).getByRole('complementary', { name: '이전 Update' })).getByText('다른 일정')).toBeVisible())
    await user.click(within(reopened).getByRole('button', { name: FILL }))
    expect(within(reopened).getByLabelText('진행사항')).toHaveValue('다른 일정')
    await register(user, within(reopened).getByRole('form', { name: 'Action 추가' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다. 이전 Next Action을 종료(수행)로 바꿨습니다.')).toBeVisible()
    const closed = (await gateway.actions.list(code, {})).find((a) => a.id === added.id)
    expect(closed?.nextActionStatus).toBe('done')
    await waitFor(() => expect(isClosedAsDone(rowWith(table, '그 사이 추가'))).toBe(true))
  })

  it('keeps the checkbox off when the fill button is pressed again', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)
    await user.click(within(dialog).getByRole('checkbox', { name: CHECKBOX }))

    await fillAndPress(user, dialog)

    expect(within(dialog).getByRole('checkbox', { name: CHECKBOX })).not.toBeChecked()
    await register(user, form)
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })
})

describe('카드가 바뀐 뒤의 채움·체크 (재리뷰 Major)', () => {
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

  it('sends the filled row id when the card has not changed (A)', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form } = await openDeal1()
    await fillAndPress(user, dialog)

    await register(user, form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBe(KIM_BASIS_ID)
  })

  it('clears the checkbox and tells the user to fill again once the card shows another row', async () => {
    const { dialog } = await cardChangedAfter409()

    expect(within(dialog).getByText(CARD_CHANGED)).toBeVisible()
    // 카드가 바뀌면 채움이 무효가 되어 종료 체크박스 자체가 사라진다.
    expect(within(dialog).queryByRole('checkbox', { name: CHECKBOX })).toBeNull()
  })

  it('does not send the new basis id nor close it, and keeps the typed progress', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, dialog, form, code, added } = await cardChangedAfter409()
    create.mockClear()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')

    await user.click(within(form).getByRole('button', { name: '등록' }))

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(dialog).not.toBeInTheDocument()
    const stillOpen = (await gateway.actions.list(code, {})).find((a) => a.id === added.id)
    expect(stillOpen?.nextActionStatus).toBe('open')
  })
})

describe('이전 Update 카드의 기준 행 (서버 정의와 같다)', () => {
  it('shows the latest next action row, ties of the same acted time broken by the higher id', async () => {
    const { user, client } = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    const base = { type: { name: '미팅' }, progress: '같은 시각', dueDate: '2026-11-01', memo: '' }
    await gateway.actions.create(code, { ...base, nextAction: '먼저 저장한 것' })
    const later = await gateway.actions.create(code, { ...base, nextAction: '나중에 저장한 것' }) // 같은 Fake 시각, 더 큰 id
    await client.invalidateQueries({ queryKey: keys.actions(code) })
    await screen.findByRole('table', { name: 'Action 목록' })

    await user.click(await screen.findByRole('button', { name: 'Action 추가' }))
    const dialog = await screen.findByRole('dialog', { name: 'Action 추가' })

    await waitFor(() => expect(within(within(dialog).getByRole('complementary', { name: '이전 Update' })).getByText('나중에 저장한 것')).toBeVisible())
    await user.click(within(dialog).getByRole('button', { name: FILL }))
    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('나중에 저장한 것')
    await user.type(within(dialog).getByLabelText('유형'), '미팅')
    const create = vi.spyOn(gateway.actions, 'create')
    await user.click(within(dialog).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBe(later.id)
  })
})
