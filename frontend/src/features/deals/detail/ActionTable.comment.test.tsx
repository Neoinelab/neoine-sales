import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { A_INPUT, DETAIL, addAction, openActionsTab, rowWith } from '../../../test/actionDetail'
import { COMMENT_NOW, seedComments } from '../../../test/commentScreen'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'

/** Actions 표의 Comment 열과 아이콘(CM-R40). Action A(김영업, 수행일 2026-11-10)와 진행사항만 있는 P를 쓴다. */
beforeEach(() => resetMock({ now: COMMENT_NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

async function openWithAP(who: { role?: 'sales' | 'admin' | 'user'; userId?: number }) {
  const view = await openActionsTab(who)
  const viewer = who.userId ?? (who.role === 'user' ? USER_ID.han : who.role === 'admin' ? USER_ID.root : USER_ID.kim)
  const a = await addAction(view, A_INPUT, USER_ID.kim, viewer)
  const p = await addAction(view, { progress: '현장 점검', type: { name: '방문' }, actedOn: '2026-11-11' }, USER_ID.kim, viewer)
  return { view, a, p }
}

const commentButton = (row: HTMLElement) => within(row).getByRole('button', { name: /^Comment (추가|보기)/ })

describe('Actions 표의 Comment 열', () => {
  // 맨 오른쪽 Comment 열에 아이콘과 그 Action의 읽지 않은 수가 보인다. 쓰기 권한자는 "추가", user는 "보기"다.
  // 테스트 코드: CM-073
  it('shows the icon and the unread count of each action in the rightmost Comment column, add for writers and view for a user', async () => {
    // given: A에 읽지 않은 Comment 2건, P에 읽은 Comment 1건이 있고 박영업이 Actions 탭을 연다
    const { view, a, p } = await openWithAP({ userId: USER_ID.park })
    await seedComments(view, [
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: '읽지 않은 1', createdAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: '읽지 않은 2', createdAt: '2026-11-12T09:10:00+09:00' },
      { dealCode: view.code, actionId: p.id, authorId: USER_ID.kim, body: '읽은 1', createdAt: '2026-11-12T09:20:00+09:00', readAt: '2026-11-12T09:20:00+09:00' },
    ])

    // when: 머리글과 두 행을 읽는다
    const headers = within(view.table).getAllByRole('columnheader').map((h) => h.textContent)
    await screen.findByRole('button', { name: 'Comment 추가 (읽지 않은 2건)' })

    // then: 머리글 마지막이 "Comment"이고 A 행 버튼 이름에 읽지 않은 2건이 있으며 배지 "2"가 있다
    expect(headers.at(-1)).toBe('Comment')
    const aRow = rowWith(view.table, '킥오프 미팅')
    expect(commentButton(aRow)).toHaveAccessibleName('Comment 추가 (읽지 않은 2건)')
    expect(within(aRow).getByText('2')).toBeVisible()
    // then: P 행은 "Comment 추가"이고 배지가 없다
    const pRow = rowWith(view.table, '현장 점검')
    expect(commentButton(pRow)).toHaveAccessibleName('Comment 추가')
    expect(within(pRow).queryByText(/^\d+\+?$/)).not.toBeInTheDocument()
  })

  // user에게는 같은 열이 "Comment 보기"다.
  // 테스트 코드: CM-073
  it('names the button "Comment 보기" for a read-only user', async () => {
    // given: A에 읽지 않은 Comment 2건이 있고 한조회(user)가 Actions 탭을 연다
    const { view, a } = await openWithAP({ role: 'user' })
    await seedComments(view, [
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: '읽지 않은 1', createdAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: '읽지 않은 2', createdAt: '2026-11-12T09:10:00+09:00' },
    ])

    // when·then: A 행 버튼이 "Comment 보기 (읽지 않은 2건)"이고 P 행은 "Comment 보기"다
    await screen.findByRole('button', { name: 'Comment 보기 (읽지 않은 2건)' })
    expect(commentButton(rowWith(view.table, '현장 점검'))).toHaveAccessibleName('Comment 보기')
  })

  // 100건 이상의 읽지 않은 수는 배지에 "99+"로 보인다.
  // 테스트 코드: CM-073
  it('caps the row badge at 99+', async () => {
    // given: A에 읽지 않은 Comment 120건
    const { view, a } = await openWithAP({ userId: USER_ID.park })
    await seedComments(view, Array.from({ length: 120 }, (_, i) => ({
      dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: `글 ${i}`, createdAt: `2026-11-12T09:${String(i % 60).padStart(2, '0')}:00+09:00`,
    })))

    // when·then: A 행 배지가 "99+"다
    await waitFor(() => expect(within(rowWith(view.table, '킥오프 미팅')).getByText('99+')).toBeVisible())
  })
})

describe('Comment 아이콘', () => {
  // 쓰기 권한자가 누르면 상세 팝업이 열리고 포커스가 "Comment 입력"에 있다. 상태는 바뀌지 않는다.
  // 테스트 코드: CM-074
  it('opens the detail popup with the focus on the comment box for a writer without changing any state', async () => {
    // given: KIM의 Action A를 박영업이 본다(상태 변경 요청 감시)
    const change = vi.spyOn(gateway.actions, 'changeNextActionStatus')
    const { view } = await openWithAP({ userId: USER_ID.park })

    // when: 박영업이 A 행의 Comment 아이콘을 누른다
    await view.user.click(commentButton(rowWith(view.table, '킥오프 미팅')))

    // then: "Action 상세" 팝업이 열리고 포커스가 "Comment 입력"에 있으며 상태 변경은 없다
    const dialog = await screen.findByRole('dialog', { name: DETAIL })
    await waitFor(() => expect(within(dialog).getByLabelText('Comment 입력')).toHaveFocus())
    expect(change).not.toHaveBeenCalled()
    expect(within(rowWith(view.table, '킥오프 미팅')).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  // user가 누르면 팝업의 Comment 영역이 보이고 입력 칸은 없다.
  // 테스트 코드: CM-074
  it('opens the popup with the Comment area and no input box for a read-only user', async () => {
    // given: A에 Comment가 있고 한조회(user)가 본다
    const { view, a } = await openWithAP({ role: 'user' })
    await seedComments(view, [{ dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: '보기만', createdAt: '2026-11-12T09:00:00+09:00' }])

    // when: A 행의 Comment 아이콘을 누른다
    await view.user.click(await screen.findByRole('button', { name: 'Comment 보기 (읽지 않은 1건)' }))

    // then: 팝업 Comment 영역에 글이 보이고 입력 칸이 없다
    const dialog = await screen.findByRole('dialog', { name: DETAIL })
    expect(within(dialog).getByRole('heading', { name: 'Comment (1)' })).toBeVisible()
    expect(within(dialog).getByRole('list', { name: 'Comment 목록' })).toHaveTextContent('보기만')
    expect(within(dialog).queryByLabelText('Comment 입력')).not.toBeInTheDocument()
  })

  // 행의 다른 곳(진행사항 칸)을 누르면 기존처럼 팝업이 열리고 포커스는 입력 칸에 가지 않는다.
  // 테스트 코드: CM-074
  it('opens the popup as before from another cell of the row, without moving the focus to the comment box', async () => {
    // given: 김영업(Owner·작성자)이 연 Actions 탭
    const { view } = await openWithAP({ userId: USER_ID.kim })

    // when: A 행의 진행사항 칸을 누른다
    await view.user.click(within(rowWith(view.table, '킥오프 미팅')).getByText('킥오프 미팅'))

    // then: 팝업이 열리고 포커스는 Comment 입력 칸이 아니다
    const dialog = await screen.findByRole('dialog', { name: DETAIL })
    expect(within(dialog).getByLabelText('Comment 입력')).not.toHaveFocus()
  })
})
