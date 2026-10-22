import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { confirmRevenue, expectOnlyActionPopup, statusSelect } from '../../../test/actionFormUtils'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/** Action 추가·수정 팝업 (AC-7~15). 기본 탭이 Deal 상세라 ?tab=actions로 들어온다. */
afterEach(() => vi.restoreAllMocks())

type View = Awaited<ReturnType<typeof renderAt>>

async function openActions(role: 'sales' | 'admin' | 'user' = 'sales') {
  const view = await renderAt(await detailPath(1, '?tab=actions'), { role })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table }
}

const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)
const addButton = () => screen.getByRole('button', { name: 'Action 추가' })

async function openAdd(user: View['user']) {
  await user.click(addButton())
  const dialog = await screen.findByRole('dialog', { name: 'Action 추가' })
  return { dialog, form: within(dialog).getByRole('form', { name: 'Action 추가' }) }
}

async function openEdit(user: View['user'], table: HTMLElement, index: number) {
  const row = bodyRows(table)[index]!
  await user.click(within(row).getByRole('button', { name: '수정' }))
  const dialog = await screen.findByRole('dialog', { name: 'Action 수정' })
  return { row, dialog, form: within(dialog).getByRole('form', { name: 'Action 수정' }) }
}

async function fillValid(user: View['user'], form: HTMLElement, progress = '팝업에서 등록') {
  await user.type(within(form).getByLabelText('유형'), '미팅')
  await user.type(within(form).getByLabelText('진행사항'), progress)
}

const serverFailure = () =>
  new ApiError(500, {
    type: 'https://sales.neoine.test/problems/internal',
    title: 'x',
    status: 500,
    detail: '서버 저장에 실패했습니다.',
  })

describe('Action 추가 버튼 (AC-7)', () => {
  it.each(['sales', 'admin'] as const)('shows the Action 추가 button to %s', async (role) => {
    await openActions(role)

    expect(addButton()).toBeVisible()
  })

  it('hides the Action 추가 button from the user role', async () => {
    await openActions('user')

    expect(screen.queryByRole('button', { name: 'Action 추가' })).not.toBeInTheDocument()
  })

  it('never shows the old Next Action 업데이트 wording', async () => {
    const { user } = await openActions()
    expect(screen.queryByText('Next Action 업데이트')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()

    await openAdd(user)

    expect(screen.queryByText('Next Action 업데이트')).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()
  })

  it('keeps the button visible while the dialog is open', async () => {
    const { user } = await openActions()

    await openAdd(user)

    expect(addButton()).toBeInTheDocument()
  })
})

describe('Action 추가 팝업 열기 (AC-8)', () => {
  it('opens a modal dialog titled Action 추가 with every field and the previous update', async () => {
    const { user } = await openActions()

    const { dialog, form } = await openAdd(user)

    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByRole('heading', { level: 2, name: 'Action 추가' })).toBeVisible()
    for (const label of ['Status', 'Forecast', '유형', '진행사항', 'Next Action', 'Due Date', 'Memo']) {
      expect(within(form).getByLabelText(label)).toBeVisible()
    }
    const previous = within(dialog).getByRole('complementary', { name: '이전 Update' })
    expect(previous).toHaveTextContent('계약서 초안 검토')
  })

  it('shows one dialog heading, not a second inline form title', async () => {
    const { user } = await openActions()

    const { dialog } = await openAdd(user)

    expect(within(dialog).getAllByRole('heading', { name: 'Action 추가' })).toHaveLength(1)
  })

  it('places the previous update before the form inside the dialog (stacked above)', async () => {
    const { user } = await openActions()

    const { dialog, form } = await openAdd(user)

    const previous = within(dialog).getByRole('complementary', { name: '이전 Update' })
    expect(previous.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe('등록 성공 (AC-9)', () => {
  it('closes the dialog, shows the notice and lists the new action', async () => {
    const { user, table } = await openActions()
    const { form } = await openAdd(user)
    await fillValid(user, form)

    await user.click(within(form).getByRole('button', { name: '등록' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('팝업에서 등록'))
  })

  it('appends the Status and Forecast summary to the notice when they changed together', async () => {
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)
    await fillValid(user, form)

    await user.click(within(form).getByRole('button', { name: '등록' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText(/Action이 등록되었습니다\. Status가 .*계약완료.* Forecast가 .*Won.* 변경되었습니다\./)).toBeVisible()
  })
})

describe('등록·수정 실패 (AC-10)', () => {
  it('keeps the dialog and the input with the server error inside when registering fails', async () => {
    vi.spyOn(gateway.actions, 'create').mockRejectedValue(serverFailure())
    const { user, table } = await openActions()
    const before = bodyRows(table).length
    const { dialog, form } = await openAdd(user)
    await fillValid(user, form, '실패해도 남아야 하는 입력')

    await user.click(within(form).getByRole('button', { name: '등록' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('서버 저장에 실패했습니다.')
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('실패해도 남아야 하는 입력')
    expect(within(form).getByLabelText('유형')).toHaveDisplayValue('미팅')
    expect(bodyRows(table)).toHaveLength(before)
    expect(screen.queryByText('Action이 등록되었습니다.')).not.toBeInTheDocument()
  })

  it('keeps the edit dialog and the changed value when saving fails', async () => {
    vi.spyOn(gateway.actions, 'update').mockRejectedValue(serverFailure())
    const { user, table } = await openActions()
    const { dialog, form } = await openEdit(user, table, 1)
    const progress = within(form).getByLabelText('진행사항')
    await user.clear(progress)
    await user.type(progress, '저장 실패한 수정값')

    await user.click(within(form).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('서버 저장에 실패했습니다.')
    expect(screen.getByRole('dialog', { name: 'Action 수정' })).toBeVisible()
    expect(progress).toHaveValue('저장 실패한 수정값')
    expect(screen.queryByText('Action이 수정되었습니다.')).not.toBeInTheDocument()
  })

  it('shows the client validation messages inside the dialog and keeps it open', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user } = await openActions()
    const { dialog, form } = await openAdd(user)

    await user.click(within(form).getByRole('button', { name: '등록' }))

    expect(within(dialog).getByText('유형을 입력하세요.')).toBeVisible()
    expect(within(dialog).getByText('진행사항 또는 Next Action을 입력하세요.')).toBeVisible()
    await user.type(within(form).getByLabelText('Next Action'), '다음 할 일')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    expect(within(dialog).getByText('Due Date를 입력하세요.')).toBeVisible()
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })
})

describe('Action 수정 팝업 (AC-11)', () => {
  it('opens filled with the action and without previous update or status fields, then saves and closes', async () => {
    const { user, table } = await openActions()

    const { dialog, form } = await openEdit(user, table, 1)

    expect(within(form).getByLabelText('진행사항')).toHaveValue('임원 보고용 ROI 자료 전달')
    expect(within(dialog).queryByRole('complementary', { name: '이전 Update' })).not.toBeInTheDocument()
    expect(within(form).queryByLabelText('Status')).not.toBeInTheDocument()
    expect(within(form).queryByLabelText('Forecast')).not.toBeInTheDocument()
    const progress = within(form).getByLabelText('진행사항')
    await user.clear(progress)
    await user.type(progress, 'ROI 자료 팝업 수정본')

    await user.click(within(form).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 수정' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 수정되었습니다.')).toBeVisible()
    await waitFor(() => expect(bodyRows(table)[1]).toHaveTextContent('ROI 자료 팝업 수정본'))
  })
})

describe('취소와 Esc (AC-12)', () => {
  it('focuses the progress field first when the add dialog opens, not the previous update fill button', async () => {
    const { user } = await openActions()
    const { dialog, form } = await openAdd(user)

    expect(within(dialog).getByRole('complementary', { name: '이전 Update' })).toBeVisible()
    expect(within(form).getByLabelText('진행사항')).toHaveFocus()
  })

  it('closes without saving on cancel, restores focus to the add button and drops the input', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.type(within(form).getByLabelText('진행사항'), '버릴 입력')

    await user.click(within(form).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(addButton()).toHaveFocus()
    expect(create).not.toHaveBeenCalled()
    const reopened = await openAdd(user)
    expect(within(reopened.form).getByLabelText('진행사항')).toHaveValue('')
  })

  it('closes on Escape without saving and restores focus to the add button', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.type(within(form).getByLabelText('진행사항'), '버릴 입력')

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(addButton()).toHaveFocus()
    expect(create).not.toHaveBeenCalled()
    const reopened = await openAdd(user)
    expect(within(reopened.form).getByLabelText('진행사항')).toHaveValue('')
  })

  it('closes the edit dialog on Escape, focuses the row edit button and reopens with the original value', async () => {
    const update = vi.spyOn(gateway.actions, 'update')
    const { user, table } = await openActions()
    const { form } = await openEdit(user, table, 1)
    await user.type(within(form).getByLabelText('진행사항'), ' 덧붙인 내용')

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(bodyRows(table)[1]!).getByRole('button', { name: '수정' })).toHaveFocus()
    expect(update).not.toHaveBeenCalled()
    const reopened = await openEdit(user, table, 1)
    expect(within(reopened.form).getByLabelText('진행사항')).toHaveValue('임원 보고용 ROI 자료 전달')
  })

  it('closes the edit dialog on cancel and focuses the row edit button', async () => {
    const { user, table } = await openActions()
    const { form } = await openEdit(user, table, 0)

    await user.click(within(form).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' })).toHaveFocus()
  })
})

describe('저장 중 (AC-13)', () => {
  it('disables cancel and ignores Escape while the request is pending, then closes when it finishes', async () => {
    const original = gateway.actions.create.bind(gateway.actions)
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.spyOn(gateway.actions, 'create').mockImplementation(async (...args) => {
      await gate
      return original(...args)
    })
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await fillValid(user, form, '저장 중 입력')

    await user.click(within(form).getByRole('button', { name: '등록' }))

    await waitFor(() => expect(within(form).getByRole('button', { name: '취소' })).toBeDisabled())
    await user.keyboard('{Escape}')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('저장 중 입력')
    release()
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
  })

  it('enables cancel again after a failed save', async () => {
    vi.spyOn(gateway.actions, 'create').mockRejectedValue(serverFailure())
    const { user } = await openActions()
    const { dialog, form } = await openAdd(user)
    await fillValid(user, form)

    await user.click(within(form).getByRole('button', { name: '등록' }))

    await within(dialog).findByRole('alert')
    expect(within(form).getByRole('button', { name: '취소' })).toBeEnabled()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('겹친 팝업 (AC-14)', () => {
  it('closes only the sync dialog on Escape and keeps the Action dialog with its input', async () => {
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.type(within(form).getByLabelText('진행사항'), '남아야 하는 입력')
    await user.selectOptions(statusSelect(form), '계약완료')
    await screen.findByRole('dialog', { name: '매출 확정' })
    expect(screen.getAllByRole('dialog')).toHaveLength(2)

    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '매출 확정' })).not.toBeInTheDocument())
    expectOnlyActionPopup()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('남아야 하는 입력')
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
  })

  it('closes the Action dialog on the next Escape after the sync dialog is gone', async () => {
    const { user } = await openActions()
    await openAdd(user)
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await screen.findByRole('dialog', { name: '매출 확정' })
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '매출 확정' })).not.toBeInTheDocument())

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(addButton()).toHaveFocus()
  })

  it('keeps Tab focus inside the top dialog only', async () => {
    const { user } = await openActions()
    await openAdd(user)
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    const top = await screen.findByRole('dialog', { name: '매출 확정' })

    for (let i = 0; i < 8; i += 1) {
      await user.tab()
      expect(top).toContainElement(document.activeElement as HTMLElement)
    }
    for (let i = 0; i < 8; i += 1) {
      await user.tab({ shift: true })
      expect(top).toContainElement(document.activeElement as HTMLElement)
    }
  })
})
