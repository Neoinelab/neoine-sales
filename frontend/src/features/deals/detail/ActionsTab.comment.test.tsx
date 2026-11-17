import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { A_INPUT, DETAIL, addAction, bodyRows, openActionsTab, openDetail, rowWith } from '../../../test/actionDetail'
import { COMMENT_NOW, commentItems, seedComments } from '../../../test/commentScreen'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'

/** Action 추가 팝업의 Comment 칸(CM-R42)과 Comment가 있는 Action의 삭제(CM-R16). 서버 시계는 2026-11-17로 고정한다. */
beforeEach(() => resetMock({ now: COMMENT_NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

async function openForm(view: Awaited<ReturnType<typeof openActionsTab>>) {
  await view.user.click(screen.getByRole('button', { name: 'Action 추가' }))
  return screen.getByRole('form', { name: 'Action 추가' })
}

describe('Action 추가 팝업의 Comment 칸', () => {
  // Comment 칸에 쓰면 새 Action의 Comment가 생기고 비우면 생기지 않는다. Memo 칸은 없다.
  // 테스트 코드: CM-078
  it('creates a comment of the new action from the Comment box, and none when it is left empty', async () => {
    // given: 박영업이 연 "Action 추가" 팝업(등록 요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openActionsTab({ userId: USER_ID.park })
    const form = await openForm(view)

    // then: "Memo" 칸은 없고 "Comment" 칸이 있다
    expect(within(form).queryByLabelText('Memo')).not.toBeInTheDocument()
    expect(within(form).getByLabelText('Comment')).toBeVisible()

    // when: 진행사항 "현장 방문"과 Comment "담당자 교체 예정"으로 등록한다
    await view.user.type(within(form).getByLabelText('유형'), '방문')
    await view.user.type(within(form).getByLabelText('진행사항'), '현장 방문')
    await view.user.type(within(form).getByLabelText('Comment'), '담당자 교체 예정')
    await view.user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 첫 요청의 comment는 "담당자 교체 예정"이고 memo 키는 없다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toMatchObject({ comment: '담당자 교체 예정' })
    expect(create.mock.calls[0]?.[1]).not.toHaveProperty('memo')
    // then: 새 Action 팝업에 그 Comment가 "읽지 않음"으로 보인다(Owner가 아닌 사람이 썼다)
    const dialog = await openDetail(view, '현장 방문')
    await within(dialog).findByRole('heading', { name: 'Comment (1)' })
    expect(commentItems(dialog)[0]).toHaveTextContent('담당자 교체 예정')
    expect(commentItems(dialog)[0]).toHaveTextContent('읽지 않음')
    // then: Comments 탭에도 그 Comment가 보인다
    await view.user.click(within(dialog).getByRole('button', { name: '닫기' }))
    await view.user.click(screen.getByRole('tab', { name: /^Comments/ }))
    expect(commentItems()[0]).toHaveTextContent('담당자 교체 예정')

    // when: Comment를 비운 채 한 번 더 등록한다
    await view.user.click(screen.getByRole('tab', { name: 'Actions' }))
    const second = await openForm(view)
    await view.user.type(within(second).getByLabelText('유형'), '방문')
    await view.user.type(within(second).getByLabelText('진행사항'), '두 번째 방문')
    await view.user.click(within(second).getByRole('button', { name: '등록' }))

    // then: 둘째 요청의 comment는 ""이고 Comment가 늘지 않는다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(2))
    expect(create.mock.calls[1]?.[1]).toMatchObject({ comment: '' })
    expect(await gateway.comments.list(view.code)).toHaveLength(1)
  })
})

describe('Comment가 있는 Action의 삭제', () => {
  // 확인 문구에 함께 지워지는 Comment 건수가 있고 삭제 뒤 Comments 탭과 배지에서 사라진다. Comment가 없으면 그 문장이 없다.
  // 테스트 코드: CM-080
  it('states the count of the comments deleted with the action and removes them from the Comments tab and the badge', async () => {
    // given: KIM의 A에 Comment 2건(1건 읽지 않음)과 Deal Comment 1건, Comment 없는 Action P
    const view = await openActionsTab()
    const a = await addAction(view, A_INPUT)
    await addAction(view, { progress: '현장 점검', type: { name: '방문' }, actedOn: '2026-11-11' })
    await seedComments(view, [
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.kim, body: 'A 읽음', createdAt: '2026-11-12T09:00:00+09:00', readAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.park, body: 'A 읽지 않음', createdAt: '2026-11-12T09:10:00+09:00' },
      { dealCode: view.code, authorId: USER_ID.park, body: 'Deal 글', createdAt: '2026-11-12T09:20:00+09:00' },
    ])

    // when: Comment 없는 Action P의 삭제 확인을 연다
    const pDialog = await openDetail(view, '현장 점검')
    await view.user.click(within(pDialog).getByRole('button', { name: '삭제' }))
    const pConfirm = await screen.findByRole('dialog', { name: 'Action 삭제' })
    // then: 확인 문구에 Comment 건수 문장이 없다
    expect(pConfirm).not.toHaveTextContent('연결된 Comment')
    await view.user.click(within(pConfirm).getByRole('button', { name: '취소' }))
    await view.user.click(within(screen.getByRole('dialog', { name: DETAIL })).getByRole('button', { name: '닫기' }))

    // when: A 팝업에서 "삭제"를 누른다
    const dialog = await openDetail(view, '킥오프 미팅')
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))
    const confirm = await screen.findByRole('dialog', { name: 'Action 삭제' })
    // then: 확인 문구 끝에 " 연결된 Comment 2건도 함께 삭제됩니다."가 있다
    expect(confirm).toHaveTextContent(/ 연결된 Comment 2건도 함께 삭제됩니다\./)

    // when: 확인한 뒤 Comments 탭을 연다
    await view.user.click(within(confirm).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(rowWith(view.table, '현장 점검')).toBeVisible())
    expect(bodyRows(view.table).some((r) => r.textContent?.includes('킥오프 미팅'))).toBe(false)
    // (Owner가 탭을 열면 읽음 처리되므로 탭을 열기 전에 배지를 확인한다)
    await waitFor(() => expect(within(screen.getByRole('tab', { name: /^Comments/ })).getByText('1')).toBeVisible())
    await view.user.click(screen.getByRole('tab', { name: /^Comments/ }))

    // then: Deal Comment 1건만 남고 탭 배지가 1 줄어 "1"이었다(읽지 않은 것은 Deal Comment뿐)
    await waitFor(() => expect(commentItems()).toHaveLength(1))
    expect(commentItems()[0]).toHaveTextContent('Deal 글')
  })
})
