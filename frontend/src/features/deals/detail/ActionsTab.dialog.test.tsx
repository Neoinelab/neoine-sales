import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { confirmRevenue, expectOnlyActionPopup, statusSelect } from '../../../test/actionFormUtils'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/** Action 추가 팝업. 기본 탭이 Deal 상세라 ?tab=actions로 들어온다. */
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

describe('Action 추가 버튼', () => {
  // sales와 admin에게는 Action 추가 버튼이 보인다.
  // 테스트 코드: AC-072
  it.each(['sales', 'admin'] as const)('shows the Action 추가 button to %s', async (role) => {
    // when: 해당 역할로 Actions 탭을 연다
    await openActions(role)

    // then: Action 추가 버튼이 보인다
    expect(addButton()).toBeVisible()
  })

  // user에게는 Action 추가 버튼이 없다.
  // 테스트 코드: AC-072
  it('hides the Action 추가 button from the user role', async () => {
    // when: user로 Actions 탭을 연다
    await openActions('user')

    // then: Action 추가 버튼이 없다
    expect(screen.queryByRole('button', { name: 'Action 추가' })).not.toBeInTheDocument()
  })

  // 예전 "Next Action 업데이트" 문구는 어디에도 없다.
  // 테스트 코드: AC-074
  it('never shows the old Next Action 업데이트 wording', async () => {
    // given: sales가 Actions 탭을 연다
    const { user } = await openActions()
    // then: 탭에 예전 문구와 버튼이 없다
    expect(screen.queryByText('Next Action 업데이트')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()

    // when: 추가 팝업을 연다
    await openAdd(user)

    // then: 팝업에도 예전 문구와 폼이 없다
    expect(screen.queryByText('Next Action 업데이트')).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()
  })

  // 팝업이 열려 있어도 추가 버튼은 보인다.
  // 테스트 코드: AC-074
  it('keeps the button visible while the dialog is open', async () => {
    // given: sales가 Actions 탭을 연다
    const { user } = await openActions()

    // when: 추가 팝업을 연다
    await openAdd(user)

    // then: 추가 버튼이 그대로 있다
    expect(addButton()).toBeInTheDocument()
  })
})

describe('Action 추가 팝업 열기', () => {
  // 추가 팝업은 모달이며 모든 칸과 이전 Update 카드를 보인다.
  // 테스트 코드: AC-074
  it('opens a modal dialog titled Action 추가 with every field and the previous update', async () => {
    // given: sales가 Actions 탭을 연다
    const { user } = await openActions()

    // when: 추가 팝업을 연다
    const { dialog, form } = await openAdd(user)

    // then: aria-modal 팝업이고 제목이 Action 추가다
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByRole('heading', { level: 2, name: 'Action 추가' })).toBeVisible()
    // then: Status·Forecast·유형·진행사항·Next Action·Due·Comment 칸이 있고 Memo 칸은 없다
    for (const label of ['Status', 'Forecast', '유형', '진행사항', 'Next Action', 'Due Date', 'Comment']) {
      expect(within(form).getByLabelText(label)).toBeVisible()
    }
    expect(within(form).queryByLabelText('Memo')).not.toBeInTheDocument()
    // then: 이전 Update 카드에 기준 행 내용이 보인다
    const previous = within(dialog).getByRole('complementary', { name: '이전 Update' })
    expect(previous).toHaveTextContent('계약서 초안 검토')
  })

  // 팝업 제목은 하나뿐이고 폼 안에 두 번째 제목이 없다.
  // 테스트 코드: AC-074
  it('shows one dialog heading, not a second inline form title', async () => {
    // given: sales가 Actions 탭을 연다
    const { user } = await openActions()

    // when: 추가 팝업을 연다
    const { dialog } = await openAdd(user)

    // then: Action 추가 제목이 하나다
    expect(within(dialog).getAllByRole('heading', { name: 'Action 추가' })).toHaveLength(1)
  })

  // 이전 Update 카드는 폼 앞에 놓인다.
  // 테스트 코드: AC-074
  it('places the previous update before the form inside the dialog (stacked above)', async () => {
    // given: sales가 Actions 탭을 연다
    const { user } = await openActions()

    // when: 추가 팝업을 연다
    const { dialog, form } = await openAdd(user)

    // then: 카드가 폼보다 앞에 있다
    const previous = within(dialog).getByRole('complementary', { name: '이전 Update' })
    expect(previous.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe('등록 성공', () => {
  // 등록하면 팝업이 닫히고 알림이 보이며 새 Action이 목록에 나온다.
  // 테스트 코드: AC-077
  it('closes the dialog, shows the notice and lists the new action', async () => {
    // given: sales가 추가 팝업에서 유효한 내용을 채운다
    const { user, table } = await openActions()
    const { form } = await openAdd(user)
    await fillValid(user, form)

    // when: 등록을 누른다
    await user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 팝업이 닫히고 등록 알림이 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
    // then: 새 Action이 목록 맨 위에 있다
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('팝업에서 등록'))
  })

  // Status·Forecast가 함께 바뀌면 알림에 변경 요약이 붙는다.
  // 테스트 코드: AC-079
  it('appends the Status and Forecast summary to the notice when they changed together', async () => {
    // given: sales가 추가 팝업에서 계약완료로 바꾸고 매출을 확정해 내용을 채운다
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)
    await fillValid(user, form)

    // when: 등록을 누른다
    await user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 팝업이 닫힌다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    // then: 알림에 Status와 Forecast 변경 요약이 붙는다
    expect(screen.getByText(/Action이 등록되었습니다\. Status가 .*계약완료.* Forecast가 .*Won.* 변경되었습니다\./)).toBeVisible()
  })
})

describe('등록 실패', () => {
  // 등록 실패 시 팝업과 입력을 유지하고 서버 오류를 팝업 안에 보인다.
  // 테스트 코드: AC-084
  it('keeps the dialog and the input with the server error inside when registering fails', async () => {
    // given: 등록이 서버 오류로 실패하도록 한 sales와 추가 팝업의 입력
    vi.spyOn(gateway.actions, 'create').mockRejectedValue(serverFailure())
    const { user, table } = await openActions()
    const before = bodyRows(table).length
    const { dialog, form } = await openAdd(user)
    await fillValid(user, form, '실패해도 남아야 하는 입력')

    // when: 등록을 누른다
    await user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 팝업 안 배너에 서버 문구가 보인다
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('서버 저장에 실패했습니다.')
    // then: 팝업과 입력이 그대로이고 목록·알림에 변화가 없다
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('실패해도 남아야 하는 입력')
    expect(within(form).getByLabelText('유형')).toHaveDisplayValue('미팅')
    expect(bodyRows(table)).toHaveLength(before)
    expect(screen.queryByText('Action이 등록되었습니다.')).not.toBeInTheDocument()
  })

  // 화면 검증 문구는 팝업 안에 보이고 팝업이 열려 있으며 요청하지 않는다.
  // 테스트 코드: AC-075
  it('shows the client validation messages inside the dialog and keeps it open', async () => {
    // given: sales가 추가 팝업을 연다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user } = await openActions()
    const { dialog, form } = await openAdd(user)

    // when: 모든 칸을 비우고 등록을 누른다
    await user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 유형·진행사항 문구가 팝업 안에 보인다
    expect(within(dialog).getByText('유형을 입력하세요.')).toBeVisible()
    expect(within(dialog).getByText('진행사항 또는 Next Action을 입력하세요.')).toBeVisible()
    // when: Next Action만 쓰고 다시 등록을 누른다
    await user.type(within(form).getByLabelText('Next Action'), '다음 할 일')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    // then: Due Date 문구가 보이고 팝업이 열려 있으며 등록 요청이 없다
    expect(within(dialog).getByText('Due Date를 입력하세요.')).toBeVisible()
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })
})

describe('취소와 Esc', () => {
  // 추가 팝업이 열리면 진행사항 칸에 포커스가 간다.
  // 테스트 코드: AC-074
  it('focuses the progress field first when the add dialog opens, not the previous update fill button', async () => {
    // given: sales가 Actions 탭을 연다
    const { user } = await openActions()
    // when: 추가 팝업을 연다
    const { dialog, form } = await openAdd(user)

    // then: 이전 Update 카드가 있어도 포커스는 진행사항 칸이다
    expect(within(dialog).getByRole('complementary', { name: '이전 Update' })).toBeVisible()
    expect(within(form).getByLabelText('진행사항')).toHaveFocus()
  })

  // 취소하면 저장 없이 닫히고 추가 버튼으로 포커스가 가며 입력을 버린다.
  // 테스트 코드: AC-085
  it('closes without saving on cancel, restores focus to the add button and drops the input', async () => {
    // given: sales가 추가 팝업에서 진행사항을 입력한다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.type(within(form).getByLabelText('진행사항'), '버릴 입력')

    // when: 취소를 누른다
    await user.click(within(form).getByRole('button', { name: '취소' }))

    // then: 팝업이 닫히고 추가 버튼에 포커스가 가며 등록 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(addButton()).toHaveFocus()
    expect(create).not.toHaveBeenCalled()
    // when: 다시 연다
    const reopened = await openAdd(user)
    // then: 진행사항이 비어 있다
    expect(within(reopened.form).getByLabelText('진행사항')).toHaveValue('')
  })

  // Esc는 저장 없이 닫고 추가 버튼으로 포커스를 돌려준다.
  // 테스트 코드: AC-085
  it('closes on Escape without saving and restores focus to the add button', async () => {
    // given: sales가 추가 팝업에서 진행사항을 입력한다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.type(within(form).getByLabelText('진행사항'), '버릴 입력')

    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 팝업이 닫히고 추가 버튼에 포커스가 가며 등록 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(addButton()).toHaveFocus()
    expect(create).not.toHaveBeenCalled()
    // when: 다시 연다
    const reopened = await openAdd(user)
    // then: 진행사항이 비어 있다
    expect(within(reopened.form).getByLabelText('진행사항')).toHaveValue('')
  })
})

describe('저장 중', () => {
  // 저장 중에는 취소가 꺼지고 Esc가 무시되며 끝나면 닫힌다.
  // 테스트 코드: AC-084
  it('disables cancel and ignores Escape while the request is pending, then closes when it finishes', async () => {
    // given: 등록 요청이 끝나기를 기다리게 한 sales와 채운 추가 팝업
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

    // when: 등록을 누른다
    await user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 저장 중에는 취소가 꺼져 있다
    await waitFor(() => expect(within(form).getByRole('button', { name: '취소' })).toBeDisabled())
    // when: Esc를 누른다
    await user.keyboard('{Escape}')
    fireEvent.keyDown(document, { key: 'Escape' })
    // then: 팝업과 입력이 그대로다
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('저장 중 입력')
    // when: 요청이 끝난다
    release()
    // then: 팝업이 닫히고 등록 알림이 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
  })

  // 저장이 실패하면 취소가 다시 켜진다.
  // 테스트 코드: AC-084
  it('enables cancel again after a failed save', async () => {
    // given: 등록이 서버 오류로 실패하도록 한 sales와 채운 추가 팝업
    vi.spyOn(gateway.actions, 'create').mockRejectedValue(serverFailure())
    const { user } = await openActions()
    const { dialog, form } = await openAdd(user)
    await fillValid(user, form)

    // when: 등록을 누른다
    await user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 오류 배너가 보이고 취소가 켜져 있다
    await within(dialog).findByRole('alert')
    expect(within(form).getByRole('button', { name: '취소' })).toBeEnabled()
    // when: Esc를 누른다
    await user.keyboard('{Escape}')
    // then: 팝업이 닫힌다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('겹친 팝업', () => {
  // 겹친 동기화 대화상자는 Esc로 먼저 닫히고 Action 팝업과 입력은 남는다.
  // 테스트 코드: AC-085
  it('closes only the sync dialog on Escape and keeps the Action dialog with its input', async () => {
    // given: sales가 추가 팝업에 입력하고 Status를 바꿔 동기화 대화상자가 겹쳤다
    const { user } = await openActions()
    const { form } = await openAdd(user)
    await user.type(within(form).getByLabelText('진행사항'), '남아야 하는 입력')
    await user.selectOptions(statusSelect(form), '계약완료')
    await screen.findByRole('dialog', { name: '매출 확정' })
    expect(screen.getAllByRole('dialog')).toHaveLength(2)

    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 동기화 대화상자만 닫히고 Action 팝업과 입력이 남으며 Status는 원래 값이다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '매출 확정' })).not.toBeInTheDocument())
    expectOnlyActionPopup()
    expect(within(form).getByLabelText('진행사항')).toHaveValue('남아야 하는 입력')
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
  })

  // 동기화 대화상자가 사라진 뒤 다음 Esc가 Action 팝업을 닫는다.
  // 테스트 코드: AC-085
  it('closes the Action dialog on the next Escape after the sync dialog is gone', async () => {
    // given: sales가 추가 팝업에서 동기화 대화상자를 Esc로 닫았다
    const { user } = await openActions()
    await openAdd(user)
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await screen.findByRole('dialog', { name: '매출 확정' })
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '매출 확정' })).not.toBeInTheDocument())

    // when: Esc를 한 번 더 누른다
    await user.keyboard('{Escape}')

    // then: 팝업이 닫히고 추가 버튼에 포커스가 간다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(addButton()).toHaveFocus()
  })

  // Tab 포커스는 맨 위 팝업 안에서만 돈다.
  // 테스트 코드: AC-085
  it('keeps Tab focus inside the top dialog only', async () => {
    // given: sales가 추가 팝업에서 Status를 바꿔 동기화 대화상자가 겹쳤다
    const { user } = await openActions()
    await openAdd(user)
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    const top = await screen.findByRole('dialog', { name: '매출 확정' })

    // when: Tab과 Shift+Tab을 여러 번 누른다
    for (let i = 0; i < 8; i += 1) {
      await user.tab()
      // then: 포커스가 항상 맨 위 대화상자 안에 있다
      expect(top).toContainElement(document.activeElement as HTMLElement)
    }
    for (let i = 0; i < 8; i += 1) {
      await user.tab({ shift: true })
      expect(top).toContainElement(document.activeElement as HTMLElement)
    }
  })
})
