import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { A_INPUT, addAction, DETAIL, openActionsTab, rowWith } from '../../../test/actionDetail'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'

beforeEach(() => resetMock({ now: '2026-11-13T14:30:00+09:00' }))
afterEach(() => { vi.restoreAllMocks(); resetMock({ now: null }) })

async function setup() {
  const view = await openActionsTab()
  const action = await addAction(view, A_INPUT)
  return { ...view, action, row: rowWith(view.table, '킥오프 미팅') }
}

describe('Actions 목록 인라인 수정', () => {
  // 테스트 코드: AC-163
  it.each([
    { opener: '진행사항', label: '진행사항', draft: '버릴 진행사항' },
    { opener: 'Next Action · Due Date', label: 'Next Action', draft: '버릴 Next Action' },
    { opener: 'Due Date', label: 'Due Date', draft: '20300101' },
  ])('$label 편집 중 다른 영역으로 포커스를 옮기면 저장 없이 취소한다', async (field) => {
    // given: Actions 표에서 값을 편집하고 있다
    const { user, row } = await setup()
    const update = vi.spyOn(gateway.actions, 'update')
    await user.click(within(row).getByRole('button', { name: `${field.opener} 수정` }))
    const input = within(row).getByLabelText<HTMLInputElement | HTMLTextAreaElement>(field.label)
    const initial = input.value
    await user.clear(input)
    await user.type(input, field.draft)
    const outside = screen.getByRole('tab', { name: 'Actions' })

    // when: 편집 그룹 밖의 탭으로 포커스를 이동한다
    await user.click(outside)

    // then: 저장·취소 버튼이 사라지고 저장 요청 없이 원래 값으로 돌아간다
    expect(within(row).queryByRole('button', { name: `${field.opener} 저장` })).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: `${field.opener} 취소` })).not.toBeInTheDocument()
    expect(outside).toHaveFocus()
    expect(update).not.toHaveBeenCalled()
    await user.click(within(row).getByRole('button', { name: `${field.opener} 수정` }))
    expect(within(row).getByLabelText(field.label)).toHaveValue(initial)
  })

  it('does not open the popup from row or non-date cells', async () => {
    const { user, row } = await setup()
    await user.click(row)
    expect(screen.queryByRole('dialog', { name: DETAIL })).not.toBeInTheDocument()
    await user.click(within(row).getByRole('cell', { name: '미팅' }))
    expect(screen.queryByRole('dialog', { name: DETAIL })).not.toBeInTheDocument()
  })

  it('does not allow Due Date editing or open a popup when Next Action is absent', async () => {
    const view = await openActionsTab()
    await addAction(view, { progress: '날짜 없는 Action' })
    const row = rowWith(view.table, '날짜 없는 Action')
    expect(within(row).queryByRole('button', { name: 'Due Date 수정' })).not.toBeInTheDocument()
    const dueCell = within(row).getAllByRole('cell').at(4)
    if (!dueCell) throw new Error('Due Date cell is missing')
    await view.user.click(dueCell)
    expect(within(row).queryByLabelText('Due Date')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: DETAIL })).not.toBeInTheDocument()
  })

  it('opens Action 추가 from inside the search region', async () => {
    const view = await openActionsTab()
    const search = screen.getByRole('search', { name: 'Action 검색' })
    await view.user.click(within(search).getByRole('button', { name: 'Action 추가' }))
    expect(await screen.findByRole('dialog', { name: 'Action 추가' })).toBeVisible()
  })

  it('saves progress in the row without opening a popup or changing next action or due date', async () => {
    const { user, action, row } = await setup()
    await user.click(within(row).getByRole('button', { name: '진행사항 수정' }))
    await user.clear(within(row).getByLabelText('진행사항'))
    await user.type(within(row).getByLabelText('진행사항'), '목록에서 수정한 진행사항')
    await user.click(within(row).getByRole('button', { name: '진행사항 저장' }))
    await waitFor(() => expect(within(row).getByRole('button', { name: '진행사항 수정' })).toHaveTextContent('목록에서 수정한 진행사항'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    const stored = (await gateway.actions.list(action.dealCode, {})).find((item) => item.id === action.id)
    expect(stored).toMatchObject({ progress: '목록에서 수정한 진행사항', nextAction: action.nextAction, dueDate: action.dueDate })
  })

  it('saves Next Action in the row while preserving progress', async () => {
    const { user, action, row } = await setup()
    await user.click(within(row).getByRole('button', { name: 'Next Action · Due Date 수정' }))
    await user.type(within(row).getByLabelText('Next Action'), ' 목록 수정')
    await user.click(within(row).getByRole('button', { name: 'Next Action · Due Date 저장' }))
    await waitFor(() => expect(within(row).getByRole('button', { name: 'Next Action · Due Date 수정' })).toHaveTextContent('요구사항 문서 전달 목록 수정'))
    const stored = (await gateway.actions.list(action.dealCode, {})).find((item) => item.id === action.id)
    expect(stored).toMatchObject({ progress: action.progress, nextAction: '요구사항 문서 전달 목록 수정', dueDate: action.dueDate })
  })

  it('saves only Due Date directly from the row', async () => {
    const { user, action, row } = await setup()
    await user.click(within(row).getByRole('button', { name: 'Due Date 수정' }))
    await user.clear(within(row).getByLabelText('Due Date'))
    await user.type(within(row).getByLabelText('Due Date'), '20270201')
    await user.click(within(row).getByRole('button', { name: 'Due Date 저장' }))
    await waitFor(() => expect(within(row).getByRole('button', { name: 'Due Date 수정' })).toHaveTextContent('2027-02-01'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    const stored = (await gateway.actions.list(action.dealCode, {})).find((item) => item.id === action.id)
    expect(stored).toMatchObject({ progress: action.progress, nextAction: action.nextAction, dueDate: '2027-02-01' })
  })

  it('opens the popup from the acted date link and edits Due Date independently', async () => {
    const { user, row, action } = await setup()
    await user.click(within(row).getByRole('link', { name: '2026-11-10' }))
    const dialog = await screen.findByRole('dialog', { name: DETAIL })
    await user.click(within(dialog).getByRole('button', { name: 'Due Date 수정' }))
    expect(within(dialog).queryByLabelText('Next Action')).not.toBeInTheDocument()
    await user.clear(within(dialog).getByLabelText('Due Date'))
    await user.type(within(dialog).getByLabelText('Due Date'), '20270301')
    await user.click(within(dialog).getByRole('button', { name: 'Due Date 저장' }))
    await waitFor(() => expect(within(dialog).getByRole('button', { name: 'Due Date 수정' })).toHaveTextContent('2027-03-01'))
    const stored = (await gateway.actions.list(action.dealCode, {})).find((item) => item.id === action.id)
    expect(stored).toMatchObject({ nextAction: action.nextAction, dueDate: '2027-03-01' })
  })

  it('does not offer row editing for another sales user', async () => {
    const view = await openActionsTab({ userId: USER_ID.park })
    const action = await addAction(view, A_INPUT, USER_ID.kim, USER_ID.park)
    const row = rowWith(view.table, '킥오프 미팅')
    expect(within(row).queryByRole('button', { name: /수정$/ })).not.toBeInTheDocument()
    expect(within(row).getByRole('link', { name: action.actedOn })).toBeVisible()
  })

  it('keeps the stored due date when a missing date is rejected and the edit is cancelled', async () => {
    const { user, action, row } = await setup()
    await user.click(within(row).getByRole('button', { name: 'Due Date 수정' }))
    await user.clear(within(row).getByLabelText('Due Date'))
    await user.click(within(row).getByRole('button', { name: 'Due Date 저장' }))
    expect(await within(row).findByRole('alert')).toHaveTextContent('Due Date를 입력하세요.')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(within(row).getByRole('button', { name: 'Due Date 취소' }))
    expect(within(row).getByRole('button', { name: 'Due Date 수정' })).toHaveTextContent(action.dueDate ?? '')
    const stored = (await gateway.actions.list(action.dealCode, {})).find((item) => item.id === action.id)
    expect(stored?.dueDate).toBe(action.dueDate)
  })
})
