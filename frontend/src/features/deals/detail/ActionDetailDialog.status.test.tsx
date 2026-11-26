import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { A_INPUT, DETAIL, addAction, fieldValue, makeGate, openActionsTab, openDetail, rowWith } from '../../../test/actionDetail'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'

/** Action 상세 팝업의 Next Action 상태 변경(AC-R54, NA-R21~R24). 서버 시계는 2026-11-13로 고정한다. */
const NOW = '2026-11-13T14:30:00+09:00'
const CLOSE = 'Next Action 종료(수행)'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const detail = () => screen.getByRole('dialog', { name: DETAIL })

function conflict(detailText: string) {
  return new ApiError(409, { type: 'https://sales.neoine.test/problems/invalid-state', title: 'x', status: 409, detail: detailText })
}

describe('팝업에서 Next Action 종료', () => {
  // 팝업의 종료(수행)은 종료 대화상자를 거쳐 팝업이 열린 채 새 상태와 새 Comment를 보이고 표 상태 칸도 같다.
  // 테스트 코드: AC-144, CM-079
  it('closes through the close dialog, keeps the popup open and updates the popup and the table row', async () => {
    // given: KIM의 Open Action A 상세 팝업
    const view = await openActionsTab()
    await addAction(view, A_INPUT)
    const dialog = await openDetail(view, '킥오프 미팅')

    // when: 팝업의 "종료(수행)"을 누르고 열린 대화상자에 "전달 완료"를 쓴 뒤 "종료"를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '종료(수행)' }))
    const close = await screen.findByRole('dialog', { name: CLOSE })
    await view.user.type(within(close).getByLabelText('Comment에 남길 내용(선택)'), '전달 완료')
    await view.user.click(within(close).getByRole('button', { name: '종료' }))

    // then: 종료 대화상자만 닫히고 상세 팝업은 열린 채 새 상태를 보이고 Comment 영역 맨 위에 "전달 완료"(KIM, Owner이므로 "읽지 않음" 없음)가 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: CLOSE })).not.toBeInTheDocument())
    await waitFor(() => expect(fieldValue(detail(), 'Next Action 상태')).toHaveTextContent('종료(수행) · 종료일 2026-11-13'))
    const comments = within(detail()).getByRole('list', { name: 'Comment 목록' })
    expect(within(comments).getAllByRole('listitem')[0]).toHaveTextContent('전달 완료')
    expect(within(comments).getAllByRole('listitem')[0]).not.toHaveTextContent('읽지 않음')
    expect(within(detail()).getByRole('heading', { name: 'Comment (1)' })).toBeVisible()
    // then: 표의 그 행 상태 칸도 "종료(수행)"이다
    expect(within(rowWith(view.table, '킥오프 미팅')).getAllByRole('cell')[5]).toHaveTextContent('종료(수행)')
  })

  // 서버가 거절하면 종료 대화상자 안에 서버 문구가 보이고 입력한 Comment가 남는다.
  // 테스트 코드: AC-144
  it('shows the server message inside the close dialog and keeps the typed comment when the server refuses', async () => {
    // given: 서버가 상태 변경을 거절한다
    vi.spyOn(gateway.actions, 'changeNextActionStatus').mockRejectedValue(conflict('이미 종료(수행) 상태입니다.'))
    const view = await openActionsTab()
    await addAction(view, A_INPUT)
    const dialog = await openDetail(view, '킥오프 미팅')
    await view.user.click(within(dialog).getByRole('button', { name: '종료(수행)' }))
    const close = await screen.findByRole('dialog', { name: CLOSE })
    await view.user.type(within(close).getByLabelText('Comment에 남길 내용(선택)'), '잃으면 안 되는 Comment')

    // when: "종료"를 누른다
    await view.user.click(within(close).getByRole('button', { name: '종료' }))

    // then: 대화상자 안에 서버 문구가 보이고 Comment가 그대로이며 상세 팝업도 열려 있다
    expect(await within(close).findByText('이미 종료(수행) 상태입니다.')).toBeVisible()
    expect(within(close).getByLabelText('Comment에 남길 내용(선택)')).toHaveValue('잃으면 안 되는 Comment')
    expect(detail()).toBeVisible()
  })

  // 종료 대화상자의 Esc는 그 대화상자만 닫고 상세 팝업은 남긴다.
  // 테스트 코드: AC-144
  it('closes only the close dialog on Escape and keeps the detail dialog', async () => {
    // given: 팝업에서 연 종료 대화상자
    const view = await openActionsTab()
    await addAction(view, A_INPUT)
    const dialog = await openDetail(view, '킥오프 미팅')
    await view.user.click(within(dialog).getByRole('button', { name: '종료(수행)' }))
    await screen.findByRole('dialog', { name: CLOSE })

    // when: Esc를 누른다
    await view.user.keyboard('{Escape}')

    // then: 종료 대화상자만 닫히고 상태는 Open 그대로다
    expect(screen.queryByRole('dialog', { name: CLOSE })).not.toBeInTheDocument()
    expect(fieldValue(detail(), 'Next Action 상태')).toHaveTextContent('Open')
  })

  // 요청이 진행 중이면 표·팝업의 상태 버튼과 닫기·삭제가 꺼진다.
  // 테스트 코드: AC-144
  it('disables every status button, close and delete while the status request is pending', async () => {
    // given: 응답을 붙들어 둔 상태 변경
    const view = await openActionsTab()
    await addAction(view, A_INPUT)
    const original = gateway.actions.changeNextActionStatus.bind(gateway.actions)
    const { gate, release } = makeGate()
    vi.spyOn(gateway.actions, 'changeNextActionStatus').mockImplementation(async (...args) => {
      await gate
      return original(...args)
    })
    const dialog = await openDetail(view, '킥오프 미팅')
    await view.user.click(within(dialog).getByRole('button', { name: '종료(수행)' }))
    const close = await screen.findByRole('dialog', { name: CLOSE })

    // when: "종료"를 눌러 요청이 진행 중이다
    await view.user.click(within(close).getByRole('button', { name: '종료' }))

    // then: 팝업의 상태 버튼·닫기·삭제가 꺼져 있다
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '닫기' })).toBeDisabled())
    expect(within(dialog).getByRole('button', { name: '삭제' })).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: '종료(미수행)' })).toBeDisabled()
    // then: 표 행의 상태 버튼도 꺼져 있다
    expect(within(rowWith(view.table, '킥오프 미팅')).getByRole('button', { name: '종료(수행)' })).toBeDisabled()
    release()
    await waitFor(() => expect(within(detail()).getByRole('button', { name: '닫기' })).toBeEnabled())
  })
})

describe('팝업의 상태 버튼 권한과 Open으로', () => {
  // 테스트 코드: AC-145
  it('reopens a closed next action after confirming an optional comment', async () => {
    // given: 종료(수행)된 KIM의 Action A 팝업
    const view = await openActionsTab()
    const created = await addAction(view, A_INPUT)
    await gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })
    await view.client.invalidateQueries()
    const dialog = await openDetail(view, '킥오프 미팅')
    await waitFor(() => expect(within(dialog).getByRole('button', { name: 'Open으로' })).toBeVisible())

    // when: 팝업에서 "Open으로"를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: 'Open으로' }))
    const confirm = await screen.findByRole('dialog', { name: 'Next Action Open' })
    await view.user.type(within(confirm).getByRole('textbox', { name: 'Comment에 남길 내용(선택)' }), '후속 미팅 필요')
    await view.user.click(within(confirm).getByRole('button', { name: 'Open으로' }))

    await waitFor(() => expect(fieldValue(detail(), 'Next Action 상태')).toHaveTextContent(/^Open/))
    expect(await within(dialog).findByText('후속 미팅 필요')).toBeVisible()
    expect(screen.getAllByRole('dialog')).toHaveLength(1)
  })

  // 테스트 코드: AC-144
  it('keeps the comment and shows the server message in the confirmation dialog when reopening is refused', async () => {
    // given: 종료(수행)된 Action A 팝업, 서버가 되돌리기를 거절한다
    const view = await openActionsTab()
    const created = await addAction(view, A_INPUT)
    await gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })
    await view.client.invalidateQueries()
    const dialog = await openDetail(view, '킥오프 미팅')
    vi.spyOn(gateway.actions, 'changeNextActionStatus').mockRejectedValue(conflict('이미 Open 상태입니다.'))
    await waitFor(() => expect(within(dialog).getByRole('button', { name: 'Open으로' })).toBeVisible())

    // when: "Open으로"를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: 'Open으로' }))
    const confirm = within(await screen.findByRole('dialog', { name: 'Next Action Open' }))
    const comment = confirm.getByRole('textbox', { name: 'Comment에 남길 내용(선택)' })
    await view.user.type(comment, '후속 미팅 필요')
    await view.user.click(confirm.getByRole('button', { name: 'Open으로' }))

    expect(await confirm.findByRole('alert')).toHaveTextContent('이미 Open 상태입니다.')
    expect(comment).toHaveValue('후속 미팅 필요')
  })

  // 다른 sales의 Next Action은 라벨만 보이고 상태 버튼이 없다.
  // 테스트 코드: AC-145
  it('shows only the label to another sales', async () => {
    // given: LEE(박영업)의 Open Action B를 KIM이 본다
    const view = await openActionsTab()
    await addAction(view, { progress: '박영업의 진행', nextAction: '박영업 후속', dueDate: '2027-02-01' }, USER_ID.park)

    // when: B의 상세 팝업을 연다
    const dialog = await openDetail(view, '박영업의 진행')

    // then: 상태 라벨만 있고 상태 버튼이 없다
    expect(fieldValue(dialog, 'Next Action 상태')).toHaveTextContent('Open')
    for (const name of ['종료(수행)', '종료(미수행)', 'Open으로']) {
      expect(within(dialog).queryByRole('button', { name })).not.toBeInTheDocument()
    }
  })

  // user는 라벨만 보인다.
  // 테스트 코드: AC-145
  it('shows only the label to the user role', async () => {
    // given: user가 연 Actions 탭
    const view = await openActionsTab({ role: 'user' })

    // when: KIM의 Open Action 상세 팝업을 연다
    const dialog = await openDetail(view, '최종 가격 협의')

    // then: 상태 라벨만 있고 상태 버튼이 없다
    expect(fieldValue(dialog, 'Next Action 상태')).toHaveTextContent('Open')
    for (const name of ['종료(수행)', '종료(미수행)', 'Open으로']) {
      expect(within(dialog).queryByRole('button', { name })).not.toBeInTheDocument()
    }
  })

  // admin은 남의 Open Action에 종료 버튼 둘을 가진다.
  // 테스트 코드: AC-145
  it('gives admin both close buttons on another users open action', async () => {
    // given: 박영업의 Open Action B를 admin이 본다
    const view = await openActionsTab({ role: 'admin' })
    await addAction(view, { progress: '박영업의 진행', nextAction: '박영업 후속', dueDate: '2027-02-01' }, USER_ID.park, USER_ID.root)

    // when: B의 상세 팝업을 연다
    const dialog = await openDetail(view, '박영업의 진행')

    // then: "종료(수행)"·"종료(미수행)" 버튼이 있다
    expect(within(dialog).getByRole('button', { name: '종료(수행)' })).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '종료(미수행)' })).toBeVisible()
  })
})
